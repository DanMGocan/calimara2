from ._shared import *
from .economy import award_like_created, award_super_like_created
from ..achievements import emit_super_like_created
from ..week_util import end_of_month_utc, start_of_month_utc


class LikeError(Exception):
    """Base class for like errors."""


class LikeSelfError(LikeError):
    pass


def create_like(db: Session, post_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None):
    identity_filters = []
    if user_id:
        post_owner_id = db.query(models.Post.user_id).filter(models.Post.id == post_id).scalar()
        if post_owner_id == user_id:
            raise LikeSelfError()
        identity_filters.append(models.Like.user_id == user_id)
    if ip_address:
        identity_filters.append(models.Like.ip_address == ip_address)
    if not identity_filters:
        return None

    existing_like = (
        db.query(models.Like)
        .filter(models.Like.post_id == post_id, or_(*identity_filters))
        .first()
    )
    if existing_like:
        return None

    db_like = models.Like(
        post_id=post_id,
        user_id=user_id,
        ip_address=None if user_id else ip_address,
    )
    db.add(db_like)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(db_like)
    award_like_created(db, db_like)
    db.refresh(db_like)
    return db_like

def get_likes_count_for_post(db: Session, post_id: int):
    return db.query(models.Like).filter(models.Like.post_id == post_id).count()

def user_liked_post(db: Session, post_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None) -> bool:
    identity_filters = []
    if user_id:
        identity_filters.append(models.Like.user_id == user_id)
    if ip_address:
        identity_filters.append(models.Like.ip_address == ip_address)
    if not identity_filters:
        return False
    query = db.query(models.Like.id).filter(
        models.Like.post_id == post_id,
        or_(*identity_filters),
    )
    return query.first() is not None

def delete_like(db: Session, post_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None) -> bool:
    identity_filters = []
    if user_id:
        identity_filters.append(models.Like.user_id == user_id)
    if ip_address:
        identity_filters.append(models.Like.ip_address == ip_address)
    if not identity_filters:
        return False
    query = db.query(models.Like).filter(
        models.Like.post_id == post_id,
        or_(*identity_filters),
    )
    like = query.first()
    if not like:
        return False
    db.delete(like)
    db.commit()
    return True

def get_user_total_likes(db: Session, user_id: int):
    return db.query(models.Like).join(models.Post).filter(models.Post.user_id == user_id).count()

# ===================================
# FEATURED & BEST FRIENDS
# ===================================

SUPER_LIKE_MONTHLY_QUOTAS = {
    "free": 1,
    "trubadur": 3,
    "cronicar": 4,
    "rapsod": 5,
}

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

def _naive_datetime(value):
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)

def effective_super_like_tier_for_user(user: models.User) -> str:
    if not user or not user.is_premium:
        return "free"
    tier = (user.premium_tier or "trubadur").lower()
    return tier if tier in {"trubadur", "cronicar", "rapsod"} else "trubadur"

def monthly_quota_for_user(user: models.User) -> int:
    return SUPER_LIKE_MONTHLY_QUOTAS[effective_super_like_tier_for_user(user)]

def super_like_quota_period() -> tuple[datetime, datetime]:
    return start_of_month_utc(), end_of_month_utc()

def get_user_monthly_super_like_count(
    db: Session,
    user_id: int,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> int:
    start, end = period_start, period_end
    if start is None or end is None:
        start, end = super_like_quota_period()
    # SQLAlchemy stores naive datetimes on SQLite; strip tzinfo for cross-DB portability.
    month_start = _naive_datetime(start)
    month_end = _naive_datetime(end)
    return (
        db.query(models.SuperLike)
        .filter(
            models.SuperLike.user_id == user_id,
            models.SuperLike.created_at >= month_start,
            models.SuperLike.created_at < month_end,
        )
        .count()
    )

def weekly_quota_for_user(user: models.User) -> int:
    return monthly_quota_for_user(user)

def get_user_weekly_super_like_count(db: Session, user_id: int) -> int:
    return get_user_monthly_super_like_count(db, user_id)

def super_like_quota_payload(db: Session, user: models.User) -> dict:
    period_start, period_end = super_like_quota_period()
    quota = monthly_quota_for_user(user)
    used = get_user_monthly_super_like_count(db, user.id, period_start, period_end)
    return {
        "premium_tier": effective_super_like_tier_for_user(user),
        "monthly_quota": quota,
        "used_this_month": used,
        "remaining": max(0, quota - used),
        "period_start": period_start,
        "period_end": period_end,
        "month_resets_at": period_end,
        # Compatibility aliases for callers that still read the old weekly names.
        "weekly_quota": quota,
        "used_this_week": used,
        "week_resets_at": period_end,
        "is_premium": user.is_premium,
    }

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
    used = get_user_monthly_super_like_count(db, user.id)
    if used >= monthly_quota_for_user(user):
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
