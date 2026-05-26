import calendar
import logging
from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from ._shared import *

logger = logging.getLogger(__name__)

DIACRITICS_MONTHLY_CHARACTER_QUOTAS = {
    "free": 15_000,
    "trubadur": 60_000,
    "cronicar": 120_000,
    "rapsod": 180_000,
}

DIACRITICS_USAGE_COUNTED_STATUSES = ("pending", "succeeded")
_missing_diacritics_usage_table_warned = False


def _pending_stale_minutes() -> int:
    try:
        return max(1, int(os.getenv("DIACRITICS_PENDING_STALE_MINUTES", "15")))
    except (TypeError, ValueError):
        return 15


DIACRITICS_PENDING_STALE_MINUTES = _pending_stale_minutes()


class DiacriticsQuotaExceeded(Exception):
    def __init__(self, limit: int, used: int, requested: int):
        self.limit = limit
        self.used = used
        self.requested = requested
        self.remaining = max(0, limit - used)
        super().__init__("Diacritics character quota exceeded")


class DiacriticsQuotaUnavailable(Exception):
    pass


def _diacritics_usage_table_available(db: Session) -> bool:
    global _missing_diacritics_usage_table_warned
    table_name = models.DiacriticsUsageEvent.__tablename__
    try:
        available = inspect(db.get_bind()).has_table(table_name)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not inspect database table %s", table_name)
        return False
    if not available and not _missing_diacritics_usage_table_warned:
        _missing_diacritics_usage_table_warned = True
        logger.warning(
            "%s table is missing; Diacritice quotas are unavailable until schema.sql has been applied",
            table_name,
        )
    return available


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def diacritics_quota_limit_for_user(user: models.User) -> int:
    if not user:
        return 0
    tier = user.premium_tier if user.is_premium else "free"
    return DIACRITICS_MONTHLY_CHARACTER_QUOTAS.get(
        tier or "free",
        DIACRITICS_MONTHLY_CHARACTER_QUOTAS["free"],
    )


def diacritics_quota_period_for_user(user: models.User) -> tuple[Optional[datetime], Optional[datetime]]:
    if not user:
        return None, None
    now = utcnow_naive()
    if user.is_premium and user.premium_until:
        period_end = _naive(user.premium_until)
        period_start = _naive(user.premium_period_start) if user.premium_period_start else period_end - timedelta(days=30)
        return period_start, period_end

    anchor = _naive(user.created_at) if user.created_at else now
    if now < anchor:
        return anchor, _add_months(anchor, 1)
    elapsed_months = (now.year - anchor.year) * 12 + (now.month - anchor.month)
    period_start = _add_months(anchor, elapsed_months)
    if period_start > now:
        elapsed_months -= 1
        period_start = _add_months(anchor, elapsed_months)
    return period_start, _add_months(anchor, elapsed_months + 1)


def count_diacritics_characters(value: str | None) -> int:
    text = rich_text.rich_text_to_plain_text(value)
    return len(text)


def diacritics_character_count_for_request(body) -> int:
    if body.kind == "theatre_play":
        parts = [body.title, body.description, *[item.description for item in body.characters]]
    else:
        parts = [body.title, body.content]
    return sum(count_diacritics_characters(part) for part in parts if part)


def diacritics_word_count_for_request(body) -> int:
    return diacritics_character_count_for_request(body)


def get_user_diacritics_character_usage(
    db: Session,
    user_id: int,
    period_start: datetime,
    period_end: datetime,
) -> int:
    used = (
        db.query(func.coalesce(func.sum(models.DiacriticsUsageEvent.character_count), 0))
        .filter(
            models.DiacriticsUsageEvent.user_id == user_id,
            models.DiacriticsUsageEvent.quota_period_start == period_start,
            models.DiacriticsUsageEvent.quota_period_end == period_end,
            models.DiacriticsUsageEvent.status.in_(DIACRITICS_USAGE_COUNTED_STATUSES),
        )
        .scalar()
    )
    return int(used or 0)


def expire_stale_diacritics_usage(db: Session) -> int:
    cutoff = utcnow_naive() - timedelta(minutes=DIACRITICS_PENDING_STALE_MINUTES)
    try:
        expired = (
            db.query(models.DiacriticsUsageEvent)
            .filter(
                models.DiacriticsUsageEvent.status == "pending",
                models.DiacriticsUsageEvent.created_at <= cutoff,
            )
            .update(
                {
                    models.DiacriticsUsageEvent.status: "failed",
                    models.DiacriticsUsageEvent.error_message: "Cererea Diacritice a expirat înainte de finalizare.",
                },
                synchronize_session=False,
            )
        )
        if expired:
            db.commit()
        return int(expired or 0)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not expire stale Diacritice usage events")
        return 0


def get_user_diacritics_word_usage(
    db: Session,
    user_id: int,
    period_start: datetime,
    period_end: datetime,
) -> int:
    return get_user_diacritics_character_usage(db, user_id, period_start, period_end)


def diacritics_quota_payload(db: Session, user: models.User) -> dict:
    limit = diacritics_quota_limit_for_user(user)
    period_start, period_end = diacritics_quota_period_for_user(user)
    used = 0
    table_available = _diacritics_usage_table_available(db) if user else False
    if user and period_start and period_end and table_available:
        expire_stale_diacritics_usage(db)
        used = get_user_diacritics_character_usage(db, user.id, period_start, period_end)
    return {
        "premium_tier": user.premium_tier if user and user.is_premium else "free",
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "period_start": period_start,
        "period_end": period_end,
        "can_request": bool(user and table_available and limit > 0 and period_start and period_end and used < limit),
    }


def _quota_payload_from_used(
    user: models.User,
    *,
    limit: int,
    used: int,
    period_start: datetime,
    period_end: datetime,
) -> dict:
    return {
        "premium_tier": user.premium_tier if user and user.is_premium else "free",
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "period_start": period_start,
        "period_end": period_end,
        "can_request": bool(user and limit > 0 and used < limit),
    }


def reserve_diacritics_usage(
    db: Session,
    *,
    user: models.User,
    kind: str,
    character_count: int | None = None,
    word_count: int | None = None,
) -> tuple[models.DiacriticsUsageEvent, dict]:
    if character_count is None:
        character_count = word_count or 0
    if not user:
        raise DiacriticsQuotaExceeded(limit=0, used=0, requested=character_count)
    period_start, period_end = diacritics_quota_period_for_user(user)
    limit = diacritics_quota_limit_for_user(user)
    if not period_start or not period_end or limit <= 0:
        raise DiacriticsQuotaExceeded(limit=limit, used=0, requested=character_count)
    if not _diacritics_usage_table_available(db):
        raise DiacriticsQuotaUnavailable("Diacriticele sunt indisponibile până la actualizarea bazei de date.")

    expire_stale_diacritics_usage(db)
    db.query(models.User.id).filter(models.User.id == user.id).with_for_update().one()
    used = get_user_diacritics_character_usage(db, user.id, period_start, period_end)
    if used + character_count > limit:
        raise DiacriticsQuotaExceeded(limit=limit, used=used, requested=character_count)

    event = models.DiacriticsUsageEvent(
        user_id=user.id,
        kind=kind,
        character_count=max(0, int(character_count or 0)),
        quota_period_start=period_start,
        quota_period_end=period_end,
        status="pending",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    next_used = used + event.character_count
    return event, _quota_payload_from_used(
        user,
        limit=limit,
        used=next_used,
        period_start=period_start,
        period_end=period_end,
    )


def mark_diacritics_usage_succeeded(db: Session, event: models.DiacriticsUsageEvent) -> models.DiacriticsUsageEvent:
    event.status = "succeeded"
    event.error_message = None
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def mark_diacritics_usage_failed(
    db: Session,
    event: models.DiacriticsUsageEvent,
    error_message: str | None = None,
) -> models.DiacriticsUsageEvent:
    event.status = "failed"
    event.error_message = error_message
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
