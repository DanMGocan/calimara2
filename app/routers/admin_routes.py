import logging
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from .. import admin, crud, models, schemas, statistics
from ..database import get_db
from ..week_util import utcnow_naive

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

CONTENT_TYPES = {"post", "comment", "audio", "forum_thread", "forum_reply"}
CONTENT_STATUSES = {"approved", "pending", "flagged", "rejected"}
PREMIUM_TIERS = {"free", "trubadur", "cronicar", "rapsod"}


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Format dată invalid: {value}. Folosiți YYYY-MM-DD.")


def _date_filters(column, from_date: Optional[date], to_date: Optional[date]) -> list:
    filters = []
    if from_date:
        filters.append(column >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        filters.append(column < datetime.combine(to_date + timedelta(days=1), datetime.min.time()))
    return filters


def _audit(
    db: Session,
    request: Optional[Request],
    actor: models.User,
    *,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[models.AdminAuditLog]:
    return admin.write_admin_audit_log(
        db,
        actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        request=request,
        extra_data=metadata,
    )


def _admin_count(db: Session) -> int:
    return db.query(models.User).filter(models.User.is_admin == True).count()


def _ensure_not_self(actor: models.User, target: models.User, action: str) -> None:
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail=f"Nu poți executa această acțiune asupra propriului cont: {action}.")


def _ensure_can_remove_admin(db: Session, target: models.User) -> None:
    if target.is_admin and _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Nu poți modifica ultimul administrator.")


def _as_iso(value):
    return value.isoformat() if value else None


def _user_payload(db: Session, user: models.User, include_counts: bool = False) -> dict:
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "is_moderator": user.is_moderator,
        "is_suspended": user.is_suspended,
        "suspension_reason": user.suspension_reason,
        "suspended_at": _as_iso(user.suspended_at),
        "suspended_by": user.suspended_by,
        "premium_tier": user.premium_tier,
        "premium_period_start": _as_iso(user.premium_period_start),
        "premium_until": _as_iso(user.premium_until),
        "is_premium": user.is_premium,
        "stripe_customer_id": user.stripe_customer_id,
        "stripe_subscription_id": user.stripe_subscription_id,
        "gologani_balance": user.gologani_balance,
        "seconds_listened": user.seconds_listened or 0,
        "created_at": _as_iso(user.created_at),
        "updated_at": _as_iso(user.updated_at),
    }
    if include_counts:
        payload["counts"] = {
            "posts": db.query(models.Post).filter(models.Post.user_id == user.id).count(),
            "comments": db.query(models.Comment).filter(models.Comment.user_id == user.id).count(),
            "forum_threads": db.query(models.ForumThread).filter(models.ForumThread.author_id == user.id).count(),
            "forum_replies": db.query(models.ForumReply).filter(models.ForumReply.author_id == user.id).count(),
            "super_likes_given": db.query(models.SuperLike).filter(models.SuperLike.user_id == user.id).count(),
            "inventory_items": db.query(models.UserInventoryItem).filter(models.UserInventoryItem.user_id == user.id).count(),
        }
    return payload


def _audit_payload(log: models.AdminAuditLog) -> dict:
    return {
        "id": log.id,
        "actor_user_id": log.actor_user_id,
        "actor_username": log.actor_username,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "reason": log.reason,
        "ip_address": log.ip_address,
        "metadata": log.extra_data or {},
        "created_at": _as_iso(log.created_at),
    }


def _admin_daily_metrics_available(db: Session) -> bool:
    if admin.db_table_exists(db, models.AdminDailyMetric.__tablename__):
        return True
    admin.warn_missing_table_once(
        models.AdminDailyMetric.__tablename__,
        "admin daily metrics are returned empty and rollups are computed without persistence",
    )
    return False


def _admin_audit_logs_available(db: Session) -> bool:
    if admin.db_table_exists(db, models.AdminAuditLog.__tablename__):
        return True
    admin.warn_missing_table_once(
        models.AdminAuditLog.__tablename__,
        "admin audit history is returned empty and new audit entries are skipped",
    )
    return False


def _job_payload(job: models.AIJob) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "target_type": job.target_type,
        "target_id": job.target_id,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "run_after": _as_iso(job.run_after),
        "locked_at": _as_iso(job.locked_at),
        "locked_by": job.locked_by,
        "error_message": job.error_message,
        "created_at": _as_iso(job.created_at),
        "updated_at": _as_iso(job.updated_at),
    }


def _content_payload(item, content_type: str) -> dict:
    if content_type == "post":
        return {
            "id": item.id,
            "type": "post",
            "title": item.title,
            "content": item.content,
            "author": item.owner.username if item.owner else None,
            "author_id": item.user_id,
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "category": item.category,
            "views": item.view_count,
            "seconds_listened": item.seconds_listened or 0,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    if content_type == "comment":
        return {
            "id": item.id,
            "type": "comment",
            "title": item.post.title if item.post else "Comentariu",
            "content": item.content,
            "author": item.commenter.username if item.commenter else (item.author_name or "Anonim"),
            "author_id": item.user_id,
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "post_id": item.post_id,
            "created_at": _as_iso(item.created_at),
            "updated_at": None,
        }
    if content_type == "audio":
        return {
            "id": item.id,
            "type": "audio",
            "title": item.post.title if item.post else "Audio",
            "content": item.transcript or item.moderation_reason or "",
            "author": item.post.owner.username if item.post and item.post.owner else None,
            "author_id": item.post.user_id if item.post else None,
            "status": item.status,
            "reason": item.moderation_reason,
            "toxicity_score": None,
            "post_id": item.post_id,
            "source": item.source,
            "duration_seconds": item.duration_seconds,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    if content_type == "forum_thread":
        return {
            "id": item.id,
            "type": "forum_thread",
            "title": item.title,
            "content": item.content,
            "author": item.author.username if item.author else None,
            "author_id": item.author_id,
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "section": item.section,
            "views": item.view_count,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    return {
        "id": item.id,
        "type": "forum_reply",
        "title": item.thread.title if item.thread else "Răspuns pe forum",
        "content": item.content,
        "author": item.author.username if item.author else None,
        "author_id": item.author_id,
        "status": item.moderation_status,
        "reason": item.moderation_reason,
        "toxicity_score": item.toxicity_score,
        "thread_id": item.thread_id,
        "created_at": _as_iso(item.created_at),
        "updated_at": _as_iso(item.updated_at),
    }


def _content_object(db: Session, content_type: str, content_id: int):
    if content_type == "post":
        return db.query(models.Post).options(joinedload(models.Post.owner)).filter(models.Post.id == content_id).first()
    if content_type == "comment":
        return db.query(models.Comment).options(
            joinedload(models.Comment.commenter),
            joinedload(models.Comment.post),
        ).filter(models.Comment.id == content_id).first()
    if content_type == "audio":
        return db.query(models.PostAudio).options(
            joinedload(models.PostAudio.post).joinedload(models.Post.owner)
        ).filter(models.PostAudio.id == content_id).first()
    if content_type == "forum_thread":
        return db.query(models.ForumThread).options(joinedload(models.ForumThread.author)).filter(models.ForumThread.id == content_id).first()
    if content_type == "forum_reply":
        return db.query(models.ForumReply).options(
            joinedload(models.ForumReply.author),
            joinedload(models.ForumReply.thread),
        ).filter(models.ForumReply.id == content_id).first()
    return None


def _count_by_status(db: Session, model, column) -> dict:
    rows = db.query(column, func.count()).group_by(column).all()
    return {str(status or "unknown"): count for status, count in rows}


def _premium_filter():
    return and_(models.User.premium_until != None, models.User.premium_until > utcnow_naive())


def _metric_counts_for_day(db: Session, target_date: date) -> dict:
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    day_filter_user = [models.User.created_at >= start, models.User.created_at < end]
    day_filter_post = [models.Post.created_at >= start, models.Post.created_at < end]
    day_filter_comment = [models.Comment.created_at >= start, models.Comment.created_at < end]
    day_filter_views = [models.PageView.created_at >= start, models.PageView.created_at < end]
    day_filter_listens = [models.AudioListenEvent.created_at >= start, models.AudioListenEvent.created_at < end]
    day_filter_jobs = [models.AIJob.created_at >= start, models.AIJob.created_at < end]

    issued = db.query(func.coalesce(func.sum(models.GologaniTransaction.amount), 0)).filter(
        models.GologaniTransaction.amount > 0,
        models.GologaniTransaction.created_at >= start,
        models.GologaniTransaction.created_at < end,
    ).scalar()
    spent = db.query(func.coalesce(func.sum(models.GologaniTransaction.amount), 0)).filter(
        models.GologaniTransaction.amount < 0,
        models.GologaniTransaction.created_at >= start,
        models.GologaniTransaction.created_at < end,
    ).scalar()

    return {
        "new_users": db.query(models.User).filter(*day_filter_user).count(),
        "new_posts": db.query(models.Post).filter(*day_filter_post).count(),
        "new_comments": db.query(models.Comment).filter(*day_filter_comment).count(),
        "page_views": db.query(models.PageView).filter(*day_filter_views).count(),
        "seconds_listened": int(db.query(func.coalesce(func.sum(models.AudioListenEvent.seconds), 0)).filter(*day_filter_listens).scalar() or 0),
        "unique_views": db.query(models.PageView).filter(
            *day_filter_views,
            models.PageView.is_bot == False,
            models.PageView.is_duplicate == False,
        ).count(),
        "bot_views": db.query(models.PageView).filter(*day_filter_views, models.PageView.is_bot == True).count(),
        "likes": db.query(models.Like).filter(models.Like.created_at >= start, models.Like.created_at < end).count(),
        "super_likes": db.query(models.SuperLike).filter(models.SuperLike.created_at >= start, models.SuperLike.created_at < end).count(),
        "shop_purchases": db.query(models.UserInventoryItem).filter(models.UserInventoryItem.purchased_at >= start, models.UserInventoryItem.purchased_at < end).count(),
        "gologani_issued": int(issued or 0),
        "gologani_spent": abs(int(spent or 0)),
        "ai_jobs_created": db.query(models.AIJob).filter(*day_filter_jobs).count(),
        "ai_jobs_failed": db.query(models.AIJob).filter(*day_filter_jobs, models.AIJob.status == "failed").count(),
    }


def aggregate_admin_daily_metrics(db: Session, target_date: date):
    metrics = _metric_counts_for_day(db, target_date)
    metrics.update({
        "total_users": db.query(models.User).count(),
        "active_premium_users": db.query(models.User).filter(_premium_filter()).count(),
        "total_posts": db.query(models.Post).count(),
        "approved_posts": db.query(models.Post).filter(models.Post.moderation_status == "approved").count(),
        "pending_moderation": crud.get_moderation_stats(db)["total_pending"],
        "flagged_moderation": crud.get_moderation_stats(db)["total_flagged"],
        "total_comments": db.query(models.Comment).count(),
        "total_seconds_listened": int(db.query(func.coalesce(func.sum(models.User.seconds_listened), 0)).scalar() or 0),
        "forum_threads": db.query(models.ForumThread).count(),
        "forum_replies": db.query(models.ForumReply).count(),
        "shop_items": db.query(models.ShopItem).count(),
        "ai_jobs_pending": db.query(models.AIJob).filter(models.AIJob.status == "pending").count(),
        "ai_jobs_failed_total": db.query(models.AIJob).filter(models.AIJob.status == "failed").count(),
    })
    if not _admin_daily_metrics_available(db):
        return SimpleNamespace(id=None, stat_date=target_date, metrics=metrics)
    row = db.query(models.AdminDailyMetric).filter(models.AdminDailyMetric.stat_date == target_date).first()
    if row:
        row.metrics = metrics
    else:
        row = models.AdminDailyMetric(stat_date=target_date, metrics=metrics)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/overview")
def admin_overview(
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    start = _parse_date(from_date)
    end = _parse_date(to_date)
    now = utcnow_naive()
    date_f_user = _date_filters(models.User.created_at, start, end)
    date_f_post = _date_filters(models.Post.created_at, start, end)
    date_f_comment = _date_filters(models.Comment.created_at, start, end)
    overview = statistics.get_overview_stats(db, start, end)
    moderation_stats = crud.get_moderation_stats(db)
    extended_moderation = crud.get_moderation_stats_extended(db)

    premium_by_tier = {
        tier: db.query(models.User).filter(_premium_filter(), models.User.premium_tier == tier).count()
        for tier in PREMIUM_TIERS
        if tier != "free"
    }
    jobs_by_status = _count_by_status(db, models.AIJob, models.AIJob.status)
    audio_by_status = _count_by_status(db, models.PostAudio, models.PostAudio.status)
    content_by_status = {
        "posts": _count_by_status(db, models.Post, models.Post.moderation_status),
        "comments": _count_by_status(db, models.Comment, models.Comment.moderation_status),
        "forum_threads": _count_by_status(db, models.ForumThread, models.ForumThread.moderation_status),
        "forum_replies": _count_by_status(db, models.ForumReply, models.ForumReply.moderation_status),
    }

    daily_metrics = []
    if _admin_daily_metrics_available(db):
        metric_query = db.query(models.AdminDailyMetric)
        if start:
            metric_query = metric_query.filter(models.AdminDailyMetric.stat_date >= start)
        if end:
            metric_query = metric_query.filter(models.AdminDailyMetric.stat_date <= end)
        daily_metrics = [
            {"date": row.stat_date.isoformat(), "metrics": row.metrics or {}}
            for row in metric_query.order_by(models.AdminDailyMetric.stat_date.desc()).limit(30).all()
        ]

    return {
        "cards": {
            "total_users": db.query(models.User).count(),
            "new_users": db.query(models.User).filter(*date_f_user).count(),
            "active_premium_users": db.query(models.User).filter(models.User.premium_until != None, models.User.premium_until > now).count(),
            "suspended_users": db.query(models.User).filter(models.User.is_suspended == True).count(),
            "total_posts": db.query(models.Post).count(),
            "new_posts": db.query(models.Post).filter(*date_f_post).count(),
            "total_comments": db.query(models.Comment).count(),
            "new_comments": db.query(models.Comment).filter(*date_f_comment).count(),
            "seconds_listened": int(db.query(func.coalesce(func.sum(models.AudioListenEvent.seconds), 0)).scalar() or 0),
            "pending_moderation": moderation_stats["total_pending"],
            "flagged_moderation": moderation_stats["total_flagged"],
            "failed_jobs": jobs_by_status.get("failed", 0),
            "shop_items": db.query(models.ShopItem).count(),
        },
        "traffic": overview,
        "moderation": {"basic": moderation_stats, "extended": extended_moderation, "content_by_status": content_by_status},
        "premium": {"by_tier": premium_by_tier},
        "jobs": {"by_status": jobs_by_status},
        "audio": {"by_status": audio_by_status},
        "economy": {
            "shop_items_active": db.query(models.ShopItem).filter(models.ShopItem.is_active == True).count(),
            "inventory_items": db.query(models.UserInventoryItem).count(),
            "gologani_balance_total": int(db.query(func.coalesce(func.sum(models.User.gologani_balance), 0)).scalar() or 0),
        },
        "daily_metrics": daily_metrics,
    }


@router.post("/metrics/rollup")
def rollup_admin_metrics(
    request: Request,
    target_date: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    parsed = _parse_date(target_date) or (date.today() - timedelta(days=1))
    row = aggregate_admin_daily_metrics(db, parsed)
    _audit(db, request, current_user, action="admin_metrics_rollup", target_type="admin_daily_metric", target_id=getattr(row, "id", None), metadata={"date": parsed.isoformat()})
    return {"date": row.stat_date.isoformat(), "metrics": row.metrics or {}, "persisted": getattr(row, "id", None) is not None}


@router.get("/users")
def list_admin_users(
    q: str = "",
    role: str = "all",
    status_filter: str = Query("all", alias="status"),
    premium: str = "all",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    query = db.query(models.User)
    term = q.strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(models.User.username.ilike(like), models.User.email.ilike(like)))
    if role == "admin":
        query = query.filter(models.User.is_admin == True)
    elif role == "moderator":
        query = query.filter(models.User.is_moderator == True, models.User.is_admin == False)
    elif role == "member":
        query = query.filter(models.User.is_admin == False, models.User.is_moderator == False)
    if status_filter == "suspended":
        query = query.filter(models.User.is_suspended == True)
    elif status_filter == "active":
        query = query.filter(models.User.is_suspended == False)
    if premium in PREMIUM_TIERS and premium != "all":
        if premium == "free":
            query = query.filter(or_(models.User.premium_until == None, models.User.premium_until <= utcnow_naive()))
        else:
            query = query.filter(_premium_filter(), models.User.premium_tier == premium)
    total = query.count()
    users = query.order_by(models.User.created_at.desc(), models.User.id.desc()).offset(offset).limit(limit).all()
    return {"users": [_user_payload(db, user, include_counts=True) for user in users], "total": total}


@router.get("/users/{user_id}")
def get_admin_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    recent_posts = db.query(models.Post).filter(models.Post.user_id == user.id).order_by(models.Post.created_at.desc()).limit(10).all()
    transactions = db.query(models.GologaniTransaction).filter(models.GologaniTransaction.user_id == user.id).order_by(models.GologaniTransaction.created_at.desc()).limit(20).all()
    audits = []
    if _admin_audit_logs_available(db):
        audits = db.query(models.AdminAuditLog).filter(models.AdminAuditLog.target_type == "user", models.AdminAuditLog.target_id == user.id).order_by(models.AdminAuditLog.created_at.desc()).limit(20).all()
    return {
        "user": _user_payload(db, user, include_counts=True),
        "recent_posts": [_content_payload(post, "post") for post in recent_posts],
        "transactions": [
            {
                "id": tx.id,
                "amount": tx.amount,
                "balance_after": tx.balance_after,
                "event_type": tx.event_type,
                "description": tx.description,
                "created_at": _as_iso(tx.created_at),
            }
            for tx in transactions
        ],
        "audit": [_audit_payload(log) for log in audits],
    }


@router.put("/users/{user_id}/roles")
def update_admin_user_roles(
    user_id: int,
    data: schemas.AdminRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    if user.is_admin and not data.is_admin:
        _ensure_can_remove_admin(db, user)
    if current_user.id == user.id and not data.is_admin:
        raise HTTPException(status_code=400, detail="Nu îți poți elimina propriul rol de administrator.")
    before = {"is_admin": user.is_admin, "is_moderator": user.is_moderator}
    user.is_admin = data.is_admin
    user.is_moderator = data.is_moderator or data.is_admin
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_roles_update", target_type="user", target_id=user.id, reason=data.reason, metadata={"before": before, "after": {"is_admin": user.is_admin, "is_moderator": user.is_moderator}})
    return _user_payload(db, user, include_counts=True)


@router.post("/users/{user_id}/suspend")
def suspend_admin_user(
    user_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    _ensure_not_self(current_user, user, "suspendare")
    _ensure_can_remove_admin(db, user)
    user.is_suspended = True
    user.suspension_reason = data.reason
    user.suspended_at = utcnow_naive()
    user.suspended_by = current_user.id
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_suspend", target_type="user", target_id=user.id, reason=data.reason)
    return _user_payload(db, user, include_counts=True)


@router.post("/users/{user_id}/reactivate")
def reactivate_admin_user(
    user_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    user.is_suspended = False
    user.suspension_reason = None
    user.suspended_at = None
    user.suspended_by = None
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_reactivate", target_type="user", target_id=user.id, reason=data.reason)
    return _user_payload(db, user, include_counts=True)


@router.put("/users/{user_id}/premium")
def update_admin_user_premium(
    user_id: int,
    data: schemas.AdminPremiumUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    before = {
        "premium_tier": user.premium_tier,
        "premium_until": _as_iso(user.premium_until),
        "stripe_subscription_id": user.stripe_subscription_id,
    }
    if data.premium_tier == "free":
        user.premium_tier = "free"
        user.premium_period_start = None
        user.premium_until = None
        user.stripe_subscription_id = None
    else:
        user.premium_tier = data.premium_tier
        user.premium_period_start = data.premium_period_start or user.premium_period_start or utcnow_naive()
        user.premium_until = data.premium_until or (utcnow_naive() + timedelta(days=30))
        if data.stripe_subscription_id is not None:
            user.stripe_subscription_id = data.stripe_subscription_id
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_premium_update", target_type="user", target_id=user.id, reason=data.reason, metadata={"before": before, "after": {"premium_tier": user.premium_tier, "premium_until": _as_iso(user.premium_until), "stripe_subscription_id": user.stripe_subscription_id}})
    return _user_payload(db, user, include_counts=True)


@router.post("/users/{user_id}/gologani-adjustments")
def adjust_admin_user_gologani(
    user_id: int,
    data: schemas.AdminGologaniAdjustment,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    tx = crud.grant_gologani(
        db,
        user_id=user.id,
        amount=data.amount,
        event_type="admin_adjustment",
        idempotency_key=f"admin-adjustment:{current_user.id}:{user.id}:{uuid4()}",
        source_type="admin",
        source_id=current_user.id,
        description=data.reason,
        extra_data={"admin_username": current_user.username},
    )
    db.refresh(user)
    _audit(db, request, current_user, action="user_gologani_adjust", target_type="user", target_id=user.id, reason=data.reason, metadata={"amount": data.amount, "transaction_id": tx.id if tx else None})
    return {"user": _user_payload(db, user, include_counts=True), "transaction_id": tx.id if tx else None}


@router.delete("/users/{user_id}")
def delete_admin_user(
    user_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    _ensure_not_self(current_user, user, "ștergere")
    _ensure_can_remove_admin(db, user)
    metadata = {"username": user.username, "email": user.email}
    db.delete(user)
    db.commit()
    _audit(db, request, current_user, action="user_delete", target_type="user", target_id=user_id, reason=data.reason, metadata=metadata)
    return {"success": True}


@router.get("/content")
def list_admin_content(
    content_type: str = "all",
    status_filter: str = Query("all", alias="status"),
    q: str = "",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if content_type != "all" and content_type not in CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Tip de conținut invalid")
    if status_filter != "all" and status_filter not in CONTENT_STATUSES and status_filter not in {"ready", "failed", "processing", "cancelled"}:
        raise HTTPException(status_code=400, detail="Status invalid")
    term = q.strip()
    items = []

    def add_rows(rows, kind):
        items.extend(_content_payload(row, kind) for row in rows)

    if content_type in {"all", "post"}:
        query = db.query(models.Post).options(joinedload(models.Post.owner))
        if status_filter != "all":
            query = query.filter(models.Post.moderation_status == status_filter)
        if term:
            like = f"%{term}%"
            query = query.filter(or_(models.Post.title.ilike(like), models.Post.content.ilike(like)))
        add_rows(query.order_by(models.Post.created_at.desc()).limit(limit).offset(offset if content_type == "post" else 0).all(), "post")
    if content_type in {"all", "comment"}:
        query = db.query(models.Comment).options(joinedload(models.Comment.commenter), joinedload(models.Comment.post))
        if status_filter != "all":
            query = query.filter(models.Comment.moderation_status == status_filter)
        if term:
            query = query.filter(models.Comment.content.ilike(f"%{term}%"))
        add_rows(query.order_by(models.Comment.created_at.desc()).limit(limit).offset(offset if content_type == "comment" else 0).all(), "comment")
    if content_type in {"all", "audio"}:
        query = db.query(models.PostAudio).options(joinedload(models.PostAudio.post).joinedload(models.Post.owner))
        if status_filter != "all":
            query = query.filter(models.PostAudio.status == status_filter)
        if term:
            query = query.filter(models.PostAudio.transcript.ilike(f"%{term}%"))
        add_rows(query.order_by(models.PostAudio.created_at.desc()).limit(limit).offset(offset if content_type == "audio" else 0).all(), "audio")
    if content_type in {"all", "forum_thread"}:
        query = db.query(models.ForumThread).options(joinedload(models.ForumThread.author))
        if status_filter != "all":
            query = query.filter(models.ForumThread.moderation_status == status_filter)
        if term:
            like = f"%{term}%"
            query = query.filter(or_(models.ForumThread.title.ilike(like), models.ForumThread.content.ilike(like)))
        add_rows(query.order_by(models.ForumThread.created_at.desc()).limit(limit).offset(offset if content_type == "forum_thread" else 0).all(), "forum_thread")
    if content_type in {"all", "forum_reply"}:
        query = db.query(models.ForumReply).options(joinedload(models.ForumReply.author), joinedload(models.ForumReply.thread))
        if status_filter != "all":
            query = query.filter(models.ForumReply.moderation_status == status_filter)
        if term:
            query = query.filter(models.ForumReply.content.ilike(f"%{term}%"))
        add_rows(query.order_by(models.ForumReply.created_at.desc()).limit(limit).offset(offset if content_type == "forum_reply" else 0).all(), "forum_reply")

    items.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    if content_type == "all":
        items = items[offset:offset + limit]
    return {"content": items, "total": len(items)}


@router.get("/content/{content_type}/{content_id}")
def get_admin_content_detail(
    content_type: schemas.AdminContentType,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = _content_object(db, content_type, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    return _content_payload(item, content_type)


@router.put("/content/{content_type}/{content_id}")
def update_admin_content(
    content_type: schemas.AdminContentType,
    content_id: int,
    data: schemas.AdminContentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = _content_object(db, content_type, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    changed = {}
    for field in ("title", "content", "category", "section"):
        value = getattr(data, field)
        if value is not None and hasattr(item, field):
            changed[field] = {"before": getattr(item, field), "after": value}
            setattr(item, field, value)
    if data.moderation_status in {"approved", "rejected"}:
        db.commit()
        item = crud.approve_content(db, content_type, content_id, current_user.id, data.reason) if data.moderation_status == "approved" else crud.reject_content(db, content_type, content_id, current_user.id, data.reason)
    else:
        if data.moderation_status:
            if content_type == "audio":
                item.status = data.moderation_status
            elif hasattr(item, "moderation_status"):
                item.moderation_status = data.moderation_status
            if hasattr(item, "moderation_reason"):
                item.moderation_reason = data.reason
        db.commit()
        db.refresh(item)
    _audit(db, request, current_user, action="content_update", target_type=content_type, target_id=content_id, reason=data.reason, metadata={"changed": changed, "moderation_status": data.moderation_status})
    refreshed = _content_object(db, content_type, content_id)
    return _content_payload(refreshed, content_type)


@router.post("/content/{content_type}/{content_id}/moderate")
def moderate_admin_content(
    content_type: schemas.AdminContentType,
    content_id: int,
    data: schemas.ModerationActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if data.action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    result = crud.approve_content(db, content_type, content_id, current_user.id, data.reason) if data.action == "approve" else crud.reject_content(db, content_type, content_id, current_user.id, data.reason)
    if not result:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    _audit(db, request, current_user, action=f"content_{data.action}", target_type=content_type, target_id=content_id, reason=data.reason)
    return _content_payload(_content_object(db, content_type, content_id), content_type)


@router.delete("/content/{content_type}/{content_id}")
def delete_admin_content(
    content_type: schemas.AdminContentType,
    content_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = _content_object(db, content_type, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    snapshot = _content_payload(item, content_type)
    db.delete(item)
    db.commit()
    _audit(db, request, current_user, action="content_delete", target_type=content_type, target_id=content_id, reason=data.reason, metadata={"snapshot": {k: snapshot.get(k) for k in ("title", "author", "status")}})
    return {"success": True}


@router.get("/jobs")
def list_admin_jobs(
    status_filter: str = Query("all", alias="status"),
    job_type: str = "all",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    query = db.query(models.AIJob)
    if status_filter != "all":
        query = query.filter(models.AIJob.status == status_filter)
    if job_type != "all":
        query = query.filter(models.AIJob.job_type == job_type)
    total = query.count()
    jobs = query.order_by(models.AIJob.created_at.desc(), models.AIJob.id.desc()).offset(offset).limit(limit).all()
    return {"jobs": [_job_payload(job) for job in jobs], "total": total}


@router.post("/jobs/{job_id}/retry")
def retry_admin_job(
    job_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    job = db.query(models.AIJob).filter(models.AIJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Jobul nu a fost găsit")
    job.status = "pending"
    job.attempts = 0
    job.locked_at = None
    job.locked_by = None
    job.error_message = None
    job.run_after = utcnow_naive()
    db.commit()
    db.refresh(job)
    _audit(db, request, current_user, action="ai_job_retry", target_type="ai_job", target_id=job.id, reason=data.reason)
    return _job_payload(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_admin_job(
    job_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    job = db.query(models.AIJob).filter(models.AIJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Jobul nu a fost găsit")
    job.status = "cancelled"
    job.locked_at = None
    job.locked_by = None
    job.error_message = data.reason
    db.commit()
    db.refresh(job)
    _audit(db, request, current_user, action="ai_job_cancel", target_type="ai_job", target_id=job.id, reason=data.reason)
    return _job_payload(job)


@router.get("/audit-log")
def list_admin_audit_log(
    actor: str = "",
    action: str = "",
    target_type: str = "",
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if not _admin_audit_logs_available(db):
        return {"logs": [], "total": 0, "unavailable": True}
    query = db.query(models.AdminAuditLog)
    if actor:
        query = query.filter(models.AdminAuditLog.actor_username.ilike(f"%{actor.strip()}%"))
    if action:
        query = query.filter(models.AdminAuditLog.action == action)
    if target_type:
        query = query.filter(models.AdminAuditLog.target_type == target_type)
    total = query.count()
    logs = query.order_by(models.AdminAuditLog.created_at.desc(), models.AdminAuditLog.id.desc()).offset(offset).limit(limit).all()
    return {"logs": [_audit_payload(log) for log in logs], "total": total}
