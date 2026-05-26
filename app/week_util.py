from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime (no tzinfo).

    Replaces datetime.utcnow(), which is deprecated on Python 3.12+. Produces
    the same value shape so it is a drop-in replacement for use against the
    naive DateTime columns already in the schema.
    """
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def start_of_iso_week_utc() -> datetime:
    """Return the Monday 00:00:00 UTC that begins the ISO week containing _now()."""
    now = _now()
    days_since_monday = now.weekday()  # Mon=0 ... Sun=6
    monday = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday


def end_of_iso_week_utc() -> datetime:
    """Return the next Monday 00:00:00 UTC (exclusive upper bound of the current ISO week)."""
    return start_of_iso_week_utc() + timedelta(days=7)


def start_of_month_utc() -> datetime:
    """Return the first day 00:00:00 UTC of the calendar month containing _now()."""
    now = _now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def end_of_month_utc() -> datetime:
    """Return the first day 00:00:00 UTC of the next calendar month."""
    start = start_of_month_utc()
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)
