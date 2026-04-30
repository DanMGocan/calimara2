import logging
import os
import re
from datetime import datetime, date as date_type, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, desc, extract, case
from sqlalchemy.exc import IntegrityError
from . import models, schemas
from .week_util import utcnow_naive

logger = logging.getLogger(__name__)

AUDIO_TTS_MONTHLY_QUOTAS = {
    "audio": 100_000,
    "author_audio": 250_000,
}

# ===================================
# USER CRUD FUNCTIONS
# ===================================

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_google_id(db: Session, google_id: str):
    return db.query(models.User).filter(models.User.google_id == google_id).first()

def create_user_from_google(db: Session, user_data: Dict[str, Any]):
    db_user = models.User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: Dict[str, Any]):
    db.query(models.User).filter(models.User.id == user_id).update(user_update)
    db.commit()
    return get_user_by_id(db, user_id)

def get_random_users(db: Session, limit: int = 10):
    return db.query(models.User).order_by(func.random()).limit(limit).all()

def get_random_user_with_posts(db: Session):
    # Postgres rejects `SELECT DISTINCT ... ORDER BY random()` because the
    # ORDER BY expression isn't in the SELECT list. Use EXISTS instead of
    # DISTINCT+JOIN so we can order by random() freely.
    return (
        db.query(models.User)
        .filter(
            db.query(models.Post.id)
            .filter(
                models.Post.user_id == models.User.id,
                models.Post.moderation_status == "approved",
            )
            .exists()
        )
        .order_by(func.random())
        .limit(1)
        .first()
    )

# ===================================
# POST CRUD FUNCTIONS
# ===================================

def generate_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    return slug

def ensure_unique_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while db.query(models.Post).filter(models.Post.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

def get_post(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_post_by_slug(db: Session, slug: str):
    return db.query(models.Post).filter(models.Post.slug == slug).first()

def get_posts(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Post).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_posts_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def create_user_post(db: Session, post: schemas.PostCreate, user_id: int, category: str = "proza_scurta"):
    base_slug = generate_slug(post.title)
    slug = ensure_unique_slug(db, base_slug)
    
    db_post = models.Post(
        **post.model_dump(exclude={"ai_critic"}),
        user_id=user_id,
        slug=slug,
        category=category,
        ai_critic_requested=post.ai_critic,
        moderation_status="pending"
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    return db_post

def update_post(db: Session, post_id: int, post_update: schemas.PostUpdate, category: Optional[str] = None):
    db_post = get_post(db, post_id)
    if not db_post:
        return None
    
    update_data = post_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_post, key, value)
    
    if category:
        db_post.category = category
        
    db_post.moderation_status = "pending"
    db_post.theme_analysis_status = "pending"
    db_post.themes = []
    db_post.feelings = []
    db_post.ai_critic_requested = False
    db.query(models.PostAudio).filter(models.PostAudio.post_id == post_id).update(
        {
            "status": "rejected",
            "moderation_status": "rejected",
            "moderation_reason": "Postarea a fost editată după crearea acestui audio",
        }
    )
    db.commit()
    db.refresh(db_post)
    return db_post

def delete_post(db: Session, post_id: int):
    db_post = get_post(db, post_id)
    if db_post:
        db.delete(db_post)
        db.commit()
    return db_post

def update_post_theme_analysis(db: Session, post_id: int, themes: list, feelings: list, status: str):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post:
        post.themes = themes
        post.feelings = feelings
        post.theme_analysis_status = status
        db.commit()

def get_platform_stats(db: Session):
    try:
        total_posts = db.query(func.count(models.Post.id)).filter(
            models.Post.moderation_status == "approved"
        ).scalar() or 0
        total_authors = db.query(func.count(func.distinct(models.Post.user_id))).filter(
            models.Post.moderation_status == "approved",
            models.Post.user_id.isnot(None),
        ).scalar() or 0
    except Exception:
        logger.exception("Failed to load platform stats")
        db.rollback()
        return {"total_posts": 0, "total_authors": 0}
    return {"total_posts": total_posts, "total_authors": total_authors}

def get_random_posts(db: Session, limit: int = 10):
    return db.query(models.Post).filter(models.Post.moderation_status == "approved").order_by(func.random()).limit(limit).all()

def get_random_posts_by_category(db: Session, category: str, limit: int = 10):
    return db.query(models.Post).filter(
        models.Post.category == category,
        models.Post.moderation_status == "approved"
    ).order_by(func.random()).limit(limit).all()


def get_best_audio_for_post(db: Session, post_id: int) -> Optional[models.PostAudio]:
    author_audio = (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "author",
            models.PostAudio.status == "ready",
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )
    if author_audio:
        return author_audio
    return (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "tts",
            models.PostAudio.status == "ready",
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )


def get_latest_audio_for_post(db: Session, post_id: int) -> Optional[models.PostAudio]:
    return (
        db.query(models.PostAudio)
        .filter(models.PostAudio.post_id == post_id)
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )


def create_post_audio(
    db: Session,
    post_id: int,
    source: str,
    status: str = "pending",
    **fields,
) -> models.PostAudio:
    audio = models.PostAudio(post_id=post_id, source=source, status=status, **fields)
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return audio


def update_post_audio(db: Session, audio_id: int, **fields) -> Optional[models.PostAudio]:
    audio = db.query(models.PostAudio).filter(models.PostAudio.id == audio_id).first()
    if not audio:
        return None
    for key, value in fields.items():
        setattr(audio, key, value)
    db.commit()
    db.refresh(audio)
    return audio


def get_pending_tts_audio_jobs(db: Session, limit: int = 10) -> List[models.PostAudio]:
    return (
        db.query(models.PostAudio)
        .join(models.Post)
        .filter(
            models.PostAudio.source == "tts",
            models.PostAudio.status == "pending",
            models.PostAudio.requester_user_id.isnot(None),
            models.Post.moderation_status == "approved",
        )
        .order_by(models.PostAudio.created_at.asc(), models.PostAudio.id.asc())
        .limit(limit)
        .all()
    )


def get_active_or_ready_tts_for_post(db: Session, post_id: int) -> Optional[models.PostAudio]:
    return (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "tts",
            or_(
                models.PostAudio.status == "ready",
                and_(
                    models.PostAudio.status.in_(["pending", "processing"]),
                    models.PostAudio.requester_user_id.isnot(None),
                ),
            ),
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )


def cancel_legacy_pending_tts_for_post(db: Session, post_id: int) -> int:
    updated = (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "tts",
            models.PostAudio.requester_user_id.is_(None),
            models.PostAudio.status.in_(["pending", "processing"]),
        )
        .update(
            {
                "status": "cancelled",
                "moderation_status": "cancelled",
                "moderation_reason": "Automatic TTS generation was disabled",
            },
            synchronize_session=False,
        )
    )
    if updated:
        db.commit()
    return updated


def enqueue_tts_audio_for_post(db: Session, post: models.Post) -> Optional[models.PostAudio]:
    if post.moderation_status != "approved":
        return None
    existing = (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post.id,
            models.PostAudio.source == "tts",
            models.PostAudio.status.in_(["pending", "processing", "ready"]),
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )
    if existing:
        return existing
    return create_post_audio(db, post_id=post.id, source="tts", status="pending")


def audio_tts_quota_limit_for_user(user: models.User) -> int:
    if not user or not user.is_premium:
        return 0
    return AUDIO_TTS_MONTHLY_QUOTAS.get(user.premium_tier, 0)


def audio_tts_quota_period_for_user(user: models.User) -> tuple[Optional[datetime], Optional[datetime]]:
    if not user or not user.is_premium or not user.premium_until:
        return None, None
    period_end = user.premium_until
    period_start = user.premium_period_start or (period_end - timedelta(days=30))
    return period_start, period_end


def get_user_audio_tts_character_usage(
    db: Session,
    user_id: int,
    period_start: datetime,
    period_end: datetime,
) -> int:
    used = (
        db.query(func.coalesce(func.sum(models.PostAudio.tts_character_count), 0))
        .filter(
            models.PostAudio.source == "tts",
            models.PostAudio.requester_user_id == user_id,
            models.PostAudio.quota_period_start == period_start,
            models.PostAudio.quota_period_end == period_end,
            models.PostAudio.status.in_(["pending", "processing", "ready"]),
        )
        .scalar()
    )
    return int(used or 0)


def create_tts_audio_request(
    db: Session,
    *,
    post_id: int,
    requester_user_id: int,
    tts_character_count: int,
    quota_period_start: datetime,
    quota_period_end: datetime,
) -> models.PostAudio:
    return create_post_audio(
        db,
        post_id=post_id,
        requester_user_id=requester_user_id,
        source="tts",
        status="pending",
        tts_character_count=tts_character_count,
        quota_period_start=quota_period_start,
        quota_period_end=quota_period_end,
    )


AI_JOB_ACTIVE_STATUSES = ("pending", "processing")


def enqueue_ai_job(
    db: Session,
    *,
    job_type: str,
    target_type: str,
    target_id: int,
    payload: Optional[dict] = None,
    max_attempts: int = 3,
    dedupe: bool = True,
) -> models.AIJob:
    if dedupe:
        existing = (
            db.query(models.AIJob)
            .filter(
                models.AIJob.job_type == job_type,
                models.AIJob.target_type == target_type,
                models.AIJob.target_id == target_id,
                models.AIJob.status.in_(AI_JOB_ACTIVE_STATUSES),
            )
            .order_by(models.AIJob.id.desc())
            .first()
        )
        if existing:
            return existing
    job = models.AIJob(
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
        max_attempts=max_attempts,
        status="pending",
        run_after=utcnow_naive(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_pending_ai_jobs(
    db: Session,
    *,
    limit: int = 10,
    worker_id: Optional[str] = None,
) -> List[models.AIJob]:
    now = utcnow_naive()
    query = (
        db.query(models.AIJob)
        .filter(
            models.AIJob.status == "pending",
            models.AIJob.run_after <= now,
        )
        .order_by(models.AIJob.run_after.asc(), models.AIJob.id.asc())
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    jobs = query.limit(max(1, limit)).all()
    for job in jobs:
        job.status = "processing"
        job.locked_at = now
        job.locked_by = worker_id
        job.attempts = int(job.attempts or 0) + 1
        job.error_message = None
    if jobs:
        db.commit()
        for job in jobs:
            db.refresh(job)
    return jobs


def complete_ai_job(db: Session, job: models.AIJob) -> models.AIJob:
    job.status = "completed"
    job.locked_at = None
    job.locked_by = None
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def fail_ai_job(
    db: Session,
    job: models.AIJob,
    error_message: str,
    *,
    retry: bool = True,
) -> models.AIJob:
    message = error_message[:2000] if error_message else "AI job failed"
    if retry and int(job.attempts or 0) < int(job.max_attempts or 1):
        delay_seconds = min(300, 10 * (2 ** max(0, int(job.attempts or 1) - 1)))
        job.status = "pending"
        job.run_after = utcnow_naive() + timedelta(seconds=delay_seconds)
    else:
        job.status = "failed"
    job.locked_at = None
    job.locked_by = None
    job.error_message = message
    db.commit()
    db.refresh(job)
    return job


def get_random_ready_audio(
    db: Session, category: Optional[str] = None
) -> Optional[models.PostAudio]:
    query = (
        db.query(models.PostAudio)
        .join(models.Post)
        .filter(
            models.PostAudio.status == "ready",
            models.Post.moderation_status == "approved",
        )
    )
    if category:
        query = query.filter(models.Post.category == category)
    return query.order_by(func.random()).first()

def _view_weighted_order_key():
    # Efraimidis–Spirakis weighted random: LN(RANDOM()) is always negative,
    # so multiplying by the positive weight POWER(view_count + 1, alpha)
    # and sorting DESC picks the row with the smallest |LN(R)| / weight —
    # i.e. sampling probability ∝ 1 / (view_count + 1)^alpha.
    alpha = float(os.getenv("LANDING_VIEW_DECAY_ALPHA", "0.5"))
    if alpha == 0:
        return None
    return func.ln(func.random()) * func.power(models.Post.view_count + 1, alpha)

def get_weighted_random_posts(db: Session, limit: int = 10):
    if os.getenv("LANDING_WEIGHTED_RANDOM_ENABLED", "True").lower() != "true":
        return get_random_posts(db, limit=limit)
    order_key = _view_weighted_order_key()
    if order_key is None:
        return get_random_posts(db, limit=limit)
    return db.query(models.Post).filter(
        models.Post.moderation_status == "approved"
    ).order_by(desc(order_key)).limit(limit).all()

def get_weighted_random_posts_by_category(db: Session, category: str, limit: int = 10):
    if os.getenv("LANDING_WEIGHTED_RANDOM_ENABLED", "True").lower() != "true":
        return get_random_posts_by_category(db, category, limit=limit)
    order_key = _view_weighted_order_key()
    if order_key is None:
        return get_random_posts_by_category(db, category, limit=limit)
    return db.query(models.Post).filter(
        models.Post.category == category,
        models.Post.moderation_status == "approved"
    ).order_by(desc(order_key)).limit(limit).all()

def get_latest_posts_for_user(db: Session, user_id: int, limit: int = 5, include_unapproved: bool = False):
    query = db.query(models.Post).filter(models.Post.user_id == user_id)
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")
    return query.order_by(models.Post.created_at.desc()).limit(limit).all()

def get_posts_by_month_year(
    db: Session,
    user_id: int,
    month: int,
    year: int,
    limit: int = 50,
    include_unapproved: bool = False,
):
    query = db.query(models.Post).filter(
        models.Post.user_id == user_id,
        extract('month', models.Post.created_at) == month,
        extract('year', models.Post.created_at) == year
    )
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")
    return query.order_by(models.Post.created_at.desc()).limit(limit).all()

def get_available_months_for_user(db: Session, user_id: int, include_unapproved: bool = False):
    query = db.query(
        extract('month', models.Post.created_at).label('month'),
        extract('year', models.Post.created_at).label('year'),
        func.count(models.Post.id).label('post_count')
    ).filter(
        models.Post.user_id == user_id,
    )
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")

    results = query.group_by('year', 'month').order_by(desc('year'), desc('month')).all()
    
    return [{"month": int(r.month), "year": int(r.year), "post_count": r.post_count} for r in results]

def get_posts_by_category_sorted(db: Session, category: str, sort_by: str = "newest", limit: int = 20):
    query = db.query(models.Post).filter(
        models.Post.category == category,
        models.Post.moderation_status == "approved"
    )
    
    if sort_by == "newest":
        query = query.order_by(models.Post.created_at.desc())
    elif sort_by == "oldest":
        query = query.order_by(models.Post.created_at.asc())
    elif sort_by == "popular":
        query = query.order_by(models.Post.view_count.desc())
        
    return query.limit(limit).all()

def get_distinct_categories_used(db: Session, user_id: Optional[int] = None):
    query = db.query(models.Post.category).filter(models.Post.moderation_status == "approved")
    if user_id:
        query = query.filter(models.Post.user_id == user_id)
    results = query.distinct().all()
    return [r[0] for r in results if r[0]]

def get_user_post_counts_by_category(db: Session, user_id: int):
    rows = db.query(
        models.Post.category,
        func.count(models.Post.id),
    ).filter(
        models.Post.user_id == user_id,
        models.Post.moderation_status == "approved",
    ).group_by(models.Post.category).all()
    return {category: count for category, count in rows if category}

def _get_distinct_post_terms(db: Session, field_name: str) -> List[str]:
    posts = db.query(models.Post).filter(
        models.Post.moderation_status == "approved",
        models.Post.theme_analysis_status == "completed",
    ).all()
    terms = set()
    for post in posts:
        values = getattr(post, field_name, None) or []
        for value in values:
            if isinstance(value, str) and value.strip():
                terms.add(value.strip().lower())
    return sorted(terms)

def get_distinct_themes(db: Session):
    return _get_distinct_post_terms(db, "themes")

def get_distinct_feelings(db: Session):
    return _get_distinct_post_terms(db, "feelings")

# ===================================
# COMMENT CRUD FUNCTIONS
# ===================================

def create_comment(db: Session, comment: schemas.CommentCreate, post_id: int, user_id: Optional[int] = None):
    db_comment = models.Comment(
        post_id=post_id,
        user_id=user_id,
        author_name=comment.author_name,
        author_email=comment.author_email,
        content=comment.content,
        approved=False,
        moderation_status="pending"
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


def create_robot_comment(db: Session, post_id: int, content: str):
    db_comment = models.Comment(
        post_id=post_id,
        user_id=None,
        author_name="Robotul Călimara",
        author_email=None,
        content=content,
        approved=True,
        is_robot=True,
        moderation_status="approved",
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

def get_comments_for_post(db: Session, post_id: int, approved_only: bool = True):
    query = db.query(models.Comment).filter(models.Comment.post_id == post_id)
    if approved_only:
        query = query.filter(models.Comment.approved == True)
    return query.order_by(models.Comment.created_at.desc()).all()

def approve_comment(db: Session, comment_id: int):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment:
        was_approved = comment.moderation_status == "approved"
        comment.approved = True
        comment.moderation_status = "approved"
        db.commit()
        db.refresh(comment)
        if not was_approved:
            award_content_approved(db, "comment", comment)
    return comment

def delete_comment(db: Session, comment_id: int):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment:
        db.delete(comment)
        db.commit()
    return comment

def get_user_total_comments(db: Session, user_id: int):
    return db.query(models.Comment).join(models.Post).filter(models.Post.user_id == user_id).count()

# ===================================
# MODERATION CRUD FUNCTIONS
# ===================================

def get_posts_for_moderation(db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50):
    query = db.query(models.Post)
    if status_filter:
        query = query.filter(models.Post.moderation_status == status_filter)
    return query.order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_comments_for_moderation(db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50):
    query = db.query(models.Comment)
    if status_filter:
        query = query.filter(models.Comment.moderation_status == status_filter)
    return query.order_by(models.Comment.created_at.desc()).offset(skip).limit(limit).all()

def get_moderation_stats(db: Session):
    stats = {}
    stats['posts_pending'] = db.query(models.Post).filter(models.Post.moderation_status == "pending").count()
    stats['posts_flagged'] = db.query(models.Post).filter(models.Post.moderation_status == "flagged").count()
    stats['posts_rejected'] = db.query(models.Post).filter(models.Post.moderation_status == "rejected").count()
    stats['posts_approved'] = db.query(models.Post).filter(models.Post.moderation_status == "approved").count()
    
    stats['comments_pending'] = db.query(models.Comment).filter(models.Comment.moderation_status == "pending").count()
    stats['comments_flagged'] = db.query(models.Comment).filter(models.Comment.moderation_status == "flagged").count()
    stats['comments_rejected'] = db.query(models.Comment).filter(models.Comment.moderation_status == "rejected").count()
    stats['comments_approved'] = db.query(models.Comment).filter(models.Comment.moderation_status == "approved").count()
    
    stats['forum_threads_pending'] = db.query(models.ForumThread).filter(models.ForumThread.moderation_status == "pending").count()
    stats['forum_threads_flagged'] = db.query(models.ForumThread).filter(models.ForumThread.moderation_status == "flagged").count()
    stats['forum_threads_rejected'] = db.query(models.ForumThread).filter(models.ForumThread.moderation_status == "rejected").count()
    stats['forum_threads_approved'] = db.query(models.ForumThread).filter(models.ForumThread.moderation_status == "approved").count()
    stats['forum_replies_pending'] = db.query(models.ForumReply).filter(models.ForumReply.moderation_status == "pending").count()
    stats['forum_replies_flagged'] = db.query(models.ForumReply).filter(models.ForumReply.moderation_status == "flagged").count()
    stats['forum_replies_rejected'] = db.query(models.ForumReply).filter(models.ForumReply.moderation_status == "rejected").count()
    stats['forum_replies_approved'] = db.query(models.ForumReply).filter(models.ForumReply.moderation_status == "approved").count()

    stats['total_pending'] = (
        stats['posts_pending'] + stats['comments_pending'] +
        stats['forum_threads_pending'] + stats['forum_replies_pending']
    )
    stats['total_flagged'] = (
        stats['posts_flagged'] + stats['comments_flagged'] +
        stats['forum_threads_flagged'] + stats['forum_replies_flagged']
    )
    stats['total_rejected'] = (
        stats['posts_rejected'] + stats['comments_rejected'] +
        stats['forum_threads_rejected'] + stats['forum_replies_rejected']
    )
    return stats

def approve_content(db: Session, content_type: str, content_id: int, moderator_id: int, reason: str = ""):
    if content_type == "post":
        content = db.query(models.Post).filter(models.Post.id == content_id).first()
    elif content_type == "audio":
        content = db.query(models.PostAudio).filter(models.PostAudio.id == content_id).first()
    elif content_type == "forum_thread":
        content = db.query(models.ForumThread).filter(models.ForumThread.id == content_id).first()
    elif content_type == "forum_reply":
        content = db.query(models.ForumReply).options(
            joinedload(models.ForumReply.thread),
            joinedload(models.ForumReply.author),
        ).filter(models.ForumReply.id == content_id).first()
    else:
        content = db.query(models.Comment).filter(models.Comment.id == content_id).first()
    
    if content:
        was_content_approved = getattr(content, "moderation_status", None) == "approved"
        was_forum_reply_approved = (
            content_type == "forum_reply" and content.moderation_status == "approved"
        )
        content.moderation_status = "approved"
        if hasattr(content, "moderated_by"):
            content.moderated_by = moderator_id
        if hasattr(content, "moderated_at"):
            content.moderated_at = func.now()
        if reason:
            content.moderation_reason = reason
        if content_type == "comment":
            content.approved = True
        if content_type == "audio":
            content.status = "ready"
        if content_type == "forum_thread":
            content.last_activity_at = func.now()
        if content_type == "forum_reply" and content.thread:
            content.thread.last_activity_at = func.now()
            
        db.commit()
        db.refresh(content)

        if not was_content_approved:
            award_content_approved(db, content_type, content)

        if content_type == "forum_reply" and not was_forum_reply_approved:
            _notify_forum_reply_approved(db, content)

        # Update journal
        log_entry = db.query(models.ModerationLog).filter(
            models.ModerationLog.content_type == content_type,
            models.ModerationLog.content_id == content_id
        ).first()
        if log_entry:
            log_entry.human_decision = "approved"
            log_entry.human_reason = reason
            log_entry.moderated_by = moderator_id
            log_entry.moderated_at = func.now()
        else:
            log_entry = models.ModerationLog(
                content_type=content_type, content_id=content_id,
                user_id=(
                    content.post.user_id if content_type == "audio"
                    else content.author_id if content_type in ("forum_thread", "forum_reply")
                    else content.user_id
                ),
                ai_decision="approved",
                human_decision="approved", human_reason=reason,
                moderated_by=moderator_id, moderated_at=func.now()
            )
            db.add(log_entry)
        db.commit()

        # Notify
        notification_user_id = (
            content.post.user_id if content_type == "audio" and content.post
            else getattr(content, "author_id", None) if content_type in ("forum_thread", "forum_reply")
            else getattr(content, "user_id", None)
        )
        if notification_user_id:
            content_label = (
                "Postarea" if content_type == "post"
                else "Înregistrarea audio" if content_type == "audio"
                else "Discuția" if content_type == "forum_thread"
                else "Răspunsul din forum" if content_type == "forum_reply"
                else "Comentariul"
            )
            link = None
            if content_type == "post":
                link = f"/{content.slug}"
            elif content_type == "forum_thread":
                link = f"/discutii/{content.slug}"
            elif content_type == "forum_reply" and content.thread:
                link = f"/discutii/{content.thread.slug}"
            create_notification(
                db=db, user_id=notification_user_id, notif_type="moderation_approved",
                title="Conținut aprobat",
                message=f"{content_label} ta a fost aprobată și publicată. {reason}",
                link=link
            )
        return content
    return None

def reject_content(db: Session, content_type: str, content_id: int, moderator_id: int, reason: str = ""):
    if content_type == "post":
        content = db.query(models.Post).filter(models.Post.id == content_id).first()
    elif content_type == "audio":
        content = db.query(models.PostAudio).filter(models.PostAudio.id == content_id).first()
    elif content_type == "forum_thread":
        content = db.query(models.ForumThread).filter(models.ForumThread.id == content_id).first()
    elif content_type == "forum_reply":
        content = db.query(models.ForumReply).options(
            joinedload(models.ForumReply.thread),
        ).filter(models.ForumReply.id == content_id).first()
    else:
        content = db.query(models.Comment).filter(models.Comment.id == content_id).first()
    
    if content:
        content.moderation_status = "rejected"
        if hasattr(content, "moderated_by"):
            content.moderated_by = moderator_id
        if hasattr(content, "moderated_at"):
            content.moderated_at = func.now()
        if reason:
            content.moderation_reason = reason
        if content_type == "comment":
            content.approved = False
        if content_type == "audio":
            content.status = "rejected"
            
        db.commit()
        db.refresh(content)

        # Update journal
        log_entry = db.query(models.ModerationLog).filter(
            models.ModerationLog.content_type == content_type,
            models.ModerationLog.content_id == content_id
        ).first()
        if log_entry:
            log_entry.human_decision = "rejected"
            log_entry.human_reason = reason
            log_entry.moderated_by = moderator_id
            log_entry.moderated_at = func.now()
        else:
            log_entry = models.ModerationLog(
                content_type=content_type, content_id=content_id,
                user_id=(
                    content.post.user_id if content_type == "audio"
                    else content.author_id if content_type in ("forum_thread", "forum_reply")
                    else content.user_id
                ),
                ai_decision="approved",
                human_decision="rejected", human_reason=reason,
                moderated_by=moderator_id, moderated_at=func.now()
            )
            db.add(log_entry)
        db.commit()

        # Notify
        notification_user_id = (
            content.post.user_id if content_type == "audio" and content.post
            else getattr(content, "author_id", None) if content_type in ("forum_thread", "forum_reply")
            else getattr(content, "user_id", None)
        )
        if notification_user_id:
            content_label = (
                "Postarea" if content_type == "post"
                else "Înregistrarea audio" if content_type == "audio"
                else "Discuția" if content_type == "forum_thread"
                else "Răspunsul din forum" if content_type == "forum_reply"
                else "Comentariul"
            )
            create_notification(
                db=db, user_id=notification_user_id, notif_type="moderation_rejected",
                title="Conținut respins",
                message=f"{content_label} ta a fost respinsă. Motiv: {reason}",
                link=None
            )
        return content
    return None

# ===================================
# LIKE CRUD FUNCTIONS
# ===================================

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

def get_featured_posts_for_user(db: Session, user_id: int):
    return db.query(models.FeaturedPost).options(joinedload(models.FeaturedPost.post)).filter(
        models.FeaturedPost.user_id == user_id
    ).order_by(models.FeaturedPost.position).all()

def get_best_friends_for_user(db: Session, user_id: int):
    return db.query(models.BestFriend).options(joinedload(models.BestFriend.friend)).filter(
        models.BestFriend.user_id == user_id
    ).order_by(models.BestFriend.position).all()

# ===================================
# AWARDS
# ===================================

def get_user_awards(db: Session, user_id: int):
    return db.query(models.UserAward).filter(models.UserAward.user_id == user_id).order_by(models.UserAward.award_date.desc()).all()


# ===================================
# GOLOGANI / SHOP
# ===================================

GOLOGANI_REWARDS = {
    "post_approved": 25,
    "comment_approved": 8,
    "like_given": 1,
    "like_received": 2,
    "super_like_given": 5,
    "super_like_received": 15,
    "forum_thread_approved": 15,
    "forum_reply_approved": 8,
}

DEFAULT_SHOP_ITEMS = [
    {
        "slug": "manuscrisul-scrisorii-a-iii-a",
        "name": "Manuscrisul Scrisorii a III-a",
        "description": "Un manuscris de vitrină pentru profilul tău.",
        "price": 120,
        "slot": "profile_badge",
        "sort_order": 10,
    },
    {
        "slug": "costumul-de-nunta-al-lui-nichita-stanescu",
        "name": "Costumul de nuntă al lui Nichita Stănescu",
        "description": "Un costum literar pentru apariții de cenaclu.",
        "price": 250,
        "slot": "costume",
        "sort_order": 20,
    },
]


class EconomyError(Exception):
    """Base class for Gologani/shop errors."""


class InsufficientGologaniError(EconomyError):
    pass


class ShopItemNotFoundError(EconomyError):
    pass


class ShopItemInactiveError(EconomyError):
    pass


class ShopItemDuplicateSlugError(EconomyError):
    pass


class InventoryDuplicateError(EconomyError):
    pass


class InventoryItemNotFoundError(EconomyError):
    pass


def _normalize_balance(user: models.User) -> int:
    return int(user.gologani_balance or 0)


def grant_gologani(
    db: Session,
    *,
    user_id: Optional[int],
    amount: int,
    event_type: str,
    idempotency_key: str,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    description: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> Optional[models.GologaniTransaction]:
    if not user_id or amount == 0:
        return None
    existing = (
        db.query(models.GologaniTransaction)
        .filter(models.GologaniTransaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    user.gologani_balance = _normalize_balance(user) + amount
    transaction = models.GologaniTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=user.gologani_balance,
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        description=description,
        extra_data=extra_data or {},
    )
    db.add(transaction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return (
            db.query(models.GologaniTransaction)
            .filter(models.GologaniTransaction.idempotency_key == idempotency_key)
            .first()
        )
    db.refresh(transaction)
    return transaction


def award_content_approved(db: Session, content_type: str, content) -> Optional[models.GologaniTransaction]:
    reward_key = f"{content_type}_approved"
    amount = GOLOGANI_REWARDS.get(reward_key)
    if not amount:
        return None
    if getattr(content, "moderation_status", None) != "approved":
        return None
    if content_type == "post":
        user_id = getattr(content, "user_id", None)
        label = "Postare aprobată"
    elif content_type == "comment":
        if getattr(content, "is_robot", False):
            return None
        user_id = getattr(content, "user_id", None)
        label = "Comentariu aprobat"
    elif content_type == "forum_thread":
        user_id = getattr(content, "author_id", None)
        label = "Discuție de forum aprobată"
    elif content_type == "forum_reply":
        user_id = getattr(content, "author_id", None)
        label = "Răspuns de forum aprobat"
    else:
        return None
    source_id = getattr(content, "id", None)
    return grant_gologani(
        db,
        user_id=user_id,
        amount=amount,
        event_type=reward_key,
        source_type=content_type,
        source_id=source_id,
        idempotency_key=f"reward:{reward_key}:{source_id}",
        description=label,
    )


def award_like_created(db: Session, like: models.Like) -> None:
    if not like.user_id:
        return
    post = like.post or get_post(db, like.post_id)
    if not post or post.moderation_status != "approved" or post.user_id == like.user_id:
        return
    grant_gologani(
        db,
        user_id=like.user_id,
        amount=GOLOGANI_REWARDS["like_given"],
        event_type="like_given",
        source_type="like",
        source_id=like.id,
        idempotency_key=f"reward:like_given:{like.user_id}:{like.post_id}",
        description="Apreciere oferită",
    )
    grant_gologani(
        db,
        user_id=post.user_id,
        amount=GOLOGANI_REWARDS["like_received"],
        event_type="like_received",
        source_type="like",
        source_id=like.id,
        idempotency_key=f"reward:like_received:{like.user_id}:{like.post_id}",
        description="Apreciere primită",
    )


def award_super_like_created(db: Session, super_like: models.SuperLike) -> None:
    post = super_like.post or get_post(db, super_like.post_id)
    if not post or post.moderation_status != "approved" or post.user_id == super_like.user_id:
        return
    grant_gologani(
        db,
        user_id=super_like.user_id,
        amount=GOLOGANI_REWARDS["super_like_given"],
        event_type="super_like_given",
        source_type="super_like",
        source_id=super_like.id,
        idempotency_key=f"reward:super_like_given:{super_like.user_id}:{super_like.post_id}",
        description="Super-apreciere oferită",
    )
    grant_gologani(
        db,
        user_id=post.user_id,
        amount=GOLOGANI_REWARDS["super_like_received"],
        event_type="super_like_received",
        source_type="super_like",
        source_id=super_like.id,
        idempotency_key=f"reward:super_like_received:{super_like.user_id}:{super_like.post_id}",
        description="Super-apreciere primită",
    )


def seed_default_shop_items(db: Session) -> None:
    changed = False
    for item_data in DEFAULT_SHOP_ITEMS:
        exists = db.query(models.ShopItem.id).filter(models.ShopItem.slug == item_data["slug"]).first()
        if not exists:
            db.add(models.ShopItem(**item_data))
            changed = True
    if changed:
        db.commit()


def list_shop_items(db: Session, include_inactive: bool = False) -> List[models.ShopItem]:
    query = db.query(models.ShopItem)
    if not include_inactive:
        query = query.filter(models.ShopItem.is_active == True)
    return query.order_by(models.ShopItem.sort_order.asc(), models.ShopItem.id.asc()).all()


def get_shop_item(db: Session, item_id: int) -> Optional[models.ShopItem]:
    return db.query(models.ShopItem).filter(models.ShopItem.id == item_id).first()


def create_shop_item(db: Session, data: schemas.ShopItemCreate) -> models.ShopItem:
    item = models.ShopItem(**data.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ShopItemDuplicateSlugError()
    db.refresh(item)
    return item


def update_shop_item(db: Session, item_id: int, data: schemas.ShopItemUpdate) -> Optional[models.ShopItem]:
    item = get_shop_item(db, item_id)
    if not item:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ShopItemDuplicateSlugError()
    db.refresh(item)
    return item


def get_inventory_for_user(db: Session, user_id: int) -> List[models.UserInventoryItem]:
    return (
        db.query(models.UserInventoryItem)
        .options(joinedload(models.UserInventoryItem.item))
        .filter(models.UserInventoryItem.user_id == user_id)
        .order_by(models.UserInventoryItem.purchased_at.desc(), models.UserInventoryItem.id.desc())
        .all()
    )


def get_equipped_items_for_user(db: Session, user_id: int) -> List[models.UserEquippedItem]:
    return (
        db.query(models.UserEquippedItem)
        .options(joinedload(models.UserEquippedItem.item))
        .filter(models.UserEquippedItem.user_id == user_id)
        .order_by(models.UserEquippedItem.slot.asc())
        .all()
    )


def purchase_shop_item(db: Session, user: models.User, item_id: int) -> models.UserInventoryItem:
    item = get_shop_item(db, item_id)
    if not item:
        raise ShopItemNotFoundError()
    if not item.is_active:
        raise ShopItemInactiveError()
    buyer = db.query(models.User).filter(models.User.id == user.id).first()
    if not buyer:
        raise ShopItemNotFoundError()
    existing = (
        db.query(models.UserInventoryItem)
        .filter(
            models.UserInventoryItem.user_id == buyer.id,
            models.UserInventoryItem.item_id == item.id,
        )
        .first()
    )
    if existing:
        raise InventoryDuplicateError()
    if _normalize_balance(buyer) < item.price:
        raise InsufficientGologaniError()
    buyer.gologani_balance = _normalize_balance(buyer) - item.price
    inventory_item = models.UserInventoryItem(user_id=buyer.id, item_id=item.id)
    transaction = models.GologaniTransaction(
        user_id=buyer.id,
        amount=-item.price,
        balance_after=buyer.gologani_balance,
        event_type="shop_purchase",
        source_type="shop_item",
        source_id=item.id,
        idempotency_key=f"purchase:{buyer.id}:{item.id}",
        description=f"Cumpărat: {item.name}",
        extra_data={"item_slug": item.slug, "item_slot": item.slot},
    )
    db.add(inventory_item)
    db.add(transaction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise InventoryDuplicateError()
    db.refresh(inventory_item)
    return inventory_item


def equip_inventory_item(db: Session, user: models.User, item_id: int) -> models.UserEquippedItem:
    inventory_item = (
        db.query(models.UserInventoryItem)
        .options(joinedload(models.UserInventoryItem.item))
        .filter(
            models.UserInventoryItem.user_id == user.id,
            models.UserInventoryItem.item_id == item_id,
        )
        .first()
    )
    if not inventory_item or not inventory_item.item:
        raise InventoryItemNotFoundError()
    equipped = (
        db.query(models.UserEquippedItem)
        .filter(
            models.UserEquippedItem.user_id == user.id,
            models.UserEquippedItem.slot == inventory_item.item.slot,
        )
        .first()
    )
    if equipped:
        equipped.item_id = inventory_item.item_id
        equipped.equipped_at = func.now()
    else:
        equipped = models.UserEquippedItem(
            user_id=user.id,
            item_id=inventory_item.item_id,
            slot=inventory_item.item.slot,
        )
        db.add(equipped)
    db.commit()
    db.refresh(equipped)
    return equipped


def unequip_slot(db: Session, user: models.User, slot: str) -> bool:
    equipped = (
        db.query(models.UserEquippedItem)
        .filter(
            models.UserEquippedItem.user_id == user.id,
            models.UserEquippedItem.slot == slot,
        )
        .first()
    )
    if not equipped:
        return False
    db.delete(equipped)
    db.commit()
    return True


# ===================================
# FORUM CRUD FUNCTIONS
# ===================================

FORUM_SECTIONS = ("general", "poezie", "proza_scurta", "feedback", "anunturi")


def is_forum_section(section: str) -> bool:
    return section in FORUM_SECTIONS


def _forum_status_value(moderation_result) -> str:
    status = getattr(moderation_result, "status", "approved")
    return getattr(status, "value", status)


def _ensure_unique_forum_slug(db: Session, base_slug: str) -> str:
    normalized = base_slug or "discutie"
    slug = normalized
    counter = 1
    while db.query(models.ForumThread).filter(models.ForumThread.slug == slug).first():
        slug = f"{normalized}-{counter}"
        counter += 1
    return slug


def get_forum_thread(db: Session, thread_id: int) -> Optional[models.ForumThread]:
    return (
        db.query(models.ForumThread)
        .options(joinedload(models.ForumThread.author))
        .filter(models.ForumThread.id == thread_id)
        .first()
    )


def get_forum_thread_by_slug(db: Session, slug: str) -> Optional[models.ForumThread]:
    return (
        db.query(models.ForumThread)
        .options(
            joinedload(models.ForumThread.author),
            joinedload(models.ForumThread.replies).joinedload(models.ForumReply.author),
        )
        .filter(models.ForumThread.slug == slug)
        .first()
    )


def can_view_forum_thread(user: models.User, thread: models.ForumThread) -> bool:
    return (
        thread.moderation_status == "approved"
        or thread.author_id == user.id
        or user.is_admin
        or user.is_moderator
    )


def can_moderate_forum(user: models.User) -> bool:
    return user.is_admin or user.is_moderator


def list_forum_threads(
    db: Session,
    section: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
) -> List[models.ForumThread]:
    query = (
        db.query(models.ForumThread)
        .options(joinedload(models.ForumThread.author))
        .filter(models.ForumThread.moderation_status == "approved")
    )
    if section and is_forum_section(section):
        query = query.filter(models.ForumThread.section == section)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.ForumThread.title.ilike(pattern),
                models.ForumThread.content.ilike(pattern),
            )
        )
    return (
        query.order_by(
            models.ForumThread.is_pinned.desc(),
            models.ForumThread.last_activity_at.desc(),
            models.ForumThread.id.desc(),
        )
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )


def create_forum_thread(
    db: Session, author: models.User, data: schemas.ForumThreadCreate
) -> models.ForumThread:
    if not is_forum_section(data.section):
        raise ValueError("invalid_section")
    base_slug = generate_slug(data.title.strip()) or "discutie"
    thread = models.ForumThread(
        author_id=author.id,
        section=data.section,
        title=data.title.strip(),
        slug=_ensure_unique_forum_slug(db, base_slug),
        content=data.content.strip(),
        moderation_status="pending",
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def list_forum_replies_for_thread(
    db: Session, thread_id: int, viewer: models.User
) -> List[models.ForumReply]:
    query = (
        db.query(models.ForumReply)
        .options(joinedload(models.ForumReply.author))
        .filter(models.ForumReply.thread_id == thread_id)
    )
    if not can_moderate_forum(viewer):
        query = query.filter(
            or_(
                models.ForumReply.moderation_status == "approved",
                models.ForumReply.author_id == viewer.id,
            )
        )
    return query.order_by(models.ForumReply.created_at.asc(), models.ForumReply.id.asc()).all()


def create_forum_reply(
    db: Session,
    author: models.User,
    thread: models.ForumThread,
    data: schemas.ForumReplyCreate,
) -> tuple[Optional[models.ForumReply], Optional[str]]:
    if not can_view_forum_thread(author, thread):
        return None, "not_found"
    if thread.moderation_status != "approved":
        return None, "thread_not_approved"
    if thread.is_locked and not can_moderate_forum(author):
        return None, "locked"
    reply = models.ForumReply(
        thread_id=thread.id,
        author_id=author.id,
        content=data.content.strip(),
        moderation_status="pending",
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply, None


def _notify_forum_reply_approved(db: Session, reply: models.ForumReply) -> None:
    thread = reply.thread or get_forum_thread(db, reply.thread_id)
    if not thread or thread.author_id == reply.author_id:
        return
    author = reply.author or get_user_by_id(db, reply.author_id)
    create_notification(
        db=db,
        user_id=thread.author_id,
        notif_type="forum_reply",
        title="Răspuns nou în discuția ta",
        message=f"{author.username if author else 'Un utilizator'} a răspuns în „{thread.title}\".",
        link=f"/discutii/{thread.slug}",
        extra_data={"thread_id": thread.id, "reply_id": reply.id, "thread_slug": thread.slug},
    )


def apply_forum_thread_moderation_result(db: Session, thread: models.ForumThread, moderation_result) -> models.ForumThread:
    was_approved = thread.moderation_status == "approved"
    thread.moderation_status = _forum_status_value(moderation_result)
    thread.toxicity_score = getattr(moderation_result, "toxicity_score", None)
    thread.moderation_reason = getattr(moderation_result, "reason", None)
    if thread.moderation_status == "approved":
        thread.last_activity_at = func.now()
    db.commit()
    db.refresh(thread)
    if thread.moderation_status == "approved" and not was_approved:
        award_content_approved(db, "forum_thread", thread)
    return thread


def apply_forum_reply_moderation_result(db: Session, reply: models.ForumReply, moderation_result) -> models.ForumReply:
    was_approved = reply.moderation_status == "approved"
    reply.moderation_status = _forum_status_value(moderation_result)
    reply.toxicity_score = getattr(moderation_result, "toxicity_score", None)
    reply.moderation_reason = getattr(moderation_result, "reason", None)
    if reply.moderation_status == "approved":
        thread = reply.thread or get_forum_thread(db, reply.thread_id)
        if thread:
            thread.last_activity_at = func.now()
    db.commit()
    db.refresh(reply)
    if reply.moderation_status == "approved" and not was_approved:
        award_content_approved(db, "forum_reply", reply)
        _notify_forum_reply_approved(db, reply)
    return reply


def delete_forum_thread(db: Session, actor: models.User, thread: models.ForumThread) -> bool:
    if thread.author_id != actor.id and not can_moderate_forum(actor):
        return False
    db.delete(thread)
    db.commit()
    return True


def get_forum_reply(db: Session, reply_id: int) -> Optional[models.ForumReply]:
    return (
        db.query(models.ForumReply)
        .options(
            joinedload(models.ForumReply.author),
            joinedload(models.ForumReply.thread),
        )
        .filter(models.ForumReply.id == reply_id)
        .first()
    )


def delete_forum_reply(db: Session, actor: models.User, reply: models.ForumReply) -> bool:
    if reply.author_id != actor.id and not can_moderate_forum(actor):
        return False
    db.delete(reply)
    db.commit()
    return True


def update_forum_thread_state(
    db: Session, actor: models.User, thread: models.ForumThread, action: str
) -> tuple[Optional[models.ForumThread], Optional[str]]:
    if not can_moderate_forum(actor):
        return None, "not_allowed"
    if action == "lock":
        thread.is_locked = True
    elif action == "unlock":
        thread.is_locked = False
    elif action == "pin":
        thread.is_pinned = True
    elif action == "unpin":
        thread.is_pinned = False
    else:
        return None, "bad_action"
    db.commit()
    db.refresh(thread)
    return thread, None


def get_forum_threads_for_moderation(
    db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50
) -> List[models.ForumThread]:
    query = db.query(models.ForumThread).options(joinedload(models.ForumThread.author))
    if status_filter:
        query = query.filter(models.ForumThread.moderation_status == status_filter)
    return query.order_by(models.ForumThread.created_at.desc()).offset(skip).limit(limit).all()


def get_forum_replies_for_moderation(
    db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50
) -> List[models.ForumReply]:
    query = db.query(models.ForumReply).options(
        joinedload(models.ForumReply.author),
        joinedload(models.ForumReply.thread),
    )
    if status_filter:
        query = query.filter(models.ForumReply.moderation_status == status_filter)
    return query.order_by(models.ForumReply.created_at.desc()).offset(skip).limit(limit).all()


# ===================================
# MESSAGE CRUD FUNCTIONS
# ===================================

def _conversation_access_filter(user_id: int):
    return or_(
        models.Conversation.user1_id == user_id,
        models.Conversation.user2_id == user_id,
    )

def _ordered_participants(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)

def get_user_conversations(db: Session, user_id: int):
    conversations = db.query(models.Conversation).options(
        joinedload(models.Conversation.user1),
        joinedload(models.Conversation.user2),
        joinedload(models.Conversation.messages),
    ).filter(
        _conversation_access_filter(user_id)
    ).order_by(
        models.Conversation.updated_at.desc()
    ).all()

    for conversation in conversations:
        conversation._latest_message = conversation.get_latest_message()

    return conversations

def get_conversation_by_id(db: Session, conversation_id: int, user_id: int):
    return db.query(models.Conversation).options(
        joinedload(models.Conversation.user1),
        joinedload(models.Conversation.user2),
    ).filter(
        models.Conversation.id == conversation_id,
        _conversation_access_filter(user_id),
    ).first()

def get_conversation_messages(db: Session, conversation_id: int, user_id: int, limit: int = 50, offset: int = 0):
    if not get_conversation_by_id(db, conversation_id, user_id):
        return []

    return db.query(models.Message).options(
        joinedload(models.Message.sender)
    ).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(
        models.Message.created_at.desc(),
        models.Message.id.desc(),
    ).offset(offset).limit(limit).all()

def mark_messages_as_read(db: Session, conversation_id: int, user_id: int):
    if not get_conversation_by_id(db, conversation_id, user_id):
        return 0

    updated_count = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id,
        models.Message.sender_id != user_id,
        models.Message.is_read == False,
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return updated_count

def create_message(db: Session, conversation_id: int, sender_id: int, content: str):
    conversation = get_conversation_by_id(db, conversation_id, sender_id)
    if not conversation:
        return None

    message = models.Message(
        conversation_id=conversation.id,
        sender_id=sender_id,
        content=content,
    )
    db.add(message)
    conversation.updated_at = func.now()
    db.commit()
    db.refresh(message)
    return message

def send_message_to_user(db: Session, sender_id: int, recipient_username: str, content: str):
    recipient = get_user_by_username(db, recipient_username.strip())
    if recipient is None or recipient.id == sender_id:
        return None

    user1_id, user2_id = _ordered_participants(sender_id, recipient.id)
    conversation = db.query(models.Conversation).filter(
        models.Conversation.user1_id == user1_id,
        models.Conversation.user2_id == user2_id,
    ).first()

    if conversation is None:
        conversation = models.Conversation(user1_id=user1_id, user2_id=user2_id)
        db.add(conversation)
        db.flush()

    message = models.Message(
        conversation_id=conversation.id,
        sender_id=sender_id,
        content=content,
    )
    db.add(message)
    conversation.updated_at = func.now()
    db.commit()
    db.refresh(message)
    return message

def get_unread_message_count(db: Session, user_id: int):
    return db.query(models.Message).join(
        models.Conversation,
        models.Message.conversation_id == models.Conversation.id,
    ).filter(
        _conversation_access_filter(user_id),
        models.Message.sender_id != user_id,
        models.Message.is_read == False,
    ).count()

def delete_conversation(db: Session, conversation_id: int, user_id: int):
    conversation = get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        return False

    db.delete(conversation)
    db.commit()
    return True

def search_conversations(db: Session, user_id: int, q: str):
    normalized_query = q.strip().lower()
    if not normalized_query:
        return get_user_conversations(db, user_id)

    matches = []
    for conversation in get_user_conversations(db, user_id):
        other_user = conversation.get_other_user(user_id)
        username_matches = normalized_query in other_user.username.lower()
        message_matches = any(
            normalized_query in (message.content or "").lower()
            for message in conversation.messages
        )
        if username_matches or message_matches:
            matches.append(conversation)
    return matches

# ===================================
# NOTIFICATION CRUD FUNCTIONS
# ===================================

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

def get_moderation_logs(db: Session, limit: int = 100, offset: int = 0):
    return db.query(models.ModerationLog).order_by(models.ModerationLog.created_at.desc()).offset(offset).limit(limit).all()

def get_moderation_logs_by_decision(db: Session, decision: str, limit: int = 100):
    query = db.query(models.ModerationLog)
    if decision == "pending":
        query = query.filter(
            models.ModerationLog.ai_decision == "flagged",
            or_(
                models.ModerationLog.human_decision == "pending",
                models.ModerationLog.human_decision == None,
            )
        )
    else:
        query = query.filter(
            or_(
                models.ModerationLog.ai_decision == decision,
                models.ModerationLog.human_decision == decision,
            )
        )
    return query.order_by(models.ModerationLog.created_at.desc()).limit(limit).all()

def get_moderation_logs_for_review(db: Session, limit: int = 50):
    return db.query(models.ModerationLog).filter(
        models.ModerationLog.ai_decision == "flagged",
        or_(models.ModerationLog.human_decision == None, models.ModerationLog.human_decision == "pending")
    ).order_by(models.ModerationLog.created_at.desc()).limit(limit).all()

def update_moderation_log_human_decision(db: Session, log_id: int, decision: str, reason: str, moderator_id: int):
    log = db.query(models.ModerationLog).filter(models.ModerationLog.id == log_id).first()
    if log:
        log.human_decision = decision
        log.human_reason = reason
        log.moderated_by = moderator_id
        log.moderated_at = func.now()
        db.commit()
        db.refresh(log)
    return log

# ===================================
# COLLECTION CRUD FUNCTIONS
# ===================================

def _generate_collection_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    return slug or "colectie"

def _ensure_unique_collection_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while db.query(models.Collection).filter(models.Collection.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

def get_collection(db: Session, collection_id: int):
    return db.query(models.Collection).filter(models.Collection.id == collection_id).first()

def get_collection_by_slug(db: Session, slug: str):
    return db.query(models.Collection).options(
        joinedload(models.Collection.owner)
    ).filter(models.Collection.slug == slug).first()

def get_collections_by_owner(db: Session, owner_id: int):
    return db.query(models.Collection).options(
        joinedload(models.Collection.owner)
    ).filter(
        models.Collection.owner_id == owner_id
    ).order_by(models.Collection.created_at.desc()).all()

def create_collection(db: Session, owner_id: int, data: schemas.CollectionCreate) -> models.Collection:
    base_slug = _generate_collection_slug(data.title)
    slug = _ensure_unique_collection_slug(db, base_slug)
    collection = models.Collection(
        owner_id=owner_id,
        title=data.title.strip(),
        slug=slug,
        description=(data.description or "").strip() or None,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection

def update_collection(db: Session, collection_id: int, data: schemas.CollectionUpdate) -> Optional[models.Collection]:
    collection = get_collection(db, collection_id)
    if not collection:
        return None
    payload = data.model_dump(exclude_unset=True)
    if "title" in payload and payload["title"]:
        collection.title = payload["title"].strip()
    if "description" in payload:
        value = payload["description"]
        collection.description = value.strip() if value else None
    db.commit()
    db.refresh(collection)
    return collection

def delete_collection(db: Session, collection_id: int) -> bool:
    collection = get_collection(db, collection_id)
    if not collection:
        return False
    db.delete(collection)
    db.commit()
    return True

def count_collection_posts(db: Session, collection_id: int, status: str = "accepted") -> int:
    return db.query(models.CollectionPost).filter(
        models.CollectionPost.collection_id == collection_id,
        models.CollectionPost.status == status,
    ).count()

def get_collection_entries(
    db: Session,
    collection_id: int,
    status: Optional[str] = "accepted",
    approved_posts_only: bool = True,
):
    query = db.query(models.CollectionPost).options(
        joinedload(models.CollectionPost.post).joinedload(models.Post.owner)
    ).filter(models.CollectionPost.collection_id == collection_id)
    if status:
        query = query.filter(models.CollectionPost.status == status)
    entries = query.order_by(
        models.CollectionPost.position.asc().nullslast(),
        models.CollectionPost.created_at.desc(),
    ).all()
    if approved_posts_only and status == "accepted":
        entries = [e for e in entries if e.post and e.post.moderation_status == "approved"]
    return entries

def get_collection_entry(db: Session, collection_id: int, post_id: int) -> Optional[models.CollectionPost]:
    return db.query(models.CollectionPost).filter(
        models.CollectionPost.collection_id == collection_id,
        models.CollectionPost.post_id == post_id,
    ).first()

def add_post_to_collection(
    db: Session,
    collection: models.Collection,
    post: models.Post,
    initiator_id: int,
) -> tuple[Optional[models.CollectionPost], Optional[str]]:
    """Add or re-propose a post in a collection.

    Returns (entry, error). Permission rules:
      - If initiator is both owner and author: auto-accept.
      - If initiator is the owner only: pending, author must approve.
      - If initiator is the author only: pending, owner must approve.
      - Otherwise: error.
    """
    owner_id = collection.owner_id
    author_id = post.user_id
    is_owner = initiator_id == owner_id
    is_author = initiator_id == author_id

    if not is_owner and not is_author:
        return None, "not_allowed"

    existing = get_collection_entry(db, collection.id, post.id)
    if existing:
        if existing.status == "accepted":
            return existing, "already_in_collection"
        if existing.status == "pending":
            return existing, "already_pending"
        # previously rejected — allow re-initiation by either party by reusing the row
        existing.initiator_id = initiator_id
        existing.created_at = func.now()
        existing.responded_at = None
        auto_accept = is_owner and is_author
        existing.status = "accepted" if auto_accept else "pending"
        db.commit()
        db.refresh(existing)
        _notify_collection_counterparty(db, existing, collection, post, action="created")
        return existing, None

    auto_accept = is_owner and is_author
    entry = models.CollectionPost(
        collection_id=collection.id,
        post_id=post.id,
        initiator_id=initiator_id,
        status="accepted" if auto_accept else "pending",
        responded_at=(func.now() if auto_accept else None),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    _notify_collection_counterparty(db, entry, collection, post, action="created")
    return entry, None

def respond_to_collection_entry(
    db: Session,
    entry: models.CollectionPost,
    responder_id: int,
    action: str,
) -> tuple[Optional[models.CollectionPost], Optional[str]]:
    if action not in ("accept", "reject"):
        return None, "bad_action"
    if entry.status != "pending":
        return None, "not_pending"

    collection = entry.collection
    post = entry.post
    owner_id = collection.owner_id
    author_id = post.user_id

    # Responder must be the counterparty: if initiator is the owner, responder must be the author, and vice versa.
    initiator_id = entry.initiator_id
    if initiator_id == owner_id:
        expected_responder = author_id
    elif initiator_id == author_id:
        expected_responder = owner_id
    else:
        return None, "inconsistent_initiator"

    if responder_id != expected_responder:
        return None, "not_allowed"

    entry.status = "accepted" if action == "accept" else "rejected"
    entry.responded_at = func.now()
    db.commit()
    db.refresh(entry)
    _notify_collection_counterparty(db, entry, collection, post, action=entry.status)
    return entry, None

def remove_collection_entry(
    db: Session,
    entry: models.CollectionPost,
    user_id: int,
) -> tuple[bool, Optional[str]]:
    collection = entry.collection
    post = entry.post
    owner_id = collection.owner_id
    author_id = post.user_id

    allowed = False
    if entry.status == "accepted":
        allowed = user_id in (owner_id, author_id)
    elif entry.status == "pending":
        allowed = user_id in (owner_id, author_id, entry.initiator_id)
    else:  # rejected
        allowed = user_id in (owner_id, author_id, entry.initiator_id)

    if not allowed:
        return False, "not_allowed"

    # Notify the other party if the accepted association is being torn down by the non-author
    if entry.status == "accepted" and user_id == owner_id and author_id != owner_id:
        create_notification(
            db=db,
            user_id=author_id,
            notif_type="collection_removed",
            title="Postare scoasă dintr-o colecție",
            message=f"Postarea ta \"{post.title}\" a fost scoasă din colecția \"{collection.title}\".",
            link=f"/{post.slug}",
            extra_data={"collection_id": collection.id, "post_id": post.id},
        )
    elif entry.status == "accepted" and user_id == author_id and author_id != owner_id:
        create_notification(
            db=db,
            user_id=owner_id,
            notif_type="collection_removed",
            title="Postare retrasă dintr-o colecție",
            message=f"Autorul a retras postarea \"{post.title}\" din colecția \"{collection.title}\".",
            link=f"/colectii/{collection.slug}",
            extra_data={"collection_id": collection.id, "post_id": post.id},
        )

    db.delete(entry)
    db.commit()
    return True, None

def _notify_collection_counterparty(
    db: Session,
    entry: models.CollectionPost,
    collection: models.Collection,
    post: models.Post,
    action: str,
):
    owner_id = collection.owner_id
    author_id = post.user_id
    initiator_id = entry.initiator_id

    if owner_id == author_id:
        return  # no counterparty to notify when the owner adds their own post

    if action == "created" and entry.status == "pending":
        counterparty_id = author_id if initiator_id == owner_id else owner_id
        if initiator_id == owner_id:
            title = "Invitație într-o colecție"
            message = f"Postarea ta \"{post.title}\" a fost propusă pentru colecția \"{collection.title}\". Acceptă sau refuză din panou."
        else:
            title = "Sugestie pentru colecția ta"
            message = f"Un autor a sugerat postarea \"{post.title}\" pentru colecția \"{collection.title}\". Acceptă sau refuză din panou."
        create_notification(
            db=db,
            user_id=counterparty_id,
            notif_type="collection_pending",
            title=title,
            message=message,
            link=f"/panou",
            extra_data={"collection_id": collection.id, "post_id": post.id, "entry_id": entry.id},
        )
        return

    if action in ("accepted", "rejected"):
        # Notify the initiator of the outcome.
        if action == "accepted":
            title = "Postare adăugată într-o colecție"
            message = f"Postarea \"{post.title}\" face acum parte din colecția \"{collection.title}\"."
        else:
            title = "Propunere respinsă"
            message = f"Propunerea pentru \"{post.title}\" în colecția \"{collection.title}\" a fost respinsă."
        create_notification(
            db=db,
            user_id=initiator_id,
            notif_type=f"collection_{action}",
            title=title,
            message=message,
            link=f"/colectii/{collection.slug}" if action == "accepted" else "/panou",
            extra_data={"collection_id": collection.id, "post_id": post.id, "entry_id": entry.id},
        )

def get_pending_approvals_for_user(db: Session, user_id: int):
    """Return pending entries where the user is the counterparty.

    Produces two kinds of items:
      - "invitation": owner initiated, current user is the post author.
      - "suggestion": author initiated, current user is the collection owner.
    """
    entries = db.query(models.CollectionPost).options(
        joinedload(models.CollectionPost.collection).joinedload(models.Collection.owner),
        joinedload(models.CollectionPost.post).joinedload(models.Post.owner),
    ).filter(models.CollectionPost.status == "pending").all()

    results = []
    for entry in entries:
        if not entry.collection or not entry.post:
            continue
        owner_id = entry.collection.owner_id
        author_id = entry.post.user_id
        if owner_id == author_id:
            continue
        if entry.initiator_id == owner_id and author_id == user_id:
            direction = "invitation"
        elif entry.initiator_id == author_id and owner_id == user_id:
            direction = "suggestion"
        else:
            continue
        results.append((entry, direction))
    # Most-recent first
    results.sort(key=lambda pair: pair[0].created_at, reverse=True)
    return results

def get_collections_containing_post(db: Session, post_id: int):
    """Accepted public collections that contain a given post."""
    entries = db.query(models.CollectionPost).options(
        joinedload(models.CollectionPost.collection).joinedload(models.Collection.owner)
    ).filter(
        models.CollectionPost.post_id == post_id,
        models.CollectionPost.status == "accepted",
    ).all()
    return [e.collection for e in entries if e.collection is not None]


def get_moderation_stats_extended(db: Session):
    total_logs = db.query(models.ModerationLog).count()
    pending_review_count = db.query(models.ModerationLog).filter(
        models.ModerationLog.ai_decision == "flagged",
        or_(
            models.ModerationLog.human_decision == None,
            models.ModerationLog.human_decision == "pending",
        )
    ).count()

    average_toxicity = db.query(func.avg(models.ModerationLog.toxicity_score)).scalar()
    max_toxicity = db.query(func.max(models.ModerationLog.toxicity_score)).scalar()

    return {
        "total_logs": total_logs,
        "pending_review_count": pending_review_count,
        "ai_decisions": {
            "approved": db.query(models.ModerationLog).filter(models.ModerationLog.ai_decision == "approved").count(),
            "flagged": db.query(models.ModerationLog).filter(models.ModerationLog.ai_decision == "flagged").count(),
            "rejected": db.query(models.ModerationLog).filter(models.ModerationLog.ai_decision == "rejected").count(),
        },
        "human_decisions": {
            "approved": db.query(models.ModerationLog).filter(models.ModerationLog.human_decision == "approved").count(),
            "rejected": db.query(models.ModerationLog).filter(models.ModerationLog.human_decision == "rejected").count(),
            "pending": db.query(models.ModerationLog).filter(
                or_(
                    models.ModerationLog.human_decision == "pending",
                    models.ModerationLog.human_decision == None,
                )
            ).count(),
        },
        "scores": {
            "average_toxicity": float(average_toxicity or 0),
            "max_toxicity": float(max_toxicity or 0),
        },
    }


# ===================================
# SUPER-APRECIEZ CRUD
# ===================================

from .week_util import start_of_iso_week_utc


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

def upsert_stripe_customer_id(db: Session, user_id: int, customer_id: str) -> None:
    db.query(models.User).filter(models.User.id == user_id).update(
        {"stripe_customer_id": customer_id}
    )
    db.commit()


def get_user_by_stripe_customer_id(db: Session, customer_id: str) -> Optional[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.stripe_customer_id == customer_id)
        .first()
    )


def set_premium_from_subscription(
    db: Session,
    user_id: int,
    subscription_id: str,
    premium_until: datetime,
    premium_tier: str = "premium",
    premium_period_start: Optional[datetime] = None,
) -> None:
    fields = {
        "stripe_subscription_id": subscription_id,
        "premium_tier": premium_tier,
        "premium_until": premium_until,
    }
    if premium_period_start is not None:
        fields["premium_period_start"] = premium_period_start
    db.query(models.User).filter(models.User.id == user_id).update(fields)
    db.commit()


def clear_stripe_subscription(db: Session, user_id: int) -> None:
    db.query(models.User).filter(models.User.id == user_id).update(
        {"stripe_subscription_id": None}
    )
    db.commit()


def record_stripe_event(db: Session, event_id: str, event_type: str) -> bool:
    """Return True if this is a new event; False if already processed."""
    existing = db.query(models.StripeEvent).filter(models.StripeEvent.id == event_id).first()
    if existing:
        return False
    db.add(models.StripeEvent(id=event_id, type=event_type))
    db.commit()
    return True


# ===================================
# CLUB CRUD FUNCTIONS
# ===================================

CLUB_FEATURED_DURATION = timedelta(days=7)
CLUB_VALID_SPECIALITIES = ("poezie", "proza_scurta")


def _generate_club_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    return slug or "club"


def _ensure_unique_club_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while db.query(models.Club).filter(models.Club.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def get_club(db: Session, club_id: int) -> Optional[models.Club]:
    return db.query(models.Club).filter(models.Club.id == club_id).first()


def get_club_by_slug(db: Session, slug: str) -> Optional[models.Club]:
    return db.query(models.Club).options(
        joinedload(models.Club.owner)
    ).filter(models.Club.slug == slug).first()


def list_clubs(
    db: Session,
    *,
    speciality: Optional[str] = None,
    theme_query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(models.Club).options(joinedload(models.Club.owner))
    if speciality:
        query = query.filter(models.Club.speciality == speciality)
    if theme_query:
        like = f"%{theme_query.strip()}%"
        query = query.filter(
            or_(
                models.Club.theme.ilike(like),
                models.Club.title.ilike(like),
            )
        )
    return (
        query.order_by(models.Club.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_random_club(db: Session) -> Optional[models.Club]:
    """Random club that has at least one member (always at minimum the owner)."""
    return (
        db.query(models.Club)
        .options(joinedload(models.Club.owner))
        .filter(
            db.query(models.ClubMember.id)
            .filter(models.ClubMember.club_id == models.Club.id)
            .exists()
        )
        .order_by(func.random())
        .limit(1)
        .first()
    )


def get_random_collection(db: Session) -> Optional[models.Collection]:
    """Random collection with at least one accepted post (so the random link
    isn't a dead-end to an empty page)."""
    return (
        db.query(models.Collection)
        .options(joinedload(models.Collection.owner))
        .filter(
            db.query(models.CollectionPost.id)
            .filter(
                models.CollectionPost.collection_id == models.Collection.id,
                models.CollectionPost.status == "accepted",
            )
            .exists()
        )
        .order_by(func.random())
        .limit(1)
        .first()
    )


def count_club_members(db: Session, club_id: int) -> int:
    return db.query(models.ClubMember).filter(models.ClubMember.club_id == club_id).count()


def get_club_membership(db: Session, club_id: int, user_id: int) -> Optional[models.ClubMember]:
    return db.query(models.ClubMember).filter(
        models.ClubMember.club_id == club_id,
        models.ClubMember.user_id == user_id,
    ).first()


def list_club_members(db: Session, club_id: int) -> List[models.ClubMember]:
    role_priority = case(
        (models.ClubMember.role == "owner", 0),
        (models.ClubMember.role == "admin", 1),
        else_=2,
    )
    return (
        db.query(models.ClubMember)
        .options(joinedload(models.ClubMember.user))
        .filter(models.ClubMember.club_id == club_id)
        .order_by(role_priority.asc(), models.ClubMember.joined_at.asc())
        .all()
    )


def count_member_contributions(db: Session, club_id: int, user_id: int) -> int:
    return (
        db.query(models.ClubBoardMessage)
        .filter(
            models.ClubBoardMessage.club_id == club_id,
            models.ClubBoardMessage.author_id == user_id,
        )
        .count()
    )


def create_club(db: Session, owner: models.User, data: schemas.ClubCreate) -> models.Club:
    if data.speciality not in CLUB_VALID_SPECIALITIES:
        raise ValueError("speciality_invalid")
    base_slug = _generate_club_slug(data.title)
    slug = _ensure_unique_club_slug(db, base_slug)
    club = models.Club(
        owner_id=owner.id,
        title=data.title.strip(),
        slug=slug,
        description=(data.description or "").strip() or None,
        motto=(data.motto or "").strip() or None,
        avatar_seed=(data.avatar_seed or "").strip() or None,
        theme=(data.theme or "").strip() or None,
        speciality=data.speciality,
    )
    db.add(club)
    db.flush()
    db.add(models.ClubMember(club_id=club.id, user_id=owner.id, role="owner"))
    db.commit()
    db.refresh(club)
    return club


def update_club(db: Session, club_id: int, data: schemas.ClubUpdate) -> Optional[models.Club]:
    club = get_club(db, club_id)
    if not club:
        return None
    payload = data.model_dump(exclude_unset=True)
    if "title" in payload and payload["title"]:
        club.title = payload["title"].strip()
    if "speciality" in payload and payload["speciality"]:
        if payload["speciality"] not in CLUB_VALID_SPECIALITIES:
            raise ValueError("speciality_invalid")
        club.speciality = payload["speciality"]
    for field in ("description", "motto", "avatar_seed", "theme"):
        if field in payload:
            value = payload[field]
            setattr(club, field, value.strip() if isinstance(value, str) and value.strip() else None)
    db.commit()
    db.refresh(club)
    return club


def delete_club(db: Session, club_id: int) -> bool:
    club = get_club(db, club_id)
    if not club:
        return False
    db.delete(club)
    db.commit()
    return True


def _has_pending_request(db: Session, club_id: int, user_id: int) -> bool:
    return db.query(models.ClubJoinRequest).filter(
        models.ClubJoinRequest.club_id == club_id,
        models.ClubJoinRequest.user_id == user_id,
        models.ClubJoinRequest.status == "pending",
    ).first() is not None


def get_user_pending_request(db: Session, club_id: int, user_id: int) -> Optional[models.ClubJoinRequest]:
    return db.query(models.ClubJoinRequest).filter(
        models.ClubJoinRequest.club_id == club_id,
        models.ClubJoinRequest.user_id == user_id,
        models.ClubJoinRequest.status == "pending",
    ).first()


def apply_to_club(
    db: Session, applicant: models.User, club: models.Club
) -> tuple[Optional[models.ClubJoinRequest], Optional[str]]:
    if applicant.is_suspended:
        return None, "suspended"
    if get_club_membership(db, club.id, applicant.id):
        return None, "already_member"
    if _has_pending_request(db, club.id, applicant.id):
        return None, "already_pending"
    request = models.ClubJoinRequest(
        club_id=club.id,
        user_id=applicant.id,
        direction="application",
        status="pending",
        initiator_id=applicant.id,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    _notify_club_application_to_admins(db, club, applicant, request)
    return request, None


def invite_to_club(
    db: Session, inviter: models.User, club: models.Club, target: models.User
) -> tuple[Optional[models.ClubJoinRequest], Optional[str]]:
    inviter_membership = get_club_membership(db, club.id, inviter.id)
    if not inviter_membership or inviter_membership.role not in ("owner", "admin"):
        return None, "not_allowed"
    if target.is_suspended:
        return None, "target_suspended"
    if get_club_membership(db, club.id, target.id):
        return None, "already_member"
    if _has_pending_request(db, club.id, target.id):
        return None, "already_pending"
    request = models.ClubJoinRequest(
        club_id=club.id,
        user_id=target.id,
        direction="invitation",
        status="pending",
        initiator_id=inviter.id,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    _notify_club_invitation_to_target(db, club, inviter, target, request)
    return request, None


def respond_to_club_request(
    db: Session,
    request: models.ClubJoinRequest,
    responder: models.User,
    action: str,
) -> tuple[Optional[models.ClubJoinRequest], Optional[str]]:
    if action not in ("approve", "reject"):
        return None, "bad_action"
    if request.status != "pending":
        return None, "not_pending"

    club = request.club

    # For applications: counterparty is owner/admin of the club.
    # For invitations: counterparty is the invited user themselves.
    if request.direction == "application":
        membership = get_club_membership(db, club.id, responder.id)
        if not membership or membership.role not in ("owner", "admin"):
            return None, "not_allowed"
    elif request.direction == "invitation":
        if responder.id != request.user_id:
            return None, "not_allowed"
    else:
        return None, "inconsistent_direction"

    if action == "approve":
        # If they happen to already be a member (race), just close the request.
        if not get_club_membership(db, club.id, request.user_id):
            db.add(models.ClubMember(
                club_id=club.id,
                user_id=request.user_id,
                role="member",
            ))
        request.status = "approved"
    else:
        request.status = "rejected"

    request.responded_at = utcnow_naive()
    request.responded_by = responder.id
    db.commit()
    db.refresh(request)
    _notify_club_request_outcome(db, request, action, responder)
    return request, None


def kick_member(
    db: Session, actor: models.User, club: models.Club, target_user_id: int
) -> tuple[bool, Optional[str]]:
    """Remove a member from a club.

    Permission rules:
      - Owner can kick anyone except themselves (must delete club to leave).
      - Admin can kick role="member" only.
      - Any user can leave (kick themselves) unless they are the owner.
    """
    actor_membership = get_club_membership(db, club.id, actor.id)
    target_membership = get_club_membership(db, club.id, target_user_id)
    if not target_membership:
        return False, "not_member"

    is_self = actor.id == target_user_id
    actor_role = actor_membership.role if actor_membership else None
    target_role = target_membership.role

    if is_self:
        if target_role == "owner":
            return False, "owner_cannot_leave"
    else:
        if actor_role == "owner":
            if target_role == "owner":
                return False, "cannot_kick_self"
        elif actor_role == "admin":
            if target_role != "member":
                return False, "not_allowed"
        else:
            return False, "not_allowed"

    db.delete(target_membership)
    db.commit()
    if not is_self:
        create_notification(
            db=db,
            user_id=target_user_id,
            notif_type="club_kicked",
            title="Ai fost scos dintr-un club",
            message=f"Nu mai faci parte din clubul „{club.title}\".",
            link=f"/cluburi/{club.slug}",
            extra_data={"club_id": club.id, "club_slug": club.slug},
        )
    return True, None


def update_member_role(
    db: Session,
    actor: models.User,
    club: models.Club,
    target_user_id: int,
    role: str,
) -> tuple[Optional[models.ClubMember], Optional[str]]:
    if role not in ("admin", "member"):
        return None, "bad_role"
    if club.owner_id != actor.id:
        return None, "not_allowed"
    if target_user_id == actor.id:
        return None, "cannot_change_own_role"
    membership = get_club_membership(db, club.id, target_user_id)
    if not membership:
        return None, "not_member"
    if membership.role == "owner":
        return None, "cannot_change_owner_role"
    if membership.role == role:
        return membership, None
    membership.role = role
    db.commit()
    db.refresh(membership)
    create_notification(
        db=db,
        user_id=target_user_id,
        notif_type="club_role_changed",
        title="Rolul tău în club s-a schimbat",
        message=(
            f"Ai fost numit administrator în clubul „{club.title}\"."
            if role == "admin"
            else f"Nu mai ești administrator în clubul „{club.title}\"."
        ),
        link=f"/cluburi/{club.slug}",
        extra_data={"club_id": club.id, "club_slug": club.slug, "role": role},
    )
    return membership, None


def set_featured_post(
    db: Session, actor: models.User, club: models.Club, post_id: int
) -> tuple[Optional[models.Post], Optional[str]]:
    if club.owner_id != actor.id:
        return None, "not_allowed"
    post = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
        models.Post.id == post_id
    ).first()
    if not post:
        return None, "post_not_found"
    if post.moderation_status != "approved":
        return None, "post_not_approved"
    if post.category != club.speciality:
        return None, "speciality_mismatch"
    if not get_club_membership(db, club.id, post.user_id):
        return None, "author_not_member"
    club.featured_post_id = post.id
    club.featured_until = utcnow_naive() + CLUB_FEATURED_DURATION
    db.commit()
    db.refresh(club)
    if post.user_id != actor.id:
        create_notification(
            db=db,
            user_id=post.user_id,
            notif_type="club_featured",
            title="Postarea ta este creația săptămânii",
            message=(
                f"Postarea „{post.title}\" a fost aleasă creația săptămânii "
                f"în clubul „{club.title}\"."
            ),
            link=f"/cluburi/{club.slug}",
            extra_data={"club_id": club.id, "club_slug": club.slug, "post_id": post.id},
        )
    return post, None


def clear_featured_post(db: Session, actor: models.User, club: models.Club) -> tuple[bool, Optional[str]]:
    if club.owner_id != actor.id:
        return False, "not_allowed"
    club.featured_post_id = None
    club.featured_until = None
    db.commit()
    return True, None


def get_active_featured(db: Session, club: models.Club):
    """Return (post, featured_until) if a featured post is currently active.

    Implements read-time expiry: if featured_until is in the past, lazily
    clear the columns and return None.
    """
    if not club.featured_post_id or not club.featured_until:
        return None
    if club.featured_until <= utcnow_naive():
        # Best-effort cleanup; don't block the read on the write.
        try:
            club.featured_post_id = None
            club.featured_until = None
            db.commit()
        except Exception:
            db.rollback()
        return None
    post = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
        models.Post.id == club.featured_post_id
    ).first()
    if not post:
        return None
    return post, club.featured_until


def list_board_messages(
    db: Session, club_id: int, *, limit: int = 50, offset: int = 0
) -> List[models.ClubBoardMessage]:
    """Return top-level messages newest-first; replies eager-loaded per message."""
    top_level = (
        db.query(models.ClubBoardMessage)
        .options(
            joinedload(models.ClubBoardMessage.author),
            joinedload(models.ClubBoardMessage.replies).joinedload(models.ClubBoardMessage.author),
        )
        .filter(
            models.ClubBoardMessage.club_id == club_id,
            models.ClubBoardMessage.parent_id.is_(None),
        )
        .order_by(models.ClubBoardMessage.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return top_level


def get_board_message(db: Session, message_id: int) -> Optional[models.ClubBoardMessage]:
    return (
        db.query(models.ClubBoardMessage)
        .options(joinedload(models.ClubBoardMessage.author))
        .filter(models.ClubBoardMessage.id == message_id)
        .first()
    )


def post_board_message(
    db: Session,
    author: models.User,
    club: models.Club,
    content: str,
    parent_id: Optional[int] = None,
) -> tuple[Optional[models.ClubBoardMessage], Optional[str]]:
    if not get_club_membership(db, club.id, author.id):
        return None, "not_member"
    if parent_id is not None:
        parent = get_board_message(db, parent_id)
        if not parent or parent.club_id != club.id:
            return None, "bad_parent"
        # Don't allow nesting beyond one level — replies-of-replies are flattened
        # to siblings of the original reply (frontend renders as a single thread).
        if parent.parent_id is not None:
            parent_id = parent.parent_id
    msg = models.ClubBoardMessage(
        club_id=club.id,
        author_id=author.id,
        parent_id=parent_id,
        content=content.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg, None


def delete_board_message(
    db: Session, actor: models.User, message: models.ClubBoardMessage
) -> tuple[bool, Optional[str]]:
    if actor.id == message.author_id:
        allowed = True
    else:
        membership = get_club_membership(db, message.club_id, actor.id)
        allowed = bool(membership and membership.role in ("owner", "admin"))
    if not allowed:
        return False, "not_allowed"
    db.delete(message)
    db.commit()
    return True, None


def list_user_clubs(db: Session, user_id: int) -> List[models.Club]:
    """All clubs the user belongs to (any role)."""
    return (
        db.query(models.Club)
        .options(joinedload(models.Club.owner))
        .join(models.ClubMember, models.ClubMember.club_id == models.Club.id)
        .filter(models.ClubMember.user_id == user_id)
        .order_by(models.Club.created_at.desc())
        .all()
    )


def list_user_pending_invitations(db: Session, user_id: int) -> List[models.ClubJoinRequest]:
    return (
        db.query(models.ClubJoinRequest)
        .options(
            joinedload(models.ClubJoinRequest.club).joinedload(models.Club.owner),
            joinedload(models.ClubJoinRequest.user),
        )
        .filter(
            models.ClubJoinRequest.user_id == user_id,
            models.ClubJoinRequest.status == "pending",
            models.ClubJoinRequest.direction == "invitation",
        )
        .order_by(models.ClubJoinRequest.created_at.desc())
        .all()
    )


def list_club_pending_requests(db: Session, club_id: int) -> List[models.ClubJoinRequest]:
    return (
        db.query(models.ClubJoinRequest)
        .options(
            joinedload(models.ClubJoinRequest.user),
            joinedload(models.ClubJoinRequest.initiator),
        )
        .filter(
            models.ClubJoinRequest.club_id == club_id,
            models.ClubJoinRequest.status == "pending",
        )
        .order_by(models.ClubJoinRequest.created_at.desc())
        .all()
    )


def get_club_join_request(db: Session, request_id: int) -> Optional[models.ClubJoinRequest]:
    return (
        db.query(models.ClubJoinRequest)
        .options(
            joinedload(models.ClubJoinRequest.club),
            joinedload(models.ClubJoinRequest.user),
            joinedload(models.ClubJoinRequest.initiator),
        )
        .filter(models.ClubJoinRequest.id == request_id)
        .first()
    )


def count_pending_requests_for_club(db: Session, club_id: int) -> int:
    return (
        db.query(models.ClubJoinRequest)
        .filter(
            models.ClubJoinRequest.club_id == club_id,
            models.ClubJoinRequest.status == "pending",
        )
        .count()
    )


# ----- club notification helpers -----

def _notify_club_application_to_admins(
    db: Session,
    club: models.Club,
    applicant: models.User,
    request: models.ClubJoinRequest,
) -> None:
    admin_memberships = (
        db.query(models.ClubMember)
        .filter(
            models.ClubMember.club_id == club.id,
            models.ClubMember.role.in_(("owner", "admin")),
        )
        .all()
    )
    for m in admin_memberships:
        if m.user_id == applicant.id:
            continue
        create_notification(
            db=db,
            user_id=m.user_id,
            notif_type="club_application_received",
            title="Cerere de aderare la club",
            message=f"{applicant.username} dorește să se alăture clubului „{club.title}\".",
            link=f"/cluburi/{club.slug}",
            extra_data={
                "club_id": club.id,
                "club_slug": club.slug,
                "request_id": request.id,
                "applicant_username": applicant.username,
            },
        )


def _notify_club_invitation_to_target(
    db: Session,
    club: models.Club,
    inviter: models.User,
    target: models.User,
    request: models.ClubJoinRequest,
) -> None:
    create_notification(
        db=db,
        user_id=target.id,
        notif_type="club_invitation_received",
        title="Invitație într-un club",
        message=f"{inviter.username} te-a invitat în clubul „{club.title}\".",
        link=f"/cluburi/{club.slug}",
        extra_data={
            "club_id": club.id,
            "club_slug": club.slug,
            "request_id": request.id,
            "inviter_username": inviter.username,
        },
    )


def _notify_club_request_outcome(
    db: Session,
    request: models.ClubJoinRequest,
    action: str,
    responder: models.User,
) -> None:
    club = request.club
    # Notify the user who initiated the request.
    target_user_id = request.initiator_id
    if request.direction == "application":
        if action == "approve":
            title = "Cererea ta a fost acceptată"
            message = f"Faci acum parte din clubul „{club.title}\"."
            notif_type = "club_application_approved"
        else:
            title = "Cererea ta a fost respinsă"
            message = f"Cererea ta către clubul „{club.title}\" a fost respinsă."
            notif_type = "club_application_rejected"
    else:  # invitation
        # For invitations, notify the original inviter about the invitee's decision.
        if action == "approve":
            title = "Invitație acceptată"
            message = f"{request.user.username} s-a alăturat clubului „{club.title}\"."
            notif_type = "club_invitation_accepted"
        else:
            title = "Invitație refuzată"
            message = f"{request.user.username} a refuzat invitația în clubul „{club.title}\"."
            notif_type = "club_invitation_declined"

    create_notification(
        db=db,
        user_id=target_user_id,
        notif_type=notif_type,
        title=title,
        message=message,
        link=f"/cluburi/{club.slug}",
        extra_data={
            "club_id": club.id,
            "club_slug": club.slug,
            "request_id": request.id,
        },
    )
