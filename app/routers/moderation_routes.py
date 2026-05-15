import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from .. import ai_queue, models, schemas, crud, admin, moderation
from ..database import get_db
from ..week_util import utcnow_naive

logger = logging.getLogger(__name__)

router = APIRouter(tags=["moderation"])


def _content_type_label(content_type: str) -> str:
    labels = {
        "post": "Postarea",
        "comment": "Comentariul",
        "audio": "Audio",
        "forum_thread": "Discuția",
        "forum_reply": "Răspunsul",
        "theatre_entry": "Textul de teatru",
        "stafeta_segment": "Contribuția din Ștafeta",
    }
    return labels.get(content_type, "Conținutul")


@router.get("/api/moderare/statistici")
def get_moderation_stats(
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get moderation statistics for dashboard"""
    # Set no-cache headers to prevent caching of dynamic data
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    try:
        # Use the new CRUD function to get comprehensive stats
        stats = crud.get_moderation_stats(db)

        suspended_users = db.query(models.User).filter(
            models.User.is_suspended == True
        ).count()

        today = utcnow_naive().date()
        today_actions = db.query(models.Post).filter(
            models.Post.moderated_at >= today
        ).count() + db.query(models.Comment).filter(
            models.Comment.moderated_at >= today
        ).count() + db.query(models.ForumThread).filter(
            models.ForumThread.moderated_at >= today
        ).count() + db.query(models.ForumReply).filter(
            models.ForumReply.moderated_at >= today
        ).count() + db.query(models.TheatreEntry).filter(
            models.TheatreEntry.moderated_at >= today
        ).count() + db.query(models.StafetaSegment).filter(
            models.StafetaSegment.moderated_at >= today
        ).count()

        return {
            "pending_count": stats['total_pending'],
            "flagged_count": stats['total_flagged'],
            "suspended_count": suspended_users,
            "today_actions": today_actions,
            "posts_pending": stats['posts_pending'],
            "posts_flagged": stats['posts_flagged'],
            "comments_pending": stats['comments_pending'],
            "comments_flagged": stats['comments_flagged'],
            "forum_threads_pending": stats['forum_threads_pending'],
            "forum_threads_flagged": stats['forum_threads_flagged'],
            "forum_replies_pending": stats['forum_replies_pending'],
            "forum_replies_flagged": stats['forum_replies_flagged'],
            "theatre_entries_pending": stats['theatre_entries_pending'],
            "theatre_entries_flagged": stats['theatre_entries_flagged'],
            "stafeta_segments_pending": stats['stafeta_segments_pending'],
            "stafeta_segments_flagged": stats['stafeta_segments_flagged'],
        }

    except Exception as e:
        logger.error(f"Eroare la obținerea statisticilor de moderare: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut încărca statisticile de moderare")


@router.get("/api/moderare/continut/in-asteptare")
def get_pending_content(
    request: Request,
    content_type: str = "all",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get content pending moderation - visible only to moderators"""
    try:
        if not current_user.is_moderator and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Acces de moderare necesar")

        content = []

        if content_type in ["all", "posts"]:
            posts = crud.get_posts_for_moderation(db, status_filter="pending", limit=50)

            for post in posts:
                content.append({
                    "id": post.id,
                    "type": "post",
                    "title": post.title,
                    "content": post.content,
                    "author": post.owner.username,
                    "toxicity_score": getattr(post, 'toxicity_score', 0.0),
                    "moderation_status": post.moderation_status,
                    "moderation_reason": getattr(post, 'moderation_reason', ''),
                    "created_at": post.created_at.isoformat()
                })

        if content_type in ["all", "comments"]:
            comments = crud.get_comments_for_moderation(db, status_filter="pending", limit=50)

            for comment in comments:
                author = comment.commenter.username if comment.commenter else comment.author_name
                content.append({
                    "id": comment.id,
                    "type": "comment",
                    "title": None,
                    "content": comment.content,
                    "author": author,
                    "toxicity_score": getattr(comment, 'toxicity_score', 0.0),
                    "moderation_status": comment.moderation_status,
                    "moderation_reason": getattr(comment, 'moderation_reason', ''),
                    "created_at": comment.created_at.isoformat()
                })

        if content_type in ["all", "forum_threads"]:
            threads = crud.get_forum_threads_for_moderation(db, status_filter="pending", limit=50)
            for thread in threads:
                content.append({
                    "id": thread.id,
                    "type": "forum_thread",
                    "title": thread.title,
                    "content": thread.content,
                    "author": thread.author.username if thread.author else "Necunoscut",
                    "toxicity_score": getattr(thread, "toxicity_score", 0.0) or 0.0,
                    "moderation_status": thread.moderation_status,
                    "moderation_reason": getattr(thread, "moderation_reason", ""),
                    "created_at": thread.created_at.isoformat()
                })

        if content_type in ["all", "forum_replies"]:
            replies = crud.get_forum_replies_for_moderation(db, status_filter="pending", limit=50)
            for reply in replies:
                content.append({
                    "id": reply.id,
                    "type": "forum_reply",
                    "title": reply.thread.title if reply.thread else None,
                    "content": reply.content,
                    "author": reply.author.username if reply.author else "Necunoscut",
                    "toxicity_score": getattr(reply, "toxicity_score", 0.0) or 0.0,
                    "moderation_status": reply.moderation_status,
                    "moderation_reason": getattr(reply, "moderation_reason", ""),
                    "created_at": reply.created_at.isoformat()
                })

        if content_type in ["all", "theatre_entries"]:
            entries = crud.list_theatre_entries_for_moderation(db, status_filter="pending", limit=50)
            for entry in entries:
                content.append({
                    "id": entry.id,
                    "type": "theatre_entry",
                    "title": entry.play.title if entry.play else "Teatru colaborativ",
                    "content": entry.content,
                    "author": entry.author.username if entry.author else "Necunoscut",
                    "toxicity_score": getattr(entry, "toxicity_score", 0.0) or 0.0,
                    "moderation_status": entry.moderation_status,
                    "moderation_reason": getattr(entry, "moderation_reason", ""),
                    "created_at": entry.created_at.isoformat()
                })

        if content_type in ["all", "stafeta_segments"]:
            segments = crud.list_stafeta_segments_for_moderation(db, status_filter="pending", limit=50)
            for segment in segments:
                content.append({
                    "id": segment.id,
                    "type": "stafeta_segment",
                    "title": segment.work.title if segment.work else "Ștafeta",
                    "content": segment.content,
                    "author": segment.author.username if segment.author else "Necunoscut",
                    "toxicity_score": getattr(segment, "toxicity_score", 0.0) or 0.0,
                    "moderation_status": segment.moderation_status,
                    "moderation_reason": getattr(segment, "moderation_reason", ""),
                    "created_at": segment.created_at.isoformat()
                })

        # Sort by creation date
        content.sort(key=lambda x: x["created_at"], reverse=True)

        return {"content": content}

    except Exception as e:
        logger.error(f"Eroare la obținerea conținutului în așteptare: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut încărca conținutul în așteptare")


@router.get("/api/moderare/continut/marcate")
def get_flagged_content(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get flagged content (high toxicity) - visible only to moderators"""
    try:
        if not current_user.is_moderator and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Acces de moderare necesar")

        content = []

        # Get flagged posts
        posts = crud.get_posts_for_moderation(db, status_filter="flagged", limit=50)
        logger.info(f"Found {len(posts)} flagged posts")

        for post in posts:
            content.append({
                "id": post.id,
                "type": "post",
                "title": post.title,
                "content": post.content,
                "author": post.owner.username,
                "toxicity_score": getattr(post, 'toxicity_score', 0.0),
                "moderation_status": getattr(post, 'moderation_status', 'flagged'),
                "moderation_reason": getattr(post, 'moderation_reason', ''),
                "created_at": post.created_at.isoformat()
            })

        # Get flagged comments
        comments = crud.get_comments_for_moderation(db, status_filter="flagged", limit=50)
        logger.info(f"Found {len(comments)} flagged comments")

        for comment in comments:
            author = comment.commenter.username if comment.commenter else comment.author_name
            content.append({
                "id": comment.id,
                "type": "comment",
                "title": None,
                "content": comment.content,
                "author": author,
                "toxicity_score": getattr(comment, 'toxicity_score', 0.0),
                "moderation_status": getattr(comment, 'moderation_status', 'flagged'),
                "moderation_reason": getattr(comment, 'moderation_reason', ''),
                "created_at": comment.created_at.isoformat()
            })

        audio_items = db.query(models.PostAudio).options(
            joinedload(models.PostAudio.post).joinedload(models.Post.owner)
        ).filter(models.PostAudio.status == "flagged").limit(50).all()
        logger.info(f"Found {len(audio_items)} flagged audio recordings")

        for audio in audio_items:
            post = audio.post
            content.append({
                "id": audio.id,
                "type": "audio",
                "title": post.title if post else None,
                "content": audio.transcript or audio.moderation_reason or "Înregistrare audio fără transcriere",
                "author": post.owner.username if post and post.owner else None,
                "toxicity_score": 0.0,
                "moderation_status": audio.status,
                "moderation_reason": audio.moderation_reason or "",
                "created_at": audio.created_at.isoformat()
            })

        forum_threads = crud.get_forum_threads_for_moderation(db, status_filter="flagged", limit=50)
        logger.info(f"Found {len(forum_threads)} flagged forum threads")
        for thread in forum_threads:
            content.append({
                "id": thread.id,
                "type": "forum_thread",
                "title": thread.title,
                "content": thread.content,
                "author": thread.author.username if thread.author else "Necunoscut",
                "toxicity_score": getattr(thread, "toxicity_score", 0.0) or 0.0,
                "moderation_status": getattr(thread, "moderation_status", "flagged"),
                "moderation_reason": getattr(thread, "moderation_reason", ""),
                "created_at": thread.created_at.isoformat()
            })

        forum_replies = crud.get_forum_replies_for_moderation(db, status_filter="flagged", limit=50)
        logger.info(f"Found {len(forum_replies)} flagged forum replies")
        for reply in forum_replies:
            content.append({
                "id": reply.id,
                "type": "forum_reply",
                "title": reply.thread.title if reply.thread else None,
                "content": reply.content,
                "author": reply.author.username if reply.author else "Necunoscut",
                "toxicity_score": getattr(reply, "toxicity_score", 0.0) or 0.0,
                "moderation_status": getattr(reply, "moderation_status", "flagged"),
                "moderation_reason": getattr(reply, "moderation_reason", ""),
                "created_at": reply.created_at.isoformat()
            })

        theatre_entries = crud.list_theatre_entries_for_moderation(db, status_filter="flagged", limit=50)
        logger.info(f"Found {len(theatre_entries)} flagged theatre entries")
        for entry in theatre_entries:
            content.append({
                "id": entry.id,
                "type": "theatre_entry",
                "title": entry.play.title if entry.play else "Teatru colaborativ",
                "content": entry.content,
                "author": entry.author.username if entry.author else "Necunoscut",
                "toxicity_score": getattr(entry, "toxicity_score", 0.0) or 0.0,
                "moderation_status": getattr(entry, "moderation_status", "flagged"),
                "moderation_reason": getattr(entry, "moderation_reason", ""),
                "created_at": entry.created_at.isoformat()
            })

        # Sort by toxicity score
        content.sort(key=lambda x: x.get("toxicity_score", 0), reverse=True)

        logger.info(f"Returning {len(content)} flagged content items")
        return {"content": content}

    except Exception as e:
        logger.error(f"Eroare la obținerea conținutului marcat: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut încărca conținutul marcat")


@router.get("/api/moderare/raportari")
def get_post_reports(
    status_filter: str = Query("open", alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator),
):
    """Get post reports submitted by readers."""
    if status_filter not in {"all", "open", "resolved", "dismissed"}:
        raise HTTPException(status_code=400, detail="Status de raportare invalid")
    reports = crud.list_post_reports(db, status_filter=status_filter, skip=offset, limit=limit)
    return {"reports": [crud.post_report_payload(report) for report in reports]}


@router.post("/api/moderare/raportari/{report_id}/revizie")
def review_post_report(
    report_id: int,
    review_data: schemas.PostReportReview,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator),
):
    """Review a reader-submitted post report."""
    report = crud.get_post_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Raportarea nu a fost găsită")
    if report.status != "open":
        raise HTTPException(status_code=400, detail="Raportarea a fost deja revizuită")

    action = review_data.action
    reason = review_data.reason
    post_id = report.post_id

    if action == "dismiss":
        reviewed = crud.update_post_report_review(
            db,
            report,
            status="dismissed",
            reviewer_id=current_user.id,
            note=reason,
        )
        return {"success": True, "message": "Raportarea a fost închisă", "report": crud.post_report_payload(reviewed)}

    if not post_id:
        raise HTTPException(status_code=404, detail="Postarea raportată nu mai există")

    if action == "reject_post":
        post = crud.reject_content(db, "post", post_id, current_user.id, reason)
        if not post:
            raise HTTPException(status_code=404, detail="Postarea raportată nu mai există")
        crud.resolve_open_post_reports_for_post(
            db,
            post_id=post_id,
            reviewer_id=current_user.id,
            note=reason,
        )
        reviewed = crud.get_post_report(db, report_id)
        return {"success": True, "message": "Postarea a fost respinsă", "report": crud.post_report_payload(reviewed)}

    if action == "delete_post":
        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Postarea raportată nu mai există")
        crud.resolve_open_post_reports_for_post(
            db,
            post_id=post_id,
            reviewer_id=current_user.id,
            note=reason,
        )
        db.delete(post)
        db.commit()
        db.expire_all()
        reviewed = crud.get_post_report(db, report_id)
        return {"success": True, "message": "Postarea a fost ștearsă", "report": crud.post_report_payload(reviewed)}

    raise HTTPException(status_code=400, detail="Acțiune invalidă")


@router.post("/api/moderare/modereaza/{content_type}/{content_id}")
def moderate_content_action(
    content_type: str,
    content_id: int,
    action_data: schemas.ModerationActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Perform moderation action on content - only moderators can access"""
    try:
        if not current_user.is_moderator and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Acces de moderare necesar")

        action = action_data.action
        reason = action_data.reason

        if action not in ["approve", "reject", "delete"]:
            raise HTTPException(status_code=400, detail="Acțiune invalidă")

        if content_type not in ["post", "comment", "audio", "forum_thread", "forum_reply", "theatre_entry", "stafeta_segment"]:
            raise HTTPException(status_code=400, detail="Tip de conținut invalid")

        # Use the new CRUD functions for approving/rejecting content
        if action == "approve":
            result = crud.approve_content(db, content_type, content_id, current_user.id, reason)
            if not result:
                raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
            if content_type == "post":
                ai_queue.enqueue_post_approval_jobs(db, result)
            logger.info(f"Content {content_type} {content_id} approved by moderator {current_user.username}")
            return {"success": True, "message": f"{_content_type_label(content_type)} a fost aprobat"}

        elif action == "reject":
            result = crud.reject_content(db, content_type, content_id, current_user.id, reason)
            if not result:
                raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
            logger.info(f"Content {content_type} {content_id} rejected by moderator {current_user.username}")
            return {"success": True, "message": f"{_content_type_label(content_type)} a fost respins"}

        elif action == "delete":
            # For delete, we still need to handle it manually since it's not in CRUD
            if content_type == "post":
                content = db.query(models.Post).filter(models.Post.id == content_id).first()
            elif content_type == "audio":
                content = db.query(models.PostAudio).filter(models.PostAudio.id == content_id).first()
            elif content_type == "forum_thread":
                content = db.query(models.ForumThread).filter(models.ForumThread.id == content_id).first()
            elif content_type == "forum_reply":
                content = db.query(models.ForumReply).filter(models.ForumReply.id == content_id).first()
            elif content_type == "theatre_entry":
                content = db.query(models.TheatreEntry).filter(models.TheatreEntry.id == content_id).first()
            elif content_type == "stafeta_segment":
                content = db.query(models.StafetaSegment).filter(models.StafetaSegment.id == content_id).first()
            else:
                content = db.query(models.Comment).filter(models.Comment.id == content_id).first()

            if not content:
                raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")

            db.delete(content)
            db.commit()
            logger.info(f"Content {content_type} {content_id} deleted by moderator {current_user.username}: {reason}")
            return {"success": True, "message": f"{_content_type_label(content_type)} a fost șters"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la moderarea conținutului: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut modera conținutul")


@router.get("/api/moderare/utilizatori/cauta")
def search_users_admin(
    q: str = "",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin)
):
    """Search users for admin management"""
    try:
        users = db.query(models.User).filter(
            or_(
                models.User.username.contains(q),
                models.User.email.contains(q)
            )
        ).limit(50).all()

        result = []
        for user in users:
            result.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_suspended": getattr(user, 'is_suspended', False),
                "suspension_reason": getattr(user, 'suspension_reason', ''),
                "created_at": user.created_at.isoformat(),
                "is_admin": user.is_admin,
                "is_moderator": user.is_moderator
            })

        return {"users": result}

    except Exception as e:
        logger.error(f"Eroare la căutarea utilizatorilor: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut căuta utilizatori")


@router.post("/api/moderare/utilizatori/{user_id}/suspenda")
def suspend_user(
    user_id: int,
    suspension_data: schemas.SuspendUserRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin)
):
    """Suspend a user"""
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")

        if user.is_admin:
            raise HTTPException(status_code=400, detail="Un administrator nu poate fi suspendat")

        # Only proceed if the suspension fields exist in the model
        try:
            user.is_suspended = True
            user.suspension_reason = suspension_data.reason
            user.suspended_at = utcnow_naive()
            user.suspended_by = current_user.id
        except AttributeError:
            # If suspension fields don't exist, just log the action
            logger.warning(f"Suspension fields not available in User model for user {user_id}")
            return {"success": False, "message": "Funcția de suspendare nu este disponibilă"}

        db.commit()
        logger.info(f"User {user.username} suspended by {current_user.username}: {suspension_data.reason}")

        return {"success": True, "message": f"Utilizatorul {user.username} a fost suspendat"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la suspendarea utilizatorului: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut suspenda utilizatorul")


@router.post("/api/moderare/utilizatori/{user_id}/reactiveaza")
def unsuspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin)
):
    """Unsuspend a user"""
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")

        # Only proceed if the suspension fields exist in the model
        try:
            user.is_suspended = False
            user.suspension_reason = None
            user.suspended_at = None
            user.suspended_by = None
        except AttributeError:
            # If suspension fields don't exist, just log the action
            logger.warning(f"Suspension fields not available in User model for user {user_id}")
            return {"success": False, "message": "Funcția de suspendare nu este disponibilă"}

        db.commit()
        logger.info(f"User {user.username} unsuspended by {current_user.username}")

        return {"success": True, "message": f"Utilizatorul {user.username} a fost reactivat"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la reactivarea utilizatorului: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut reactiva utilizatorul")


# --- Moderation Logs API Endpoints ---

@router.get("/api/moderare/jurnal")
def get_moderation_logs_api(
    request: Request,
    decision: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get moderation logs with optional filtering"""
    try:
        if decision:
            logs = crud.get_moderation_logs_by_decision(db, decision, limit)
        else:
            logs = crud.get_moderation_logs(db, limit, offset)

        result = []
        for log in logs:
            # Get content details
            content_preview = ""
            content_title = ""
            content_author = ""

            if log.content_type == "post":
                post = db.query(models.Post).filter(models.Post.id == log.content_id).first()
                if post:
                    content_title = post.title
                    content_preview = post.content[:100] + "..." if len(post.content) > 100 else post.content
                    content_author = post.owner.username if post.owner else "Necunoscut"
            elif log.content_type == "comment":
                comment = db.query(models.Comment).filter(models.Comment.id == log.content_id).first()
                if comment:
                    content_title = f"Comentariu la: {comment.post.title}" if comment.post else "Comentariu"
                    content_preview = comment.content[:100] + "..." if len(comment.content) > 100 else comment.content
                    content_author = comment.commenter.username if comment.commenter else (comment.author_name or "Anonim")
            elif log.content_type == "forum_thread":
                thread = db.query(models.ForumThread).filter(models.ForumThread.id == log.content_id).first()
                if thread:
                    content_title = thread.title
                    content_preview = thread.content[:100] + "..." if len(thread.content) > 100 else thread.content
                    content_author = thread.author.username if thread.author else "Necunoscut"
            elif log.content_type == "forum_reply":
                reply = db.query(models.ForumReply).options(
                    joinedload(models.ForumReply.thread),
                    joinedload(models.ForumReply.author),
                ).filter(models.ForumReply.id == log.content_id).first()
                if reply:
                    content_title = f"Răspuns în: {reply.thread.title}" if reply.thread else "Răspuns pe forum"
                    content_preview = reply.content[:100] + "..." if len(reply.content) > 100 else reply.content
                    content_author = reply.author.username if reply.author else "Necunoscut"
            elif log.content_type == "theatre_entry":
                entry = db.query(models.TheatreEntry).options(
                    joinedload(models.TheatreEntry.play),
                    joinedload(models.TheatreEntry.author),
                ).filter(models.TheatreEntry.id == log.content_id).first()
                if entry:
                    content_title = entry.play.title if entry.play else "Teatru colaborativ"
                    content_preview = entry.content[:100] + "..." if len(entry.content) > 100 else entry.content
                    content_author = entry.author.username if entry.author else "Necunoscut"

            result.append({
                "id": log.id,
                "content_type": log.content_type,
                "content_id": log.content_id,
                "content_title": content_title,
                "content_preview": content_preview,
                "content_author": content_author,
                "ai_decision": log.ai_decision,
                "toxicity_score": log.toxicity_score,
                "harassment_score": log.harassment_score,
                "hate_speech_score": log.hate_speech_score,
                "sexually_explicit_score": log.sexually_explicit_score,
                "dangerous_content_score": log.dangerous_content_score,
                "romanian_profanity_score": log.romanian_profanity_score,
                "ai_reason": log.ai_reason,
                "human_decision": log.human_decision,
                "human_reason": log.human_reason,
                "moderator": log.moderator.username if log.moderator else None,
                "moderated_at": log.moderated_at.isoformat() if log.moderated_at else None,
                "created_at": log.created_at.isoformat(),
                "needs_review": log.needs_human_review
            })

        return {"logs": result, "total": len(result)}

    except Exception as e:
        logger.error(f"Eroare la obținerea jurnalului de moderare: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut încărca jurnalul de moderare")


@router.get("/api/moderare/coada")
def get_moderation_queue_api(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get content flagged by AI that needs human review"""
    try:
        logs = crud.get_moderation_logs_for_review(db, 50)

        result = []
        for log in logs:
            # Get full content details for review
            content_data = None

            if log.content_type == "post":
                post = db.query(models.Post).filter(models.Post.id == log.content_id).first()
                if post:
                    content_data = {
                        "id": post.id,
                        "title": post.title,
                        "content": post.content,
                        "author": post.owner.username if post.owner else "Necunoscut",
                        "created_at": post.created_at.isoformat(),
                        "view_count": post.view_count,
                        "category": post.category
                    }
            elif log.content_type == "comment":
                comment = db.query(models.Comment).filter(models.Comment.id == log.content_id).first()
                if comment:
                    content_data = {
                        "id": comment.id,
                        "content": comment.content,
                        "author": comment.commenter.username if comment.commenter else (comment.author_name or "Anonim"),
                        "post_title": comment.post.title if comment.post else "Postare necunoscută",
                        "post_id": comment.post_id,
                        "created_at": comment.created_at.isoformat()
                    }
            elif log.content_type == "audio":
                audio = db.query(models.PostAudio).options(
                    joinedload(models.PostAudio.post).joinedload(models.Post.owner)
                ).filter(models.PostAudio.id == log.content_id).first()
                if audio:
                    content_data = {
                        "id": audio.id,
                        "content": audio.transcript or audio.moderation_reason or "Înregistrare audio",
                        "author": audio.post.owner.username if audio.post and audio.post.owner else "Necunoscut",
                        "post_title": audio.post.title if audio.post else "Postare necunoscută",
                        "post_id": audio.post_id,
                        "created_at": audio.created_at.isoformat(),
                        "match_score": audio.transcript_match_score,
                    }
            elif log.content_type == "forum_thread":
                thread = db.query(models.ForumThread).options(
                    joinedload(models.ForumThread.author)
                ).filter(models.ForumThread.id == log.content_id).first()
                if thread:
                    content_data = {
                        "id": thread.id,
                        "title": thread.title,
                        "content": thread.content,
                        "author": thread.author.username if thread.author else "Necunoscut",
                        "created_at": thread.created_at.isoformat(),
                        "section": thread.section,
                    }
            elif log.content_type == "forum_reply":
                reply = db.query(models.ForumReply).options(
                    joinedload(models.ForumReply.author),
                    joinedload(models.ForumReply.thread),
                ).filter(models.ForumReply.id == log.content_id).first()
                if reply:
                    content_data = {
                        "id": reply.id,
                        "title": reply.thread.title if reply.thread else None,
                        "content": reply.content,
                        "author": reply.author.username if reply.author else "Necunoscut",
                        "thread_id": reply.thread_id,
                        "created_at": reply.created_at.isoformat(),
                    }
            elif log.content_type == "theatre_entry":
                entry = db.query(models.TheatreEntry).options(
                    joinedload(models.TheatreEntry.author),
                    joinedload(models.TheatreEntry.play),
                    joinedload(models.TheatreEntry.scene),
                    joinedload(models.TheatreEntry.character),
                ).filter(models.TheatreEntry.id == log.content_id).first()
                if entry:
                    content_data = {
                        "id": entry.id,
                        "title": entry.play.title if entry.play else "Teatru colaborativ",
                        "content": entry.content,
                        "author": entry.author.username if entry.author else "Necunoscut",
                        "play_id": entry.play_id,
                        "scene_id": entry.scene_id,
                        "entry_type": entry.entry_type,
                        "character": entry.character.name if entry.character else None,
                        "created_at": entry.created_at.isoformat(),
                    }

            if content_data:
                result.append({
                    "log_id": log.id,
                    "content_type": log.content_type,
                    "content": content_data,
                    "ai_analysis": {
                        "decision": log.ai_decision,
                        "toxicity_score": log.toxicity_score,
                        "harassment_score": log.harassment_score,
                        "hate_speech_score": log.hate_speech_score,
                        "sexually_explicit_score": log.sexually_explicit_score,
                        "dangerous_content_score": log.dangerous_content_score,
                        "romanian_profanity_score": log.romanian_profanity_score,
                        "reason": log.ai_reason
                    },
                    "flagged_at": log.created_at.isoformat()
                })

        return {"queue": result, "total": len(result)}

    except Exception as e:
        logger.error(f"Eroare la obținerea cozii de moderare: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut încărca coada de moderare")


@router.post("/api/moderare/revizie/{log_id}")
def review_flagged_content(
    log_id: int,
    review_data: schemas.ModerationActionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Human moderator review of AI-flagged content"""
    try:
        decision = review_data.action  # "approved" or "rejected"
        reason = review_data.reason

        if decision not in ["approved", "rejected"]:
            raise HTTPException(status_code=400, detail="Decizie invalidă. Folosiți 'approved' sau 'rejected'")

        # Update the moderation log
        log = crud.update_moderation_log_human_decision(
            db, log_id, decision, reason, current_user.id
        )

        if not log:
            raise HTTPException(status_code=404, detail="Înregistrarea de moderare nu a fost găsită")

        # Use the centralized CRUD functions to update content and send notifications
        if decision == "approved":
            crud.approve_content(db, log.content_type, log.content_id, current_user.id, f"Revizie umană: {reason}")
        else:
            crud.reject_content(db, log.content_type, log.content_id, current_user.id, f"Revizie umană: {reason}")

        logger.info(f"Human review completed by {current_user.username}: {log.content_type} {log.content_id} {decision}")

        decision_label = "aprobat" if decision == "approved" else "respins"
        return {"success": True, "message": f"Conținut {decision_label}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la revizia conținutului marcat: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut revizui conținutul")


@router.get("/api/moderare/statistici/extinse")
def get_extended_moderation_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get extended moderation statistics including AI logs"""
    try:
        stats = crud.get_moderation_stats_extended(db)
        return stats

    except Exception as e:
        logger.error(f"Eroare la obținerea statisticilor extinse de moderare: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut încărca statisticile extinse de moderare")
