import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models, schemas, auth, crud, profile_media, rich_text
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
    """Update user's best friends list (max 3 friends)"""
    try:
        friend_usernames = best_friends_data.friends

        # Validate max 3 friends
        if len(friend_usernames) > 3:
            raise HTTPException(status_code=400, detail="Sunt permiși maximum 3 prieteni apropiați")

        # Remove existing best friends using ORM
        db.query(models.BestFriend).filter(models.BestFriend.user_id == current_user.id).delete()

        # Add new best friends
        for position, username in enumerate(friend_usernames, 1):
            if username.strip():  # Skip empty usernames
                friend = db.query(models.User).filter(models.User.username == username.strip()).first()
                if friend and friend.id != current_user.id:  # Can't add self as best friend
                    new_friendship = models.BestFriend(
                        user_id=current_user.id,
                        friend_user_id=friend.id,
                        position=position
                    )
                    db.add(new_friendship)

        db.commit()
        logger.info(f"Prieteni apropiați actualizați pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Prietenii apropiați au fost actualizați"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea prietenilor apropiați pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut actualiza prietenii apropiați")


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
    """Update user's featured posts list (max 3 posts)"""
    try:
        post_ids = featured_posts_data.post_ids

        # Validate max 3 posts
        if len(post_ids) > 3:
            raise HTTPException(status_code=400, detail="Sunt permise maximum 3 postări recomandate")

        # Validate that all posts belong to the user
        for post_id in post_ids:
            if post_id:  # Skip empty IDs
                post = db.query(models.Post).filter(
                    models.Post.id == post_id,
                    models.Post.user_id == current_user.id
                ).first()
                if not post:
                    raise HTTPException(status_code=400, detail=f"Postarea {post_id} nu a fost găsită sau nu aparține utilizatorului")

        # Remove existing featured posts using ORM
        db.query(models.FeaturedPost).filter(models.FeaturedPost.user_id == current_user.id).delete()

        # Add new featured posts
        for position, post_id in enumerate(post_ids, 1):
            if post_id:  # Skip empty post IDs
                new_featured = models.FeaturedPost(
                    user_id=current_user.id,
                    post_id=post_id,
                    position=position
                )
                db.add(new_featured)

        db.commit()
        logger.info(f"Postări recomandate actualizate pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Postările recomandate au fost actualizate"}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea postărilor recomandate pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut actualiza postările recomandate")
