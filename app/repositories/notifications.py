from ._shared import *

def create_notification(db: Session, user_id: int, notif_type: str, title: str, message: Optional[str] = None, link: Optional[str] = None, extra_data: Optional[dict] = None) -> models.Notification:
    notification = models.Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        link=link,
        extra_data=extra_data or {}
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

def get_notifications_for_user(db: Session, user_id: int, skip: int = 0, limit: int = 20):
    return db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).order_by(
        models.Notification.created_at.desc(),
        models.Notification.id.desc(),
    ).offset(skip).limit(limit).all()

def get_unread_notification_count(db: Session, user_id: int):
    return db.query(models.Notification).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).count()

def mark_notification_read(db: Session, notification_id: int, user_id: int):
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user_id
    ).first()
    if notification:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification

def mark_all_notifications_read(db: Session, user_id: int):
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()

# ===================================
# MODERATION LOG CRUD FUNCTIONS
# ===================================
