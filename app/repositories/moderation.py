from ._shared import *
from .economy import award_content_approved
from .forum import _notify_forum_reply_approved
from .mentions import notify_mentions_for_comment, notify_mentions_for_forum_reply, notify_mentions_for_forum_thread
from .notifications import create_notification

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

        if not was_content_approved:
            if content_type == "comment":
                notify_mentions_for_comment(db, content)
            elif content_type == "forum_thread":
                notify_mentions_for_forum_thread(db, content)
            elif content_type == "forum_reply":
                notify_mentions_for_forum_reply(db, content)

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
# SERIES CRUD FUNCTIONS
# ===================================

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
