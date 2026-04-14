import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import models, schemas, crud, admin, moderation
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["moderation"])


@router.get("/api/moderation/stats")
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

        today = datetime.now().date()
        today_actions = db.query(models.Post).filter(
            models.Post.moderated_at >= today
        ).count() + db.query(models.Comment).filter(
            models.Comment.moderated_at >= today
        ).count()

        return {
            "pending_count": stats['total_pending'],
            "flagged_count": stats['total_flagged'],
            "suspended_count": suspended_users,
            "today_actions": today_actions,
            "posts_pending": stats['posts_pending'],
            "posts_flagged": stats['posts_flagged'],
            "comments_pending": stats['comments_pending'],
            "comments_flagged": stats['comments_flagged']
        }

    except Exception as e:
        logger.error(f"Error getting moderation stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get moderation stats")


@router.get("/api/moderation/content/pending")
def get_pending_content(
    request: Request,
    content_type: str = "all",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get content pending moderation - visible only to moderators"""
    try:
        if not current_user.is_moderator and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Moderation access required")

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

        # Sort by creation date
        content.sort(key=lambda x: x["created_at"], reverse=True)

        return {"content": content}

    except Exception as e:
        logger.error(f"Error getting pending content: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending content")


@router.get("/api/moderation/content/flagged")
def get_flagged_content(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_moderator)
):
    """Get flagged content (high toxicity) - visible only to moderators"""
    try:
        if not current_user.is_moderator and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Moderation access required")

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

        # Sort by toxicity score
        content.sort(key=lambda x: x.get("toxicity_score", 0), reverse=True)

        logger.info(f"Returning {len(content)} flagged content items")
        return {"content": content}

    except Exception as e:
        logger.error(f"Error getting flagged content: {e}")
        raise HTTPException(status_code=500, detail="Failed to get flagged content")


@router.post("/api/moderation/moderate/{content_type}/{content_id}")
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
            raise HTTPException(status_code=403, detail="Moderation access required")

        action = action_data.action
        reason = action_data.reason

        if action not in ["approve", "reject", "delete"]:
            raise HTTPException(status_code=400, detail="Invalid action")

        if content_type not in ["post", "comment"]:
            raise HTTPException(status_code=400, detail="Invalid content type")

        # Use the new CRUD functions for approving/rejecting content
        if action == "approve":
            result = crud.approve_content(db, content_type, content_id, current_user.id, reason)
            if not result:
                raise HTTPException(status_code=404, detail="Content not found")
            logger.info(f"Content {content_type} {content_id} approved by moderator {current_user.username}")
            return {"success": True, "message": f"{content_type.title()} approved successfully"}

        elif action == "reject":
            result = crud.reject_content(db, content_type, content_id, current_user.id, reason)
            if not result:
                raise HTTPException(status_code=404, detail="Content not found")
            logger.info(f"Content {content_type} {content_id} rejected by moderator {current_user.username}")
            return {"success": True, "message": f"{content_type.title()} rejected successfully"}

        elif action == "delete":
            # For delete, we still need to handle it manually since it's not in CRUD
            if content_type == "post":
                content = db.query(models.Post).filter(models.Post.id == content_id).first()
            else:
                content = db.query(models.Comment).filter(models.Comment.id == content_id).first()

            if not content:
                raise HTTPException(status_code=404, detail="Content not found")

            db.delete(content)
            db.commit()
            logger.info(f"Content {content_type} {content_id} deleted by moderator {current_user.username}: {reason}")
            return {"success": True, "message": f"{content_type.title()} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moderating content: {e}")
        raise HTTPException(status_code=500, detail="Failed to moderate content")


@router.get("/api/moderation/users/search")
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
        logger.error(f"Error searching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to search users")


@router.post("/api/moderation/users/{user_id}/suspend")
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
            raise HTTPException(status_code=404, detail="User not found")

        if user.is_admin:
            raise HTTPException(status_code=400, detail="Cannot suspend admin user")

        # Only proceed if the suspension fields exist in the model
        try:
            user.is_suspended = True
            user.suspension_reason = suspension_data.reason
            user.suspended_at = datetime.now()
            user.suspended_by = current_user.id
        except AttributeError:
            # If suspension fields don't exist, just log the action
            logger.warning(f"Suspension fields not available in User model for user {user_id}")
            return {"success": False, "message": "Suspension functionality not available"}

        db.commit()
        logger.info(f"User {user.username} suspended by {current_user.username}: {suspension_data.reason}")

        return {"success": True, "message": f"User {user.username} suspended"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suspending user: {e}")
        raise HTTPException(status_code=500, detail="Failed to suspend user")


@router.post("/api/moderation/users/{user_id}/unsuspend")
def unsuspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin)
):
    """Unsuspend a user"""
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Only proceed if the suspension fields exist in the model
        try:
            user.is_suspended = False
            user.suspension_reason = None
            user.suspended_at = None
            user.suspended_by = None
        except AttributeError:
            # If suspension fields don't exist, just log the action
            logger.warning(f"Suspension fields not available in User model for user {user_id}")
            return {"success": False, "message": "Suspension functionality not available"}

        db.commit()
        logger.info(f"User {user.username} unsuspended by {current_user.username}")

        return {"success": True, "message": f"User {user.username} unsuspended"}

    except Exception as e:
        logger.error(f"Error unsuspending user: {e}")
        raise HTTPException(status_code=500, detail="Failed to unsuspend user")


# --- Moderation Logs API Endpoints ---

@router.get("/api/moderation/logs")
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
                    content_author = post.owner.username if post.owner else "Unknown"
            elif log.content_type == "comment":
                comment = db.query(models.Comment).filter(models.Comment.id == log.content_id).first()
                if comment:
                    content_title = f"Comment on: {comment.post.title}" if comment.post else "Comment"
                    content_preview = comment.content[:100] + "..." if len(comment.content) > 100 else comment.content
                    content_author = comment.commenter.username if comment.commenter else (comment.author_name or "Anonymous")

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
        logger.error(f"Error getting moderation logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get moderation logs")


@router.get("/api/moderation/queue")
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
                        "author": post.owner.username if post.owner else "Unknown",
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
                        "author": comment.commenter.username if comment.commenter else (comment.author_name or "Anonymous"),
                        "post_title": comment.post.title if comment.post else "Unknown Post",
                        "post_id": comment.post_id,
                        "created_at": comment.created_at.isoformat()
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
        logger.error(f"Error getting moderation queue: {e}")
        raise HTTPException(status_code=500, detail="Failed to get moderation queue")


@router.post("/api/moderation/review/{log_id}")
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
            raise HTTPException(status_code=400, detail="Invalid decision. Must be 'approved' or 'rejected'")

        # Update the moderation log
        log = crud.update_moderation_log_human_decision(
            db, log_id, decision, reason, current_user.id
        )

        if not log:
            raise HTTPException(status_code=404, detail="Moderation log not found")

        # Use the centralized CRUD functions to update content and send notifications
        if decision == "approved":
            crud.approve_content(db, log.content_type, log.content_id, current_user.id, f"Human review: {reason}")
        else:
            crud.reject_content(db, log.content_type, log.content_id, current_user.id, f"Human review: {reason}")

        logger.info(f"Human review completed by {current_user.username}: {log.content_type} {log.content_id} {decision}")

        return {"success": True, "message": f"Content {decision} successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing flagged content: {e}")
        raise HTTPException(status_code=500, detail="Failed to review content")


@router.get("/api/moderation/stats/extended")
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
        logger.error(f"Error getting extended moderation stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get extended moderation stats")


