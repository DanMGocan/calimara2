from ._shared import *


def get_follow(db: Session, follower_id: int, followed_id: int):
    return (
        db.query(models.UserFollow)
        .filter(
            models.UserFollow.follower_id == follower_id,
            models.UserFollow.followed_id == followed_id,
        )
        .first()
    )


def is_following(db: Session, follower_id: Optional[int], followed_id: int) -> bool:
    if not follower_id or follower_id == followed_id:
        return False
    return get_follow(db, follower_id, followed_id) is not None


def create_follow(db: Session, follower_id: int, followed_id: int):
    follow = models.UserFollow(follower_id=follower_id, followed_id=followed_id)
    db.add(follow)
    db.flush()
    return follow


def delete_follow(db: Session, follow: models.UserFollow) -> None:
    db.delete(follow)
    db.flush()


def get_follower_count_for_user(db: Session, user_id: int) -> int:
    follower = aliased(models.User)
    return (
        db.query(models.UserFollow.id)
        .join(follower, models.UserFollow.follower_id == follower.id)
        .filter(
            models.UserFollow.followed_id == user_id,
            follower.is_suspended == False,
        )
        .count()
    )


def get_following_count_for_user(db: Session, user_id: int) -> int:
    followed = aliased(models.User)
    return (
        db.query(models.UserFollow.id)
        .join(followed, models.UserFollow.followed_id == followed.id)
        .filter(
            models.UserFollow.follower_id == user_id,
            followed.is_suspended == False,
        )
        .count()
    )


def get_followers_for_user(db: Session, user_id: int, limit: int = 50, offset: int = 0):
    return (
        db.query(models.User)
        .join(models.UserFollow, models.UserFollow.follower_id == models.User.id)
        .filter(
            models.UserFollow.followed_id == user_id,
            models.User.is_suspended == False,
        )
        .order_by(models.UserFollow.created_at.desc(), models.UserFollow.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_following_for_user(db: Session, user_id: int, limit: int = 50, offset: int = 0):
    return (
        db.query(models.User)
        .join(models.UserFollow, models.UserFollow.followed_id == models.User.id)
        .filter(
            models.UserFollow.follower_id == user_id,
            models.User.is_suspended == False,
        )
        .order_by(models.UserFollow.created_at.desc(), models.UserFollow.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
