from ._shared import *
from ..utils import post_public_url


FOLLOWED_USER_NEW_POST = "followed_user_new_post"


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


def _has_followed_post_notification(db: Session, user_id: int, post_id: int) -> bool:
    return (
        db.query(models.Notification.id)
        .filter(
            models.Notification.user_id == user_id,
            models.Notification.type == FOLLOWED_USER_NEW_POST,
            models.Notification.extra_data["post_id"].as_integer() == post_id,
        )
        .first()
        is not None
    )


def notify_followers_of_new_post(db: Session, post: models.Post) -> int:
    if not post or post.moderation_status != "approved":
        return 0
    author = post.owner or db.query(models.User).filter(models.User.id == post.user_id).first()
    if not author:
        return 0

    followers = (
        db.query(models.User)
        .join(models.UserFollow, models.UserFollow.follower_id == models.User.id)
        .filter(
            models.UserFollow.followed_id == post.user_id,
            models.User.id != post.user_id,
            models.User.is_suspended == False,
        )
        .all()
    )
    sent = 0
    for follower in followers:
        if _has_followed_post_notification(db, follower.id, post.id):
            continue
        create_notification(
            db=db,
            user_id=follower.id,
            notif_type=FOLLOWED_USER_NEW_POST,
            title=f"Postare nouă de la {author.username}",
            message=f"{author.username} a publicat „{post.title}”.",
            link=post_public_url(author, post.slug),
            extra_data={
                "source_type": "post",
                "post_id": post.id,
                "author_id": author.id,
                "author_username": author.username,
            },
        )
        sent += 1
    return sent


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

def mark_notification_unread(db: Session, notification_id: int, user_id: int):
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user_id
    ).first()
    if notification:
        notification.is_read = False
        db.commit()
        db.refresh(notification)
    return notification

def delete_notification(db: Session, notification_id: int, user_id: int) -> bool:
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user_id
    ).first()
    if not notification:
        return False
    db.delete(notification)
    db.commit()
    return True

def mark_all_notifications_read(db: Session, user_id: int):
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()

# ===================================
# MODERATION LOG CRUD FUNCTIONS
# ===================================
