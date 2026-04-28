import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import ai_queue, audio_service, models, schemas, crud, auth
from ..database import get_db
from ..utils import get_client_ip, SUBDOMAIN_SUFFIX
from ..categories import CATEGORIES

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["posts"])


# --- Posts Archive ---

@router.get("/api/posts/archive")
def get_posts_archive(
    month: int = None,
    year: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get posts archive for current user, optionally filtered by month/year"""
    try:
        if month and year:
            posts = crud.get_posts_by_month_year(
                db, current_user.id, month, year, include_unapproved=True
            )
        else:
            posts = crud.get_latest_posts_for_user(
                db, current_user.id, limit=50, include_unapproved=True
            )

        # Format posts for frontend
        formatted_posts = []
        for post in posts:
            audio_summary = audio_service.post_audio_summary(db, post)
            active_tts = crud.get_active_or_ready_tts_for_post(db, post.id)
            if (
                active_tts
                and active_tts.requester_user_id is None
                and active_tts.status in {"pending", "processing"}
            ):
                active_tts = None
            audio_can_request = bool(
                current_user.has_audio_access
                and post.moderation_status == "approved"
                and not active_tts
            )
            formatted_posts.append({
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "content": post.content[:200] + "..." if len(post.content) > 200 else post.content,
                "category": post.category,
                "view_count": post.view_count,
                "likes_count": post.likes_count,
                "comments_count": len(post.comments),
                "moderation_status": post.moderation_status,
                "moderation_reason": post.moderation_reason,
                "created_at": post.created_at.strftime('%d %B %Y'),
                "url": f"//{current_user.username}{SUBDOMAIN_SUFFIX}/{post.slug}",
                "audio_can_request": audio_can_request,
                **audio_summary,
            })

        return {"posts": formatted_posts}

    except Exception as e:
        logger.error(f"Eroare la obținerea arhivei pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts archive")


@router.get("/api/posts/months")
def get_available_months(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get available months/years for user's posts"""
    try:
        months = crud.get_available_months_for_user(db, current_user.id, include_unapproved=True)
        return {"months": months}
    except Exception as e:
        logger.error(f"Eroare la obținerea lunilor pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available months")


# --- Post CRUD ---

@router.post("/api/posts/", response_model=schemas.Post)
@limiter.limit("20/minute")
async def create_post(
    request: Request,
    post: schemas.PostCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    db_post = crud.create_user_post(db=db, post=post, user_id=current_user.id)
    ai_queue.enqueue_post_publish_job(db, db_post, ai_critic_requested=post.ai_critic)
    return db_post


@router.put("/api/posts/{post_id}", response_model=schemas.Post)
def update_post_api(
    post_id: int,
    post_update: schemas.PostUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")

    updated = crud.update_post(db=db, post_id=post_id, post_update=post_update)
    if updated:
        ai_queue.enqueue_post_publish_job(db, updated, ai_critic_requested=False)
    return updated


@router.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post_api(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
    crud.delete_post(db=db, post_id=post_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Comments ---

@router.post("/api/posts/{post_id}/comments", response_model=schemas.Comment)
@limiter.limit("20/minute")
def add_comment_to_post(
    post_id: int,
    comment: schemas.CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user)
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    user_id = current_user.id if current_user else None
    if not user_id and (not comment.author_name or not comment.author_email):
        raise HTTPException(status_code=400, detail="Numele și emailul autorului sunt obligatorii pentru comentariile neautentificate")

    db_comment = crud.create_comment(db=db, comment=comment, post_id=post_id, user_id=user_id)
    ai_queue.enqueue_comment_moderation_job(db, db_comment)
    return db_comment


@router.put("/api/comments/{comment_id}/approve", response_model=schemas.Comment)
def approve_comment_api(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comentariul nu a fost găsit")

    # Ensure the current user owns the post associated with the comment
    db_post = crud.get_post(db, post_id=db_comment.post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu sunteți autorizat să aprobați acest comentariu")

    return crud.approve_comment(db=db, comment_id=comment_id)


@router.delete("/api/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment_api(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comentariul nu a fost găsit")

    # Ensure the current user owns the post associated with the comment
    db_post = crud.get_post(db, post_id=db_comment.post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu sunteți autorizat să ștergeți acest comentariu")

    crud.delete_comment(db=db, comment_id=comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Likes ---

@router.post("/api/posts/{post_id}/likes", response_model=schemas.Like)
def add_like_to_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user)
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    user_id = current_user.id if current_user else None
    ip_address = get_client_ip(request) if not user_id else None

    db_like = crud.create_like(db=db, post_id=post_id, user_id=user_id, ip_address=ip_address)
    if not db_like:
        raise HTTPException(status_code=409, detail="Ați apreciat deja această postare")
    return db_like


@router.get("/api/posts/{post_id}/likes/count")
def get_likes_count(post_id: int, db: Session = Depends(get_db)):
    count = crud.get_likes_count_for_post(db, post_id)
    return {"post_id": post_id, "likes_count": count}


# --- Random Posts API ---

@router.get("/api/posts/random")
def get_random_posts_api(
    category: str = "toate",
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get random posts filtered by category for AJAX requests"""
    try:
        # Filter random posts based on category parameter
        if category == "toate":
            random_posts = crud.get_random_posts(db, limit=limit)
        else:
            if category in CATEGORIES:
                random_posts = crud.get_random_posts_by_category(db, category, limit=limit)
            else:
                random_posts = []

        # Format posts for frontend
        formatted_posts = []
        for post in random_posts:
            category_name = CATEGORIES.get(post.category, "") if post.category else ""

            formatted_posts.append({
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "content": post.content[:120] + "..." if len(post.content) > 120 else post.content,
                "likes_count": post.likes_count,
                "created_at": post.created_at.strftime('%d %b'),
                "category": post.category,
                "category_name": category_name,
                "owner": {
                    "username": post.owner.username,
                    "avatar_seed": post.owner.avatar_seed or f"{post.owner.username}-shapes"
                }
            })

        return {"posts": formatted_posts}

    except Exception as e:
        logger.error(f"Error getting random posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get random posts")
