import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auth, crud, models, rich_text
from ..database import get_db
from ..utils import SUBDOMAIN_SUFFIX, get_avatar_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["follows"])


def _public_scheme() -> str:
    configured = os.getenv("PUBLIC_SCHEME", "").strip().lower()
    if configured:
        return configured
    https_only = os.getenv("HTTPS_ONLY", "True").lower() in {"true", "1", "yes", "on"}
    return "https" if https_only else "http"


def _author_link(username: str) -> str:
    suffix = SUBDOMAIN_SUFFIX if SUBDOMAIN_SUFFIX.startswith(".") else f".{SUBDOMAIN_SUFFIX}"
    return f"{_public_scheme()}://{username}{suffix}"


def _follow_user_payload(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": rich_text.rich_text_to_plain_text(user.subtitle),
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "avatar_url": get_avatar_url(user, size=96),
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
    }


def _follow_status_payload(db: Session, viewer_id: int | None, target_id: int) -> dict:
    if viewer_id == target_id:
        return {"user_id": target_id, "status": "self", "following": False}
    following = crud.is_following(db, viewer_id, target_id)
    return {
        "user_id": target_id,
        "status": "following" if following else "none",
        "following": following,
    }


def _bounded_pagination(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(int(limit or 50), 100)), max(0, int(offset or 0))


def _get_follow_target(db: Session, current_user: models.User, user_id: int) -> models.User:
    if current_user.is_suspended:
        raise HTTPException(status_code=403, detail="Contul tău nu poate urmări alți utilizatori")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Nu te poți urmări pe tine")
    target = crud.get_user_by_id(db, user_id)
    if not target or target.is_suspended:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    return target


def _notify_follow(db: Session, follower: models.User, followed: models.User, follow_id: int) -> None:
    crud.create_notification(
        db,
        user_id=followed.id,
        notif_type="follow",
        title="Urmăritor nou",
        message=f"{follower.username} te urmărește.",
        link=_author_link(follower.username),
        extra_data={"follow_id": follow_id, "follower_id": follower.id},
    )


@router.get("/api/urmariri/status/{user_id}")
def get_follow_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    target = crud.get_user_by_id(db, user_id)
    if not target or target.is_suspended:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    return _follow_status_payload(db, current_user.id, target.id)


@router.post("/api/urmariri/{user_id}")
def follow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    target = _get_follow_target(db, current_user, user_id)
    existing = crud.get_follow(db, current_user.id, target.id)
    if existing:
        return {"success": True, "following": True, "follow_id": existing.id}

    try:
        follow = crud.create_follow(db, current_user.id, target.id)
        db.commit()
        db.refresh(follow)
    except IntegrityError:
        db.rollback()
        follow = crud.get_follow(db, current_user.id, target.id)
        if not follow:
            raise HTTPException(status_code=409, detail="Urmărirea există deja")
        return {"success": True, "following": True, "follow_id": follow.id}
    except Exception as exc:
        db.rollback()
        logger.error("Eroare la urmărirea utilizatorului %s de către %s: %s", target.username, current_user.username, exc)
        raise HTTPException(status_code=500, detail="Nu am putut urmări utilizatorul")

    _notify_follow(db, current_user, target, follow.id)
    return {"success": True, "following": True, "follow_id": follow.id}


@router.delete("/api/urmariri/{user_id}")
def unfollow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    target = crud.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    follow = crud.get_follow(db, current_user.id, target.id)
    if not follow:
        return {"success": True, "following": False}
    try:
        crud.delete_follow(db, follow)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Eroare la oprirea urmăririi utilizatorului %s de către %s: %s", target.username, current_user.username, exc)
        raise HTTPException(status_code=500, detail="Nu am putut opri urmărirea")
    return {"success": True, "following": False}


@router.get("/api/utilizatori/{username}/urmaritori")
def get_public_followers(
    username: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username=username)
    if not user or user.is_suspended:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    limit, offset = _bounded_pagination(limit, offset)
    followers = crud.get_followers_for_user(db, user.id, limit=limit, offset=offset)
    return {
        "owner": _follow_user_payload(user),
        "followers": [_follow_user_payload(item) for item in followers],
        "count": crud.get_follower_count_for_user(db, user.id),
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/utilizatori/{username}/urmariti")
def get_public_following(
    username: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username=username)
    if not user or user.is_suspended:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    limit, offset = _bounded_pagination(limit, offset)
    following = crud.get_following_for_user(db, user.id, limit=limit, offset=offset)
    return {
        "owner": _follow_user_payload(user),
        "following": [_follow_user_payload(item) for item in following],
        "count": crud.get_following_count_for_user(db, user.id),
        "limit": limit,
        "offset": offset,
    }
