import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

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
    "patreon_url": ("patreon", "URL-ul Patreon trebuie să conțină patreon.com"),
    "paypal_url": ("paypal", "URL-ul PayPal trebuie să conțină paypal.me sau paypal.com"),
    "buymeacoffee_url": ("buymeacoffee", "URL-ul Cumpără-mi o cafea trebuie să conțină buymeacoffee.com"),
}
PROFILE_SETTINGS_FIELDS = (
    "subtitle",
    "avatar_seed",
    "cover_seed",
    "location",
    "youtube_playlist_url",
    *SOCIAL_LINKS.keys(),
)


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


def _current_user_payload(db: Session, user: models.User) -> dict:
    profile_photo_url = _media_url_if_visible(user, "profil")
    cover_photo_url = _media_url_if_visible(user, "coperta")
    cover_seed = user.cover_seed or default_cover_seed(user)
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
        "patreon_url": user.patreon_url,
        "paypal_url": user.paypal_url,
        "buymeacoffee_url": user.buymeacoffee_url,
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
        "gologani_balance": user.gologani_balance or 0,
        "seconds_listened": user.seconds_listened or 0,
        "equipped_items": _serialize_equipped_items(db, user),
    }


def _validate_profile_links(payload) -> None:
    validation_errors = []
    for field, (platform, message) in SOCIAL_LINKS.items():
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
    _apply_profile_fields(current_user, profile_update)
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
    _apply_profile_fields(
        current_user,
        social_update,
        fields=(*SOCIAL_LINKS.keys(), "youtube_playlist_url"),
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
    """Update user's promoted author list (max 2 authors)."""
    try:
        friend_usernames = best_friends_data.friends

        if len(friend_usernames) > crud.PROMOTED_AUTHOR_LIMIT:
            raise HTTPException(status_code=400, detail="Sunt permiși maximum 2 autori promovați")

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

    return [
        {
            "id": user.id,
            "username": user.username,
            "subtitle": rich_text.rich_text_to_plain_text(user.subtitle),
            "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        }
        for user in users
    ]


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
            raise HTTPException(status_code=400, detail="Poți promova cel mult 4 texte proprii")
        if len(author_ids) > crud.PROMOTED_AUTHOR_LIMIT:
            raise HTTPException(status_code=400, detail="Poți promova cel mult 2 autori")
        if len(other_post_ids) > crud.PROMOTED_OTHER_POST_LIMIT:
            raise HTTPException(status_code=400, detail="Poți promova cel mult 2 texte ale altor autori")

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
                detail = "Poți promova cel mult 4 texte proprii"
            else:
                detail = "Poți promova cel mult 2 texte ale altor autori"
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
            raise HTTPException(status_code=400, detail="Poți promova cel mult 2 autori")
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
    """Update user's promoted own posts list (max 4 posts)."""
    try:
        post_ids = _unique_ids(featured_posts_data.post_ids, "textele proprii")

        if len(post_ids) > crud.PROMOTED_OWN_POST_LIMIT:
            raise HTTPException(status_code=400, detail="Sunt permise maximum 4 postări promovate")

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
