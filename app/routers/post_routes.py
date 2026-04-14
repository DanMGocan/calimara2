import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import models, schemas, crud, auth, moderation, theme_analysis, category_classifier
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
            posts = crud.get_posts_by_month_year(db, current_user.id, month, year)
        else:
            posts = crud.get_latest_posts_for_user(db, current_user.id, limit=50)

        # Format posts for frontend
        formatted_posts = []
        for post in posts:
            formatted_posts.append({
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "content": post.content[:200] + "..." if len(post.content) > 200 else post.content,
                "category": post.category,
                "view_count": post.view_count,
                "likes_count": post.likes_count,
                "comments_count": len(post.comments),
                "created_at": post.created_at.strftime('%d %B %Y'),
                "url": f"//{current_user.username}.calimara.ro/{post.slug}"
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
        months = crud.get_available_months_for_user(db, current_user.id)
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
    # AI category classification
    try:
        category = category_classifier.classify_post(post.title, post.content)
    except Exception as e:
        logger.error(f"Category classification failed: {e}")
        category = "proza_scurta"

    # Create post first
    db_post = crud.create_user_post(db=db, post=post, user_id=current_user.id, category=category)

    # Then moderate it asynchronously with logging
    try:
        moderation_result = moderation.moderate_post_with_logging(
            post.title, post.content, db_post.id, current_user.id, db
        )

        # Update post with moderation results
        db_post.moderation_status = moderation_result.status.value
        db_post.toxicity_score = moderation_result.toxicity_score
        db_post.moderation_reason = moderation_result.reason

        db.commit()
        db.refresh(db_post)

        if db_post.moderation_status == "flagged":
            crud.create_notification(
                db=db,
                user_id=current_user.id,
                notif_type="moderation_queue",
                title="Postare în curs de moderare",
                message=f"Postarea '{db_post.title}' a fost trimisă pentru revizuire manuală.",
                link=None
            )

        logger.info(f"Post moderated: {moderation_result.status.value} (toxicity: {moderation_result.toxicity_score:.3f})")

    except Exception as e:
        logger.error(f"Moderation failed for post: {e}. Auto-approving due to error.")
        # If moderation fails, auto-approve to avoid blocking user content
        db_post.moderation_status = "approved"
        db_post.moderation_reason = "Auto-approved due to moderation error"
        db.commit()
        db.refresh(db_post)

    # Theme analysis (non-blocking)
    try:
        analysis = theme_analysis.analyze_post_themes(post.title, post.content, db)
        if analysis.success:
            crud.update_post_theme_analysis(db, db_post.id, analysis.themes, analysis.feelings, "completed")
        else:
            crud.update_post_theme_analysis(db, db_post.id, [], [], "failed")
        db.refresh(db_post)
    except Exception as e:
        logger.error(f"Theme analysis failed for post {db_post.id}: {e}")
        crud.update_post_theme_analysis(db, db_post.id, [], [], "failed")

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

    # Re-classify category based on updated content
    try:
        content = post_update.content if post_update.content else db_post.content
        title = post_update.title if post_update.title else db_post.title
        category = category_classifier.classify_post(title, content)
    except Exception as e:
        logger.error(f"Category re-classification failed: {e}")
        category = db_post.category or "proza_scurta"

    # Delete existing tags and create new ones if tags are provided
    if post_update.tags is not None:
        crud.delete_tags_for_post(db, post_id)
        for tag_name in post_update.tags:
            crud.create_tag(db, post_id, tag_name.strip())

    return crud.update_post(db=db, post_id=post_id, post_update=post_update, category=category)


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

    # Create comment first
    db_comment = crud.create_comment(db=db, comment=comment, post_id=post_id, user_id=user_id)

    # Then moderate it asynchronously with logging
    try:
        moderation_result = moderation.moderate_comment_with_logging(
            comment.content, db_comment.id, user_id, db
        )

        # Update comment with moderation results
        db_comment.moderation_status = moderation_result.status.value
        db_comment.toxicity_score = moderation_result.toxicity_score
        db_comment.moderation_reason = moderation_result.reason
        db_comment.approved = moderation_result.status.value == "approved"

        db.commit()
        db.refresh(db_comment)

        if db_comment.moderation_status == "flagged" and user_id:
            crud.create_notification(
                db=db,
                user_id=user_id,
                notif_type="moderation_queue",
                title="Comentariu în curs de moderare",
                message=f"Comentariul tău la postarea '{db_post.title}' a fost trimis pentru revizuire manuală.",
                link=f"/piese/{db_post.slug}"
            )

        logger.info(f"Comment moderated: {moderation_result.status.value} (toxicity: {moderation_result.toxicity_score:.3f})")
        logger.info(f"Comment ID {db_comment.id} status: {db_comment.moderation_status}, approved: {db_comment.approved}")

    except Exception as e:
        logger.error(f"Moderation failed for comment: {e}. Auto-approving due to error.")
        # If moderation fails, auto-approve to avoid blocking user content
        db_comment.moderation_status = "approved"
        db_comment.approved = True
        db_comment.moderation_reason = "Auto-approved due to moderation error"
        db.commit()
        db.refresh(db_comment)

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


# --- Tags ---

@router.get("/api/tags/suggestions")
def get_tag_suggestions_api(
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get tag suggestions for autocomplete based on partial query"""
    if not query or len(query.strip()) < 2:
        return {"suggestions": []}

    suggestions = crud.get_tag_suggestions(db, query.strip(), limit)
    return {"suggestions": suggestions}


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
