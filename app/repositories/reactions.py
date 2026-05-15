from ._shared import *
from .economy import award_like_created, award_super_like_created
from ..achievements import emit_super_like_created

def create_like(db: Session, post_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None):
    existing_like = None
    if user_id:
        existing_like = db.query(models.Like).filter(models.Like.post_id == post_id, models.Like.user_id == user_id).first()
    elif ip_address:
        existing_like = db.query(models.Like).filter(models.Like.post_id == post_id, models.Like.ip_address == ip_address).first()
    
    if existing_like:
        return None

    db_like = models.Like(post_id=post_id, user_id=user_id, ip_address=ip_address)
    db.add(db_like)
    db.commit()
    db.refresh(db_like)
    award_like_created(db, db_like)
    db.refresh(db_like)
    return db_like

def get_likes_count_for_post(db: Session, post_id: int):
    return db.query(models.Like).filter(models.Like.post_id == post_id).count()

def get_user_total_likes(db: Session, user_id: int):
    return db.query(models.Like).join(models.Post).filter(models.Post.user_id == user_id).count()

# ===================================
# FEATURED & BEST FRIENDS
# ===================================

FREE_WEEKLY_QUOTA = 1

PREMIUM_WEEKLY_QUOTA = 3

class SuperLikeError(Exception):
    """Base class for super-like errors."""

class SuperLikePostNotFoundError(SuperLikeError):
    pass

class SuperLikeSelfError(SuperLikeError):
    pass

class SuperLikeDuplicateError(SuperLikeError):
    pass

class SuperLikeQuotaError(SuperLikeError):
    pass

def weekly_quota_for_user(user: models.User) -> int:
    return PREMIUM_WEEKLY_QUOTA if user.is_premium else FREE_WEEKLY_QUOTA

def get_user_weekly_super_like_count(db: Session, user_id: int) -> int:
    # SQLAlchemy stores naive datetimes on SQLite; strip tzinfo for cross-DB portability.
    week_start = start_of_iso_week_utc().replace(tzinfo=None)
    return (
        db.query(models.SuperLike)
        .filter(
            models.SuperLike.user_id == user_id,
            models.SuperLike.created_at >= week_start,
        )
        .count()
    )

def get_super_likes_count_for_post(db: Session, post_id: int) -> int:
    return db.query(models.SuperLike).filter(models.SuperLike.post_id == post_id).count()

def user_super_liked_post(db: Session, user_id: int, post_id: int) -> bool:
    return (
        db.query(models.SuperLike.id)
        .filter(models.SuperLike.user_id == user_id, models.SuperLike.post_id == post_id)
        .first()
        is not None
    )

def create_super_like(db: Session, user: models.User, post_id: int) -> models.SuperLike:
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise SuperLikePostNotFoundError()
    if post.user_id == user.id:
        raise SuperLikeSelfError()
    if user_super_liked_post(db, user_id=user.id, post_id=post_id):
        raise SuperLikeDuplicateError()
    used = get_user_weekly_super_like_count(db, user.id)
    if used >= weekly_quota_for_user(user):
        raise SuperLikeQuotaError()
    sl = models.SuperLike(user_id=user.id, post_id=post_id)
    db.add(sl)
    try:
        db.commit()
    except Exception:
        # Race condition: a concurrent request inserted the same (user_id, post_id).
        db.rollback()
        raise SuperLikeDuplicateError()
    db.refresh(sl)
    award_super_like_created(db, sl)
    emit_super_like_created(db, sl)
    db.refresh(sl)
    return sl

def delete_super_like(db: Session, user: models.User, post_id: int) -> bool:
    sl = (
        db.query(models.SuperLike)
        .filter(models.SuperLike.user_id == user.id, models.SuperLike.post_id == post_id)
        .first()
    )
    if not sl:
        return False
    db.delete(sl)
    db.commit()
    return True


# ===================================
# STRIPE / PREMIUM CRUD
# ===================================
