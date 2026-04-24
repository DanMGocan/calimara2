import os
import re
import time
import hashlib
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from collections import defaultdict

from fastapi import Request
from sqlalchemy import func, case, distinct, and_, cast, Date as SQLDate
from sqlalchemy.orm import Session

from . import models, crud

logger = logging.getLogger(__name__)

# Configuration from environment
STATS_ENABLED = os.getenv("STATS_ENABLED", "True").lower() == "true"
BOT_DETECTION_ENABLED = os.getenv("BOT_DETECTION_ENABLED", "True").lower() == "true"
BOT_RATE_LIMIT = int(os.getenv("BOT_RATE_LIMIT_VIEWS_PER_MINUTE", "30"))
DEDUP_WINDOW_MINUTES = int(os.getenv("STATS_DEDUP_WINDOW_MINUTES", "30"))

# Known bot user-agent patterns
BOT_PATTERNS = re.compile(
    r'(googlebot|bingbot|yandexbot|baiduspider|duckduckbot|'
    r'slurp|msnbot|crawl|spider|bot[/\s;)]|scraper|'
    r'facebookexternalhit|twitterbot|linkedinbot|'
    r'whatsapp|telegrambot|discordbot|'
    r'headlesschrome|phantomjs|selenium|puppeteer|playwright|'
    r'python-requests|python-urllib|httpx|aiohttp|'
    r'curl/|wget/|libwww|java/|go-http-client|'
    r'applebot|ahrefsbot|semrushbot|dotbot|mj12bot|'
    r'petalbot|bytespider|gptbot|claudebot|ccbot|'
    r'dataforseo|zoominfobot|blexbot)',
    re.IGNORECASE
)

# In-memory rate tracking (IP -> list of timestamps)
_rate_tracker: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60  # seconds


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _get_session_fingerprint(request: Request) -> Optional[str]:
    session_cookie = request.cookies.get("session")
    if session_cookie:
        return hashlib.sha256(session_cookie.encode()).hexdigest()[:32]
    return None


def detect_bot(user_agent: str, ip_address: str) -> tuple[bool, Optional[str]]:
    if not BOT_DETECTION_ENABLED:
        return False, None

    # Layer 1: Known bot patterns
    if not user_agent or len(user_agent) < 10:
        return True, "missing_ua"

    if BOT_PATTERNS.search(user_agent):
        return True, "known_crawler"

    # Layer 2: Rate-based detection
    now = time.time()
    cutoff = now - _RATE_WINDOW
    timestamps = _rate_tracker.get(ip_address, [])
    active = [t for t in timestamps if t > cutoff]
    active.append(now)
    _rate_tracker[ip_address] = active

    if len(active) > BOT_RATE_LIMIT:
        return True, "rate_exceeded"

    # Periodic cleanup: remove stale IPs every ~100 checks
    if len(_rate_tracker) > 1000:
        stale_ips = [ip for ip, ts in _rate_tracker.items() if not ts or ts[-1] < cutoff]
        for ip in stale_ips:
            del _rate_tracker[ip]

    return False, None


def detect_device_type(user_agent: str) -> str:
    if not user_agent:
        return "unknown"
    ua = user_agent.lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobile" in ua or ("android" in ua and "tablet" not in ua):
        return "mobile"
    return "desktop"


def _check_duplicate(
    db: Session,
    ip_address: str,
    content_type: str,
    content_id: Optional[int],
) -> bool:
    window_start = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MINUTES)
    query = db.query(models.PageView.id).filter(
        models.PageView.ip_address == ip_address,
        models.PageView.content_type == content_type,
        models.PageView.content_id == content_id,
        models.PageView.created_at > window_start,
        models.PageView.is_duplicate == False,
    ).limit(1)
    return query.first() is not None


def record_view(
    db: Session,
    request: Request,
    content_type: str,
    content_id: Optional[int],
    content_key: Optional[str],
    content_owner_id: Optional[int],
    current_user: Optional[models.User],
) -> Optional[models.PageView]:
    if not STATS_ENABLED:
        return None

    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer")
    session_id = _get_session_fingerprint(request)
    user_id = current_user.id if current_user else None

    is_bot, bot_reason = detect_bot(user_agent, ip_address)
    device_type = detect_device_type(user_agent) if not is_bot else "unknown"
    is_duplicate = False

    if not is_bot:
        is_duplicate = _check_duplicate(db, ip_address, content_type, content_id)

    page_view = models.PageView(
        content_type=content_type,
        content_id=content_id,
        content_key=content_key,
        user_id=user_id,
        ip_address=ip_address,
        session_id=session_id,
        user_agent=user_agent[:2000] if user_agent else None,
        is_bot=is_bot,
        bot_reason=bot_reason,
        device_type=device_type,
        referrer_url=referrer[:2000] if referrer else None,
        is_duplicate=is_duplicate,
        content_owner_id=content_owner_id,
    )
    db.add(page_view)

    # Only increment denormalized view_count for real, unique views
    if not is_bot and not is_duplicate:
        if content_type == "post" and content_id:
            db.query(models.Post).filter(models.Post.id == content_id).update(
                {models.Post.view_count: models.Post.view_count + 1},
                synchronize_session="fetch"
            )

    db.commit()
    return page_view


# ===================================
# QUERY FUNCTIONS
# ===================================

def _real_views_filter():
    """Common filter for non-bot, non-duplicate views."""
    return and_(
        models.PageView.is_bot == False,
        models.PageView.is_duplicate == False,
    )


def _date_filter(from_date: Optional[date] = None, to_date: Optional[date] = None):
    """Build date range filters."""
    filters = []
    if from_date:
        filters.append(models.PageView.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        filters.append(models.PageView.created_at < datetime.combine(to_date + timedelta(days=1), datetime.min.time()))
    return filters


def _views_by_day(db: Session, base_filters: list, from_date: Optional[date] = None, to_date: Optional[date] = None) -> list[dict]:
    """Get daily view counts for a set of filters."""
    date_filters = _date_filter(from_date, to_date)
    rows = db.query(
        cast(models.PageView.created_at, SQLDate).label("day"),
        func.count().label("total"),
        func.count().filter(_real_views_filter()).label("real"),
    ).filter(
        *base_filters,
        *date_filters,
    ).group_by("day").order_by("day").all()

    return [{"date": str(r.day), "total": r.total, "real": r.real} for r in rows]


def _device_breakdown(db: Session, base_filters: list, date_filters: list) -> dict:
    rows = db.query(
        models.PageView.device_type,
        func.count().label("count"),
    ).filter(
        *base_filters,
        *date_filters,
        _real_views_filter(),
    ).group_by(models.PageView.device_type).all()
    return {r.device_type or "unknown": r.count for r in rows}


def _visitor_breakdown(db: Session, base_filters: list, date_filters: list) -> dict:
    row = db.query(
        func.count().filter(models.PageView.user_id != None).label("logged_in"),
        func.count().filter(models.PageView.user_id == None).label("anonymous"),
    ).filter(
        *base_filters,
        *date_filters,
        _real_views_filter(),
    ).first()
    return {"logged_in": row.logged_in, "anonymous": row.anonymous}


def get_post_stats(
    db: Session, post_id: int,
    from_date: Optional[date] = None, to_date: Optional[date] = None,
) -> dict:
    base = [models.PageView.content_type == "post", models.PageView.content_id == post_id]
    date_f = _date_filter(from_date, to_date)

    total = db.query(func.count()).filter(*base, *date_f).scalar()
    unique = db.query(func.count()).filter(*base, *date_f, _real_views_filter()).scalar()
    bot_count = db.query(func.count()).filter(*base, *date_f, models.PageView.is_bot == True).scalar()

    top_referrers = db.query(
        models.PageView.referrer_url,
        func.count().label("count"),
    ).filter(
        *base, *date_f, _real_views_filter(),
        models.PageView.referrer_url != None,
    ).group_by(models.PageView.referrer_url).order_by(func.count().desc()).limit(10).all()

    return {
        "total_views": total,
        "unique_views": unique,
        "bot_views": bot_count,
        "views_by_day": _views_by_day(db, base, from_date, to_date),
        "devices": _device_breakdown(db, base, date_f),
        "visitors": _visitor_breakdown(db, base, date_f),
        "top_referrers": [{"url": r.referrer_url, "count": r.count} for r in top_referrers],
    }


def get_author_stats(
    db: Session, user_id: int,
    from_date: Optional[date] = None, to_date: Optional[date] = None,
) -> dict:
    base = [models.PageView.content_owner_id == user_id]
    date_f = _date_filter(from_date, to_date)

    total = db.query(func.count()).filter(*base, *date_f).scalar()
    unique = db.query(func.count()).filter(*base, *date_f, _real_views_filter()).scalar()
    bot_count = db.query(func.count()).filter(*base, *date_f, models.PageView.is_bot == True).scalar()

    # Top posts
    top_posts = db.query(
        models.PageView.content_id,
        models.PageView.content_key,
        func.count().label("views"),
    ).filter(
        *base, *date_f, _real_views_filter(),
        models.PageView.content_type == "post",
    ).group_by(
        models.PageView.content_id, models.PageView.content_key,
    ).order_by(func.count().desc()).limit(10).all()

    # Category breakdown
    category_stats = db.query(
        models.Post.category,
        func.count(models.PageView.id).label("views"),
    ).join(
        models.Post,
        and_(models.PageView.content_type == "post", models.PageView.content_id == models.Post.id),
    ).filter(
        *base, *date_f, _real_views_filter(),
    ).group_by(models.Post.category).order_by(func.count(models.PageView.id).desc()).all()

    # Engagement: total likes and comments
    total_likes = crud.get_user_total_likes(db, user_id)
    total_comments = crud.get_user_total_comments(db, user_id)

    return {
        "total_views": total,
        "unique_views": unique,
        "bot_views": bot_count,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "views_by_day": _views_by_day(db, base, from_date, to_date),
        "top_posts": [{"id": r.content_id, "slug": r.content_key, "views": r.views} for r in top_posts],
        "category_breakdown": [{"category": r.category, "views": r.views} for r in category_stats],
        "devices": _device_breakdown(db, base, date_f),
        "visitors": _visitor_breakdown(db, base, date_f),
    }


def get_category_stats(
    db: Session, category_key: str,
    from_date: Optional[date] = None, to_date: Optional[date] = None,
) -> dict:
    # Get views for posts in this category via join
    date_f = _date_filter(from_date, to_date)

    query_base = db.query(func.count(models.PageView.id)).join(
        models.Post,
        and_(models.PageView.content_type == "post", models.PageView.content_id == models.Post.id),
    ).filter(models.Post.category == category_key, *date_f)

    total = query_base.scalar()
    unique = query_base.filter(_real_views_filter()).scalar()

    # Also include direct category page views
    cat_page_base = [models.PageView.content_type == "category", models.PageView.content_key == category_key]
    cat_page_views = db.query(func.count()).filter(*cat_page_base, *date_f, _real_views_filter()).scalar()

    # Top posts in category
    top_posts = db.query(
        models.PageView.content_id,
        models.PageView.content_key,
        func.count().label("views"),
    ).join(
        models.Post,
        and_(models.PageView.content_type == "post", models.PageView.content_id == models.Post.id),
    ).filter(
        models.Post.category == category_key,
        *date_f, _real_views_filter(),
    ).group_by(
        models.PageView.content_id, models.PageView.content_key,
    ).order_by(func.count().desc()).limit(10).all()

    return {
        "category": category_key,
        "total_post_views": total,
        "unique_post_views": unique,
        "category_page_views": cat_page_views,
        "top_posts": [{"id": r.content_id, "slug": r.content_key, "views": r.views} for r in top_posts],
    }


def get_overview_stats(
    db: Session,
    from_date: Optional[date] = None, to_date: Optional[date] = None,
) -> dict:
    date_f = _date_filter(from_date, to_date)

    total = db.query(func.count()).select_from(models.PageView).filter(*date_f).scalar()
    unique = db.query(func.count()).select_from(models.PageView).filter(*date_f, _real_views_filter()).scalar()
    bot_count = db.query(func.count()).select_from(models.PageView).filter(*date_f, models.PageView.is_bot == True).scalar()

    # Top authors by views
    top_authors = db.query(
        models.PageView.content_owner_id,
        func.count().label("views"),
    ).filter(
        *date_f, _real_views_filter(),
        models.PageView.content_owner_id != None,
    ).group_by(models.PageView.content_owner_id).order_by(func.count().desc()).limit(10).all()

    # Enrich with usernames
    author_ids = [a.content_owner_id for a in top_authors]
    users_map = {}
    if author_ids:
        users = db.query(models.User).filter(models.User.id.in_(author_ids)).all()
        users_map = {u.id: u.username for u in users}

    # Top posts
    top_posts = db.query(
        models.PageView.content_id,
        models.PageView.content_key,
        models.PageView.content_owner_id,
        func.count().label("views"),
    ).filter(
        *date_f, _real_views_filter(),
        models.PageView.content_type == "post",
    ).group_by(
        models.PageView.content_id, models.PageView.content_key, models.PageView.content_owner_id,
    ).order_by(func.count().desc()).limit(10).all()

    # Views by content type
    type_breakdown = db.query(
        models.PageView.content_type,
        func.count().label("views"),
    ).filter(*date_f, _real_views_filter()).group_by(
        models.PageView.content_type,
    ).all()

    return {
        "total_views": total,
        "unique_views": unique,
        "bot_views": bot_count,
        "bot_percentage": round((bot_count / total * 100), 1) if total > 0 else 0,
        "views_by_day": _views_by_day(db, [], from_date, to_date),
        "top_authors": [
            {"user_id": a.content_owner_id, "username": users_map.get(a.content_owner_id, "unknown"), "views": a.views}
            for a in top_authors
        ],
        "top_posts": [
            {"id": r.content_id, "slug": r.content_key, "owner_id": r.content_owner_id, "views": r.views}
            for r in top_posts
        ],
        "content_type_breakdown": {r.content_type: r.views for r in type_breakdown},
        "devices": _device_breakdown(db, [], date_f),
        "visitors": _visitor_breakdown(db, [], date_f),
    }


def get_my_stats(
    db: Session, user_id: int,
    from_date: Optional[date] = None, to_date: Optional[date] = None,
) -> dict:
    stats = get_author_stats(db, user_id, from_date, to_date)

    # Per-post breakdown with titles
    date_f = _date_filter(from_date, to_date)
    post_views = db.query(
        models.PageView.content_id,
        func.count().label("views"),
    ).filter(
        models.PageView.content_owner_id == user_id,
        models.PageView.content_type == "post",
        *date_f, _real_views_filter(),
    ).group_by(models.PageView.content_id).all()

    post_ids = [pv.content_id for pv in post_views]
    posts_map = {}
    if post_ids:
        posts = db.query(models.Post).filter(models.Post.id.in_(post_ids)).all()
        posts_map = {p.id: {"title": p.title, "slug": p.slug, "likes": p.likes_count} for p in posts}

    stats["posts_detail"] = [
        {
            "id": pv.content_id,
            "views": pv.views,
            "title": posts_map.get(pv.content_id, {}).get("title", ""),
            "slug": posts_map.get(pv.content_id, {}).get("slug", ""),
            "likes": posts_map.get(pv.content_id, {}).get("likes", 0),
        }
        for pv in sorted(post_views, key=lambda x: x.views, reverse=True)
    ]

    # Blog page views
    blog_views = db.query(func.count()).select_from(models.PageView).filter(
        models.PageView.content_type == "blog",
        models.PageView.content_owner_id == user_id,
        *date_f, _real_views_filter(),
    ).scalar()
    stats["blog_page_views"] = blog_views

    return stats


def aggregate_daily_stats(db: Session, target_date: date) -> None:
    """Roll up page_views for a given date into daily_stats."""
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)

    rows = db.query(
        models.PageView.content_type,
        models.PageView.content_id,
        models.PageView.content_key,
        models.PageView.content_owner_id,
        func.count().label("total_views"),
        func.count().filter(_real_views_filter()).label("unique_views"),
        func.count().filter(models.PageView.is_bot == True).label("bot_views"),
        func.count().filter(and_(_real_views_filter(), models.PageView.user_id != None)).label("logged_in_views"),
        func.count().filter(and_(_real_views_filter(), models.PageView.user_id == None)).label("anonymous_views"),
        func.count().filter(and_(_real_views_filter(), models.PageView.device_type == "desktop")).label("desktop_views"),
        func.count().filter(and_(_real_views_filter(), models.PageView.device_type == "mobile")).label("mobile_views"),
        func.count().filter(and_(_real_views_filter(), models.PageView.device_type == "tablet")).label("tablet_views"),
    ).filter(
        models.PageView.created_at >= start,
        models.PageView.created_at < end,
    ).group_by(
        models.PageView.content_type,
        models.PageView.content_id,
        models.PageView.content_key,
        models.PageView.content_owner_id,
    ).all()

    for r in rows:
        existing = db.query(models.DailyStat).filter(
            models.DailyStat.stat_date == target_date,
            models.DailyStat.content_type == r.content_type,
            models.DailyStat.content_key == r.content_key,
        ).first()

        if existing:
            existing.total_views = r.total_views
            existing.unique_views = r.unique_views
            existing.bot_views = r.bot_views
            existing.logged_in_views = r.logged_in_views
            existing.anonymous_views = r.anonymous_views
            existing.desktop_views = r.desktop_views
            existing.mobile_views = r.mobile_views
            existing.tablet_views = r.tablet_views
        else:
            db.add(models.DailyStat(
                stat_date=target_date,
                content_type=r.content_type,
                content_id=r.content_id,
                content_key=r.content_key,
                content_owner_id=r.content_owner_id,
                total_views=r.total_views,
                unique_views=r.unique_views,
                bot_views=r.bot_views,
                logged_in_views=r.logged_in_views,
                anonymous_views=r.anonymous_views,
                desktop_views=r.desktop_views,
                mobile_views=r.mobile_views,
                tablet_views=r.tablet_views,
            ))

    db.commit()
