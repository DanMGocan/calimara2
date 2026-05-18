import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, aliased

from .. import models, schemas, auth, crud, profile_media, rich_text
from ..categories import get_category_name
from ..database import get_db
from ..utils import default_cover_seed, get_avatar_url, get_cover_url, validate_social_url, validate_youtube_playlist_url
from ..week_util import utcnow_naive

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])

SOCIAL_LINKS = {
    "facebook_url": ("facebook", "URL-ul Facebook trebuie să conțină facebook.com sau fb.com"),
    "instagram_url": ("instagram", "URL-ul Instagram trebuie să conțină instagram.com"),
    "tiktok_url": ("tiktok", "URL-ul TikTok trebuie să conțină tiktok.com"),
    "x_url": ("x", "URL-ul X trebuie să conțină x.com sau twitter.com"),
    "bluesky_url": ("bluesky", "URL-ul BlueSky trebuie să conțină bsky.app"),
}
SUPPORT_LINKS = {
    "patreon_url": ("patreon", "URL-ul Patreon trebuie să conțină patreon.com"),
    "paypal_url": ("paypal", "URL-ul PayPal trebuie să conțină paypal.me sau paypal.com"),
    "buymeacoffee_url": ("buymeacoffee", "URL-ul Cumpără-mi o cafea trebuie să conțină buymeacoffee.com"),
}
PROFILE_LINKS = {**SOCIAL_LINKS, **SUPPORT_LINKS}
SUPPORT_LINK_FIELDS = tuple(SUPPORT_LINKS.keys())
SUPPORT_LINK_PREMIUM_TIERS = {"trubadur", "cronicar", "rapsod"}
PROFILE_SETTINGS_FIELDS = (
    "subtitle",
    "avatar_seed",
    "cover_seed",
    "location",
    "youtube_playlist_url",
    *PROFILE_LINKS.keys(),
)

USER_DIRECTORY_RELATIONSHIPS = {
    "all",
    "not_friends",
    "friends",
    "incoming_pending",
    "outgoing_pending",
    "following",
    "followers",
}
USER_DIRECTORY_SORTS = {"newest", "oldest", "username", "posts", "views", "comments", "followers"}


def _media_url_if_visible(user: models.User, kind: str) -> Optional[str]:
    config = profile_media.media_kind_config(kind)
    key = getattr(user, f"{config['prefix']}_storage_key", None)
    if not key or not user.is_premium:
        return None
    return profile_media.public_media_url(user.username, kind)


def _serialize_equipped_items(db: Session, user: models.User) -> list[dict]:
    equipped_items = crud.get_equipped_items_for_user(db, user.id)
    return [
        {
            "slot": equipped.slot,
            "item": {
                "id": equipped.item.id,
                "slug": equipped.item.slug,
                "name": equipped.item.name,
                "description": equipped.item.description,
                "price": equipped.item.price,
                "slot": equipped.item.slot,
                "asset_url": equipped.item.asset_url,
                "is_active": equipped.item.is_active,
                "sort_order": equipped.item.sort_order,
            },
        }
        for equipped in equipped_items
        if equipped.item
    ]


def _support_links_payload(user: models.User) -> dict[str, Optional[str]]:
    if not _can_use_support_links(user):
        return {field: None for field in SUPPORT_LINK_FIELDS}
    return {field: getattr(user, field) for field in SUPPORT_LINK_FIELDS}


def _can_use_support_links(user: models.User) -> bool:
    return user.is_premium and (user.premium_tier or "free") in SUPPORT_LINK_PREMIUM_TIERS


def _current_user_payload(db: Session, user: models.User) -> dict:
    profile_photo_url = _media_url_if_visible(user, "profil")
    cover_photo_url = _media_url_if_visible(user, "coperta")
    cover_seed = user.cover_seed or default_cover_seed(user)
    stafeta_state = crud.get_stafeta_participation_state(db, user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "subtitle": rich_text.sanitize_optional_rich_text(user.subtitle),
        "avatar_seed": user.avatar_seed,
        "cover_seed": cover_seed,
        "avatar_url": profile_photo_url or get_avatar_url(user, size=160),
        "profile_photo_url": profile_photo_url,
        "cover_photo_url": cover_photo_url,
        "cover_url": cover_photo_url or get_cover_url(cover_seed),
        "has_profile_photo": bool(user.profile_photo_storage_key),
        "has_cover_photo": bool(user.cover_photo_storage_key),
        "location": user.location,
        "youtube_playlist_url": user.youtube_playlist_url,
        "facebook_url": user.facebook_url,
        "tiktok_url": user.tiktok_url,
        "instagram_url": user.instagram_url,
        "x_url": user.x_url,
        "bluesky_url": user.bluesky_url,
        **_support_links_payload(user),
        "is_admin": user.is_admin,
        "is_moderator": user.is_moderator,
        "is_suspended": user.is_suspended,
        "is_premium": user.is_premium,
        "has_audio_access": user.has_audio_access,
        "has_author_audio_access": user.has_author_audio_access,
        "premium_tier": user.premium_tier,
        "premium_period_start": user.premium_period_start.isoformat() if user.premium_period_start else None,
        "premium_until": user.premium_until.isoformat() if user.premium_until else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "email_comment_notifications": user.email_comment_notifications,
        "email_mention_notifications": user.email_mention_notifications,
        "email_analytics_digest": user.email_analytics_digest,
        "email_admin_announcements": user.email_admin_announcements,
        "stafeta_participates": stafeta_state["participates"],
        "stafeta_desired_slots": stafeta_state["desired_slots"],
        "stafeta_max_slots": stafeta_state["max_slots"],
        "stafeta_open_assignments": stafeta_state["open_assignments"],
        "gologani_balance": user.gologani_balance or 0,
        "seconds_listened": user.seconds_listened or 0,
        "incoming_friend_request_count": crud.get_incoming_friend_request_count(db, user.id),
        "equipped_items": _serialize_equipped_items(db, user),
    }


def _validate_profile_links(payload) -> None:
    validation_errors = []
    for field, (platform, message) in PROFILE_LINKS.items():
        value = getattr(payload, field, None)
        if value and not validate_social_url(value, platform):
            validation_errors.append(message)

    youtube_playlist_url = getattr(payload, "youtube_playlist_url", None)
    if youtube_playlist_url and not validate_youtube_playlist_url(youtube_playlist_url):
        validation_errors.append("Playlistul YouTube trebuie să fie un link valid cu parametrul list")

    if validation_errors:
        raise HTTPException(status_code=422, detail="; ".join(validation_errors))


def _apply_profile_fields(current_user: models.User, payload, fields=PROFILE_SETTINGS_FIELDS) -> None:
    provided_fields = getattr(payload, "model_fields_set", set())
    for field in fields:
        if field in provided_fields:
            setattr(current_user, field, getattr(payload, field))


def _ensure_support_links_allowed(current_user: models.User, payload) -> None:
    if _can_use_support_links(current_user):
        return
    provided_fields = getattr(payload, "model_fields_set", set())
    has_support_value = any(
        field in provided_fields and bool(getattr(payload, field, None))
        for field in SUPPORT_LINK_FIELDS
    )
    if has_support_value:
        raise HTTPException(
            status_code=403,
            detail="Linkurile pentru donații sunt disponibile pentru utilizatorii Premium.",
        )


def _site_feedback_payload(item: models.SiteFeedback) -> dict:
    return {
        "id": item.id,
        "kind": item.kind,
        "user_id": item.user_id,
        "username_snapshot": item.username_snapshot,
        "email_snapshot": item.email_snapshot,
        "message": item.message,
        "page_url": item.page_url,
        "user_agent": item.user_agent,
        "client_context": item.client_context or {},
        "status": item.status,
        "admin_note": item.admin_note,
        "resolved_by": item.resolved_by,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _promotion_user_payload(db: Session, user: models.User, viewer_promoted: bool = False) -> dict:
    profile_photo_url = _media_url_if_visible(user, "profil")
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": rich_text.sanitize_optional_rich_text(user.subtitle),
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "avatar_url": profile_photo_url or get_avatar_url(user, size=96),
        "is_premium": user.is_premium,
        "premium_tier": user.premium_tier or "free",
        "viewer_promoted": viewer_promoted,
    }


def _promotion_post_payload(db: Session, post: models.Post, viewer_promoted: bool = False) -> dict:
    owner = post.owner or crud.get_user_by_id(db, post.user_id)
    return {
        "id": post.id,
        "user_id": post.user_id,
        "title": post.title,
        "slug": post.slug,
        "content": rich_text.sanitize_rich_text(post.content),
        "category": post.category,
        "category_name": get_category_name(post.category) if post.category else "",
        "moderation_status": post.moderation_status,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "owner": _promotion_user_payload(db, owner) if owner else None,
        "viewer_promoted": viewer_promoted,
    }


def _promotions_payload(db: Session, current_user: models.User) -> dict:
    promoted_post_ids = crud.get_promoted_post_ids_for_user(db, current_user.id)
    promoted_author_ids = crud.get_promoted_author_ids_for_user(db, current_user.id)
    own_entries = crud.get_promoted_own_post_entries_for_user(db, current_user.id)
    author_entries = crud.get_promoted_authors_for_user(db, current_user.id)
    other_entries = crud.get_promoted_other_post_entries_for_user(db, current_user.id)
    return {
        "limits": crud.promotion_limits(),
        "own_posts": [
            _promotion_post_payload(db, entry.post, entry.post_id in promoted_post_ids)
            for entry in own_entries
        ],
        "authors": [
            _promotion_user_payload(db, entry.friend, entry.friend_user_id in promoted_author_ids)
            for entry in author_entries
            if entry.friend
        ],
        "other_posts": [
            _promotion_post_payload(db, entry.post, entry.post_id in promoted_post_ids)
            for entry in other_entries
        ],
    }


def _unique_ids(raw_ids, field_label: str) -> list[int]:
    ids = []
    seen = set()
    for raw_id in raw_ids or []:
        if not raw_id:
            continue
        item_id = int(raw_id)
        if item_id in seen:
            raise HTTPException(status_code=400, detail=f"Lista pentru {field_label} conține duplicate")
        seen.add(item_id)
        ids.append(item_id)
    return ids


def _author_has_public_posts(db: Session, user_id: int) -> bool:
    return (
        db.query(models.Post.id)
        .filter(
            models.Post.user_id == user_id,
            models.Post.moderation_status == "approved",
        )
        .first()
        is not None
    )


def _get_promotable_author(db: Session, current_user: models.User, author_id: int) -> models.User:
    author = crud.get_user_by_id(db, author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Autorul nu a fost găsit")
    if author.id == current_user.id:
        raise HTTPException(status_code=400, detail="Nu te poți promova pe tine ca autor extern")
    if author.is_suspended:
        raise HTTPException(status_code=400, detail="Autorul nu poate fi promovat")
    if not _author_has_public_posts(db, author.id):
        raise HTTPException(status_code=400, detail="Poți promova doar autori cu texte publice aprobate")
    return author


def _get_promotable_post(
    db: Session,
    current_user: models.User,
    post_id: int,
    *,
    require_own: Optional[bool] = None,
) -> models.Post:
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Textul nu a fost găsit")
    if post.moderation_status != "approved":
        raise HTTPException(status_code=400, detail="Poți promova doar texte aprobate")
    if require_own is True and post.user_id != current_user.id:
        raise HTTPException(status_code=400, detail="Poți promova aici doar textele tale")
    if require_own is False and post.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Poți promova aici doar textele altor autori")
    if post.user_id != current_user.id and post.owner and post.owner.is_suspended:
        raise HTTPException(status_code=400, detail="Textul nu poate fi promovat")
    return post


@router.get("/api/utilizator/eu")
def get_current_user_info(
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Endpoint to check current user authentication status"""
    if current_user:
        data = {
            "authenticated": True,
            "user": _current_user_payload(db, current_user),
        }
    else:
        data = {"authenticated": False, "user": None}
    response = JSONResponse(content=data)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/api/site-feedback", status_code=status.HTTP_201_CREATED)
def create_site_feedback(
    request: Request,
    data: schemas.SiteFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    user_agent = request.headers.get("user-agent")
    item = models.SiteFeedback(
        kind=data.kind,
        user_id=current_user.id,
        username_snapshot=current_user.username,
        email_snapshot=current_user.email,
        message=data.message,
        page_url=data.page_url,
        user_agent=user_agent[:2000] if user_agent else None,
        client_context=data.client_context or {},
        status="open",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _site_feedback_payload(item)


@router.put("/api/utilizator/eu", response_model=schemas.UserInDB)
def update_current_user(
    user_update: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea profilului pentru utilizatorul: {current_user.username}")

    # Update legacy profile fields
    if "subtitle" in user_update.model_fields_set:
        current_user.subtitle = user_update.subtitle
    if "avatar_seed" in user_update.model_fields_set:
        current_user.avatar_seed = user_update.avatar_seed
    if "cover_seed" in user_update.model_fields_set:
        current_user.cover_seed = user_update.cover_seed
    if "location" in user_update.model_fields_set:
        current_user.location = user_update.location

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Profil utilizator actualizat cu succes: {current_user.username}")
    return current_user


@router.put("/api/utilizator/profil")
def update_profile_settings(
    profile_update: schemas.UserProfileSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    logger.info(f"Se încearcă actualizarea experienței de profil pentru utilizatorul: {current_user.username}")
    _validate_profile_links(profile_update)
    _ensure_support_links_allowed(current_user, profile_update)
    can_use_support_links = _can_use_support_links(current_user)
    fields = PROFILE_SETTINGS_FIELDS if can_use_support_links else tuple(
        field for field in PROFILE_SETTINGS_FIELDS if field not in SUPPORT_LINK_FIELDS
    )
    _apply_profile_fields(current_user, profile_update, fields=fields)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Experiența de profil a fost actualizată pentru utilizatorul: {current_user.username}")
    return _current_user_payload(db, current_user)


@router.get("/api/utilizator/email-preferinte")
def get_email_preferences(
    current_user: models.User = Depends(auth.get_required_user),
):
    return {
        "email_comment_notifications": current_user.email_comment_notifications,
        "email_mention_notifications": current_user.email_mention_notifications,
        "email_analytics_digest": current_user.email_analytics_digest,
        "email_admin_announcements": current_user.email_admin_announcements,
    }


@router.put("/api/utilizator/email-preferinte")
def update_email_preferences(
    preferences: schemas.EmailPreferences,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    for field in (
        "email_comment_notifications",
        "email_mention_notifications",
        "email_analytics_digest",
        "email_admin_announcements",
    ):
        setattr(current_user, field, getattr(preferences, field))
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return get_email_preferences(current_user)


@router.put("/api/utilizator/linkuri-sociale", response_model=schemas.UserInDB)
def update_user_social_links(
    social_update: schemas.SocialLinksUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea link-urilor sociale pentru utilizatorul: {current_user.username}")
    _validate_profile_links(social_update)
    _ensure_support_links_allowed(current_user, social_update)
    can_use_support_links = _can_use_support_links(current_user)
    fields = (*PROFILE_LINKS.keys(), "youtube_playlist_url") if can_use_support_links else (
        *SOCIAL_LINKS.keys(),
        "youtube_playlist_url",
    )
    _apply_profile_fields(
        current_user,
        social_update,
        fields=fields,
    )

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Link-uri sociale actualizate cu succes pentru utilizatorul: {current_user.username}")
    return current_user


@router.post("/api/utilizator/media/{kind}")
async def upload_profile_media(
    kind: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    config = profile_media.media_kind_config(kind)
    if not current_user.is_premium:
        raise HTTPException(status_code=403, detail="Încărcarea imaginilor de profil este disponibilă pentru utilizatorii Premium")

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in profile_media.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Format de imagine neacceptat")

    max_bytes = profile_media.max_upload_bytes()
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Imaginea depășește {max_mb} MB")
    if not content:
        raise HTTPException(status_code=400, detail="Fișierul imagine este gol")

    processed = profile_media.process_uploaded_image(content, kind)
    old_backend = getattr(current_user, f"{config['prefix']}_storage_backend")
    old_key = getattr(current_user, f"{config['prefix']}_storage_key")
    backend, key, stored_content_type = profile_media.save_profile_media_bytes(
        user_id=current_user.id,
        kind=kind,
        content=processed,
    )
    setattr(current_user, f"{config['prefix']}_storage_backend", backend)
    setattr(current_user, f"{config['prefix']}_storage_key", key)
    setattr(current_user, f"{config['prefix']}_content_type", stored_content_type)
    setattr(current_user, f"{config['prefix']}_updated_at", utcnow_naive())
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    profile_media.delete_stored_media(old_backend, old_key)
    return _current_user_payload(db, current_user)


@router.delete("/api/utilizator/media/{kind}")
def delete_profile_media(
    kind: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    config = profile_media.media_kind_config(kind)
    old_backend = getattr(current_user, f"{config['prefix']}_storage_backend")
    old_key = getattr(current_user, f"{config['prefix']}_storage_key")
    setattr(current_user, f"{config['prefix']}_storage_backend", None)
    setattr(current_user, f"{config['prefix']}_storage_key", None)
    setattr(current_user, f"{config['prefix']}_content_type", None)
    setattr(current_user, f"{config['prefix']}_updated_at", None)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    profile_media.delete_stored_media(old_backend, old_key)
    return _current_user_payload(db, current_user)


@router.get("/api/utilizatori/{username}/media/{kind}")
def get_public_profile_media(
    username: str,
    kind: str,
    db: Session = Depends(get_db),
):
    config = profile_media.media_kind_config(kind)
    user = crud.get_user_by_username(db, username=username)
    if not user or not user.is_premium:
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    backend = getattr(user, f"{config['prefix']}_storage_backend")
    key = getattr(user, f"{config['prefix']}_storage_key")
    content_type = getattr(user, f"{config['prefix']}_content_type") or profile_media.PROFILE_MEDIA_CONTENT_TYPE
    if not key:
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    if backend == "s3":
        return RedirectResponse(profile_media.presigned_media_url(key))
    if backend != "local":
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    path = profile_media.local_path_for_key(key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    return FileResponse(path, media_type=content_type)


@router.put("/api/utilizator/prieteni-apropiati")
def update_best_friends(
    best_friends_data: schemas.BestFriendsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Update user's promoted author list."""
    try:
        friend_usernames = best_friends_data.friends

        if len(friend_usernames) > crud.PROMOTED_AUTHOR_LIMIT:
            raise HTTPException(status_code=400, detail="Sunt permiși maximum 3 autori promovați")

        author_ids = []
        seen = set()
        for username in friend_usernames:
            username = username.strip()
            if not username:
                continue
            friend = db.query(models.User).filter(models.User.username == username).first()
            if not friend:
                raise HTTPException(status_code=400, detail=f"Autorul {username} nu a fost găsit")
            _get_promotable_author(db, current_user, friend.id)
            if friend.id in seen:
                raise HTTPException(status_code=400, detail="Lista de autori promovați conține duplicate")
            seen.add(friend.id)
            author_ids.append(friend.id)

        crud.replace_promoted_authors(db, current_user.id, author_ids)

        db.commit()
        logger.info(f"Autori promovați actualizați pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Autorii promovați au fost actualizați"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea autorilor promovați pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut actualiza autorii promovați")


def _user_directory_payload(
    db: Session,
    user: models.User,
    current_user: models.User,
    approved_post_count: int,
    total_view_count: int,
    approved_comment_count: int,
    follower_count: int,
) -> dict:
    friendship = crud.get_friendship_between(db, current_user.id, user.id)
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": rich_text.rich_text_to_plain_text(user.subtitle),
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "avatar_url": get_avatar_url(user, size=96),
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "friendship_status": crud.get_friendship_status_for_viewer(db, current_user.id, user.id),
        "friendship_id": friendship.id if friendship else None,
        "viewer_following": crud.is_following(db, current_user.id, user.id),
        "viewer_followed_by": crud.is_following(db, user.id, current_user.id),
        "friend_count": crud.get_friend_count_for_user(db, user.id),
        "follower_count": int(follower_count or 0),
        "approved_post_count": int(approved_post_count or 0),
        "total_view_count": int(total_view_count or 0),
        "approved_comment_count": int(approved_comment_count or 0),
    }


@router.get("/api/utilizatori")
def list_users_directory(
    q: str = "",
    relationship: str = "all",
    sort: str = "newest",
    offset: int = 0,
    limit: int = 24,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    term = (q or "").strip()
    relationship = (relationship or "all").strip()
    sort = (sort or "newest").strip()
    if relationship not in USER_DIRECTORY_RELATIONSHIPS:
        relationship = "all"
    if sort not in USER_DIRECTORY_SORTS:
        sort = "newest"
    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or 24), 60))

    post_stats = (
        db.query(
            models.Post.user_id.label("user_id"),
            func.count(models.Post.id).label("approved_post_count"),
            func.coalesce(func.sum(models.Post.view_count), 0).label("total_view_count"),
        )
        .filter(models.Post.moderation_status == "approved")
        .group_by(models.Post.user_id)
        .subquery()
    )
    comment_stats = (
        db.query(
            models.Post.user_id.label("user_id"),
            func.count(models.Comment.id).label("approved_comment_count"),
        )
        .join(models.Comment, models.Comment.post_id == models.Post.id)
        .filter(
            models.Post.moderation_status == "approved",
            models.Comment.approved == True,
        )
        .group_by(models.Post.user_id)
        .subquery()
    )
    follower_user = aliased(models.User)
    follower_stats = (
        db.query(
            models.UserFollow.followed_id.label("user_id"),
            func.count(models.UserFollow.id).label("follower_count"),
        )
        .join(follower_user, models.UserFollow.follower_id == follower_user.id)
        .filter(follower_user.is_suspended == False)
        .group_by(models.UserFollow.followed_id)
        .subquery()
    )

    approved_post_count = func.coalesce(post_stats.c.approved_post_count, 0).label("approved_post_count")
    total_view_count = func.coalesce(post_stats.c.total_view_count, 0).label("total_view_count")
    approved_comment_count = func.coalesce(comment_stats.c.approved_comment_count, 0).label("approved_comment_count")
    follower_count = func.coalesce(follower_stats.c.follower_count, 0).label("follower_count")

    query = (
        db.query(models.User, approved_post_count, total_view_count, approved_comment_count, follower_count)
        .outerjoin(post_stats, post_stats.c.user_id == models.User.id)
        .outerjoin(comment_stats, comment_stats.c.user_id == models.User.id)
        .outerjoin(follower_stats, follower_stats.c.user_id == models.User.id)
        .filter(
            models.User.id != current_user.id,
            models.User.is_suspended == False,
        )
    )

    if term:
        like_term = f"%{term}%"
        query = query.filter(or_(models.User.username.ilike(like_term), models.User.subtitle.ilike(like_term)))

    friendship_exists = (
        db.query(models.Friendship.id)
        .filter(
            or_(
                and_(models.Friendship.user1_id == current_user.id, models.Friendship.user2_id == models.User.id),
                and_(models.Friendship.user2_id == current_user.id, models.Friendship.user1_id == models.User.id),
            )
        )
    )
    if relationship == "not_friends":
        query = query.filter(~friendship_exists.exists())
    elif relationship == "friends":
        query = query.filter(friendship_exists.filter(models.Friendship.status == "accepted").exists())
    elif relationship == "incoming_pending":
        query = query.filter(
            friendship_exists.filter(
                models.Friendship.status == "pending",
                models.Friendship.requested_by_id != current_user.id,
            ).exists()
        )
    elif relationship == "outgoing_pending":
        query = query.filter(
            friendship_exists.filter(
                models.Friendship.status == "pending",
                models.Friendship.requested_by_id == current_user.id,
            ).exists()
        )
    elif relationship == "following":
        query = query.filter(
            db.query(models.UserFollow.id)
            .filter(
                models.UserFollow.follower_id == current_user.id,
                models.UserFollow.followed_id == models.User.id,
            )
            .exists()
        )
    elif relationship == "followers":
        query = query.filter(
            db.query(models.UserFollow.id)
            .filter(
                models.UserFollow.follower_id == models.User.id,
                models.UserFollow.followed_id == current_user.id,
            )
            .exists()
        )

    total = query.with_entities(func.count(models.User.id)).order_by(None).scalar() or 0

    if sort == "oldest":
        query = query.order_by(models.User.created_at.asc(), models.User.id.asc())
    elif sort == "username":
        query = query.order_by(func.lower(models.User.username).asc(), models.User.id.asc())
    elif sort == "posts":
        query = query.order_by(approved_post_count.desc(), func.lower(models.User.username).asc(), models.User.id.asc())
    elif sort == "views":
        query = query.order_by(total_view_count.desc(), func.lower(models.User.username).asc(), models.User.id.asc())
    elif sort == "comments":
        query = query.order_by(approved_comment_count.desc(), func.lower(models.User.username).asc(), models.User.id.asc())
    elif sort == "followers":
        query = query.order_by(follower_count.desc(), func.lower(models.User.username).asc(), models.User.id.asc())
    else:
        query = query.order_by(models.User.created_at.desc(), models.User.id.desc())

    rows = query.offset(offset).limit(limit).all()
    users = [
        _user_directory_payload(db, user, current_user, post_count, views, comments, followers)
        for user, post_count, views, comments, followers in rows
    ]
    return {
        "users": users,
        "total": int(total),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(users) < total,
        "filters": {"q": term, "relationship": relationship, "sort": sort},
    }


@router.get("/api/utilizatori/cauta")
def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Search for users by username for relationship pickers and mentions."""
    term = q.strip()
    if len(term) < 3:
        return []

    users = db.query(models.User).filter(
        models.User.username.ilike(f"%{term}%"),
        models.User.id != current_user.id,
        models.User.is_suspended == False,
    ).order_by(models.User.username.asc()).limit(10).all()

    results = []
    for user in users:
        friendship = crud.get_friendship_between(db, current_user.id, user.id)
        results.append({
            "id": user.id,
            "username": user.username,
            "subtitle": rich_text.rich_text_to_plain_text(user.subtitle),
            "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
            "friendship_status": crud.get_friendship_status_for_viewer(db, current_user.id, user.id),
            "friendship_id": friendship.id if friendship else None,
        })
    return results


@router.get("/api/utilizator/promovari")
def get_my_promotions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return _promotions_payload(db, current_user)


@router.put("/api/utilizator/promovari")
def update_my_promotions(
    promotions: schemas.UserPromotionsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        own_post_ids = _unique_ids(promotions.own_post_ids, "textele proprii")
        author_ids = _unique_ids(promotions.author_ids, "autori")
        other_post_ids = _unique_ids(promotions.other_post_ids, "textele altor autori")

        if len(own_post_ids) > crud.PROMOTED_OWN_POST_LIMIT:
            raise HTTPException(status_code=400, detail="Poți promova cel mult 2 texte proprii")
        if len(author_ids) > crud.PROMOTED_AUTHOR_LIMIT:
            raise HTTPException(status_code=400, detail="Poți promova cel mult 3 autori")
        if len(other_post_ids) > crud.PROMOTED_OTHER_POST_LIMIT:
            raise HTTPException(status_code=400, detail="Poți promova cel mult 3 texte ale altor autori")

        for post_id in own_post_ids:
            _get_promotable_post(db, current_user, post_id, require_own=True)
        for author_id in author_ids:
            _get_promotable_author(db, current_user, author_id)
        for post_id in other_post_ids:
            _get_promotable_post(db, current_user, post_id, require_own=False)

        crud.replace_promoted_own_posts(db, current_user.id, own_post_ids)
        crud.replace_promoted_authors(db, current_user.id, author_ids)
        crud.replace_promoted_other_posts(db, current_user.id, other_post_ids)
        db.commit()
        return _promotions_payload(db, current_user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea promovărilor pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut actualiza promovările")


@router.get("/api/utilizator/promovari/cauta")
def search_promotions(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    results = crud.search_promotable_content(db, current_user, q)
    promoted_post_ids = crud.get_promoted_post_ids_for_user(db, current_user.id)
    promoted_author_ids = crud.get_promoted_author_ids_for_user(db, current_user.id)
    return {
        "own_posts": [
            _promotion_post_payload(db, post, post.id in promoted_post_ids)
            for post in results["own_posts"]
        ],
        "authors": [
            _promotion_user_payload(db, author, author.id in promoted_author_ids)
            for author in results["authors"]
        ],
        "other_posts": [
            _promotion_post_payload(db, post, post.id in promoted_post_ids)
            for post in results["other_posts"]
        ],
    }


@router.post("/api/utilizator/promovari/postari/{post_id}")
def add_promoted_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        post = _get_promotable_post(db, current_user, post_id)
        ok, error = crud.add_promoted_post(db, current_user.id, post)
        if not ok:
            if error == "own_post_limit":
                detail = "Poți promova cel mult 2 texte proprii"
            else:
                detail = "Poți promova cel mult 3 texte ale altor autori"
            raise HTTPException(status_code=400, detail=detail)
        db.commit()
        return {"success": True, "promoted": True, "promotions": _promotions_payload(db, current_user)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la promovarea textului {post_id} pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut promova textul")


@router.delete("/api/utilizator/promovari/postari/{post_id}")
def remove_promoted_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        crud.remove_promoted_post(db, current_user.id, post_id)
        db.commit()
        return {"success": True, "promoted": False, "promotions": _promotions_payload(db, current_user)}
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la eliminarea promovării textului {post_id} pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut elimina promovarea")


@router.post("/api/utilizator/promovari/autori/{author_id}")
def add_promoted_author(
    author_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        author = _get_promotable_author(db, current_user, author_id)
        ok, error = crud.add_promoted_author(db, current_user.id, author.id)
        if not ok and error == "author_limit":
            raise HTTPException(status_code=400, detail="Poți promova cel mult 3 autori")
        db.commit()
        return {"success": True, "promoted": True, "promotions": _promotions_payload(db, current_user)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la promovarea autorului {author_id} pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut promova autorul")


@router.delete("/api/utilizator/promovari/autori/{author_id}")
def remove_promoted_author(
    author_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        crud.remove_promoted_author(db, current_user.id, author_id)
        db.commit()
        return {"success": True, "promoted": False, "promotions": _promotions_payload(db, current_user)}
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la eliminarea promovării autorului {author_id} pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut elimina promovarea")


@router.get("/api/utilizatori/aleatoriu")
def get_random_user(db: Session = Depends(get_db)):
    """Return a single random user who has at least one approved post."""
    user = crud.get_random_user_with_posts(db)
    if not user:
        raise HTTPException(status_code=404, detail="Nu există autori disponibili")
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": rich_text.sanitize_optional_rich_text(user.subtitle),
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
    }


@router.put("/api/utilizator/postari-recomandate")
def update_featured_posts(
    featured_posts_data: schemas.FeaturedPostsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Update user's promoted own posts list."""
    try:
        post_ids = _unique_ids(featured_posts_data.post_ids, "textele proprii")

        if len(post_ids) > crud.PROMOTED_OWN_POST_LIMIT:
            raise HTTPException(status_code=400, detail="Sunt permise maximum 2 postări promovate")

        for post_id in post_ids:
            try:
                _get_promotable_post(db, current_user, post_id, require_own=True)
            except HTTPException as exc:
                if exc.status_code == 404:
                    raise HTTPException(status_code=400, detail=f"Postarea {post_id} nu a fost găsită sau nu aparține utilizatorului")
                raise

        crud.replace_promoted_own_posts(db, current_user.id, post_ids)

        db.commit()
        logger.info(f"Postări promovate actualizate pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Postările promovate au fost actualizate"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea postărilor promovate pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut actualiza postările promovate")
