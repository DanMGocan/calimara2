import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, crud, auth
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


@router.get("/api/notificari")
def get_notifications(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    notifications = crud.get_notifications_for_user(db, current_user.id, skip, limit)
    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "is_read": n.is_read,
                "extra_data": n.extra_data,
                "created_at": n.created_at.isoformat()
            }
            for n in notifications
        ]
    }


@router.get("/api/notificari/necitite")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    count = crud.get_unread_notification_count(db, current_user.id)
    return {"unread_count": count}


@router.put("/api/notificari/{notification_id}/citita")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    notification = crud.mark_notification_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notificarea nu a fost găsită")
    return {"message": "Notificare marcată ca citită"}


@router.put("/api/notificari/{notification_id}/necitita")
def mark_unread(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    notification = crud.mark_notification_unread(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notificarea nu a fost găsită")
    return {"message": "Notificare marcată ca necitită"}


@router.delete("/api/notificari/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    deleted = crud.delete_notification(db, notification_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notificarea nu a fost găsită")
    return {"message": "Notificare ștearsă"}


@router.put("/api/notificari/citeste-toate")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    crud.mark_all_notifications_read(db, current_user.id)
    return {"message": "Toate notificările au fost marcate ca citite"}
