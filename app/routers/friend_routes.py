import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auth, crud, models, rich_text
from ..database import get_db
from ..utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX, get_avatar_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["friends"])


def _public_scheme() -> str:
    configured = os.getenv("PUBLIC_SCHEME", "").strip().lower()
    if configured:
        return configured
    https_only = os.getenv("HTTPS_ONLY", "True").lower() in {"true", "1", "yes", "on"}
    return "https" if https_only else "http"


def _main_link(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{_public_scheme()}://{MAIN_DOMAIN}{normalized}"


def _author_link(username: str) -> str:
    suffix = SUBDOMAIN_SUFFIX if SUBDOMAIN_SUFFIX.startswith(".") else f".{SUBDOMAIN_SUFFIX}"
    return f"{_public_scheme()}://{username}{suffix}"


def _friend_user_payload(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": rich_text.rich_text_to_plain_text(user.subtitle),
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "avatar_url": get_avatar_url(user, size=96),
    }


def _other_friendship_user(friendship: models.Friendship, current_user_id: int) -> models.User:
    return friendship.user2 if friendship.user1_id == current_user_id else friendship.user1


def _friendship_payload(friendship: models.Friendship, current_user_id: int) -> dict:
    other_user = _other_friendship_user(friendship, current_user_id)
    direction = None
    if friendship.status == "pending":
        direction = "outgoing" if friendship.requested_by_id == current_user_id else "incoming"
    return {
        "id": friendship.id,
        "status": friendship.status,
        "direction": direction,
        "requested_by_id": friendship.requested_by_id,
        "user": _friend_user_payload(other_user),
        "created_at": friendship.created_at.isoformat() if friendship.created_at else None,
        "updated_at": friendship.updated_at.isoformat() if friendship.updated_at else None,
        "responded_at": friendship.responded_at.isoformat() if friendship.responded_at else None,
    }


def _visible_friendship_items(db: Session, current_user_id: int) -> list[models.Friendship]:
    items = crud.get_friendships_for_user(db, current_user_id)
    visible = []
    for item in items:
        other_user = _other_friendship_user(item, current_user_id)
        if other_user and not other_user.is_suspended:
            visible.append(item)
    return visible


def _get_request_target(db: Session, current_user: models.User, user_id: int) -> models.User:
    if current_user.is_suspended:
        raise HTTPException(status_code=403, detail="Contul tău nu poate trimite cereri de prietenie")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Nu îți poți trimite cerere de prietenie ție")
    target = crud.get_user_by_id(db, user_id)
    if not target or target.is_suspended:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    return target


def _notify_friend_request(db: Session, requester: models.User, recipient: models.User, friendship_id: int) -> None:
    crud.create_notification(
        db,
        user_id=recipient.id,
        notif_type="friend_request",
        title="Cerere de prietenie",
        message=f"{requester.username} ți-a trimis o cerere de prietenie.",
        link=_main_link("/prieteni"),
        extra_data={"friendship_id": friendship_id, "requester_id": requester.id},
    )


def _notify_friend_acceptance(db: Session, accepter: models.User, requester: models.User, friendship_id: int) -> None:
    crud.create_notification(
        db,
        user_id=requester.id,
        notif_type="friend_request_accepted",
        title="Cerere acceptată",
        message=f"{accepter.username} ți-a acceptat cererea de prietenie.",
        link=_author_link(accepter.username),
        extra_data={"friendship_id": friendship_id, "friend_id": accepter.id},
    )


@router.get("/api/prieteni")
def get_my_friends(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    items = _visible_friendship_items(db, current_user.id)
    accepted = [item for item in items if item.status == "accepted"]
    incoming = [
        item
        for item in items
        if item.status == "pending" and item.requested_by_id != current_user.id
    ]
    outgoing = [
        item
        for item in items
        if item.status == "pending" and item.requested_by_id == current_user.id
    ]
    return {
        "friends": [_friendship_payload(item, current_user.id) for item in accepted],
        "incoming_requests": [_friendship_payload(item, current_user.id) for item in incoming],
        "outgoing_requests": [_friendship_payload(item, current_user.id) for item in outgoing],
        "counts": {
            "friends": len(accepted),
            "incoming": len(incoming),
            "outgoing": len(outgoing),
        },
    }


@router.get("/api/prieteni/status/{user_id}")
def get_friendship_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    target = crud.get_user_by_id(db, user_id)
    if not target or target.is_suspended:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    friendship = crud.get_friendship_between(db, current_user.id, target.id) if current_user.id != target.id else None
    return {
        "user_id": target.id,
        "status": crud.get_friendship_status_for_viewer(db, current_user.id, target.id),
        "friendship_id": friendship.id if friendship else None,
    }


@router.post("/api/prieteni/cereri/{user_id}")
def send_friend_request(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    target = _get_request_target(db, current_user, user_id)
    existing = crud.get_friendship_between(db, current_user.id, target.id)
    if existing:
        if existing.status == "accepted":
            return {"success": True, "status": "friends", "friendship": _friendship_payload(existing, current_user.id)}
        if existing.requested_by_id == current_user.id:
            return {"success": True, "status": "outgoing_pending", "friendship": _friendship_payload(existing, current_user.id)}

        try:
            crud.accept_friendship(db, existing)
            db.commit()
            db.refresh(existing)
        except Exception as exc:
            db.rollback()
            logger.error("Eroare la acceptarea automată a cererii de prietenie %s: %s", existing.id, exc)
            raise HTTPException(status_code=500, detail="Nu am putut accepta cererea de prietenie")
        _notify_friend_acceptance(db, current_user, target, existing.id)
        return {"success": True, "status": "friends", "friendship": _friendship_payload(existing, current_user.id)}

    try:
        friendship = crud.create_friend_request(db, current_user.id, target.id)
        db.commit()
        db.refresh(friendship)
    except IntegrityError:
        db.rollback()
        friendship = crud.get_friendship_between(db, current_user.id, target.id)
        if not friendship:
            raise HTTPException(status_code=409, detail="Cererea de prietenie există deja")
        return {
            "success": True,
            "status": crud.get_friendship_status_for_viewer(db, current_user.id, target.id),
            "friendship": _friendship_payload(friendship, current_user.id),
        }
    except Exception as exc:
        db.rollback()
        logger.error("Eroare la trimiterea cererii de prietenie către %s: %s", target.username, exc)
        raise HTTPException(status_code=500, detail="Nu am putut trimite cererea de prietenie")

    _notify_friend_request(db, current_user, target, friendship.id)
    return {"success": True, "status": "outgoing_pending", "friendship": _friendship_payload(friendship, current_user.id)}


@router.post("/api/prieteni/cereri/{friendship_id}/accepta")
def accept_friend_request(
    friendship_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    friendship = db.get(models.Friendship, friendship_id)
    if not friendship or current_user.id not in {friendship.user1_id, friendship.user2_id}:
        raise HTTPException(status_code=404, detail="Cererea de prietenie nu a fost găsită")
    if friendship.status != "pending" or friendship.requested_by_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cererea de prietenie nu poate fi acceptată")
    requester = crud.get_user_by_id(db, friendship.requested_by_id)
    if not requester or requester.is_suspended:
        raise HTTPException(status_code=400, detail="Cererea de prietenie nu mai este validă")
    try:
        crud.accept_friendship(db, friendship)
        db.commit()
        db.refresh(friendship)
    except Exception as exc:
        db.rollback()
        logger.error("Eroare la acceptarea cererii de prietenie %s: %s", friendship_id, exc)
        raise HTTPException(status_code=500, detail="Nu am putut accepta cererea de prietenie")

    _notify_friend_acceptance(db, current_user, requester, friendship.id)
    return {"success": True, "status": "friends", "friendship": _friendship_payload(friendship, current_user.id)}


@router.delete("/api/prieteni/cereri/{friendship_id}")
def delete_friend_request(
    friendship_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    friendship = db.get(models.Friendship, friendship_id)
    if not friendship or current_user.id not in {friendship.user1_id, friendship.user2_id}:
        raise HTTPException(status_code=404, detail="Cererea de prietenie nu a fost găsită")
    if friendship.status != "pending":
        raise HTTPException(status_code=400, detail="Relația de prietenie nu este o cerere în așteptare")
    try:
        crud.delete_friendship(db, friendship)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Eroare la ștergerea cererii de prietenie %s: %s", friendship_id, exc)
        raise HTTPException(status_code=500, detail="Nu am putut șterge cererea de prietenie")
    return {"success": True, "status": "none"}


@router.delete("/api/prieteni/{user_id}")
def remove_friend(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    target = crud.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    friendship = crud.get_friendship_between(db, current_user.id, target.id)
    if not friendship or friendship.status != "accepted":
        raise HTTPException(status_code=404, detail="Prietenia nu a fost găsită")
    try:
        crud.delete_friendship(db, friendship)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Eroare la eliminarea prieteniei cu %s: %s", target.username, exc)
        raise HTTPException(status_code=500, detail="Nu am putut elimina prietenul")
    return {"success": True, "status": "none"}
