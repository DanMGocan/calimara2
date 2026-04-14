import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, crud, auth
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


@router.get("/api/notifications")
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


@router.get("/api/notifications/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    count = crud.get_unread_notification_count(db, current_user.id)
    return {"unread_count": count}


@router.put("/api/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    notification = crud.mark_notification_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notificarea nu a fost gasita")
    return {"message": "Notificare marcata ca citita"}


@router.put("/api/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    crud.mark_all_notifications_read(db, current_user.id)
    return {"message": "Toate notificarile au fost marcate ca citite"}
