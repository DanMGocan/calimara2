from ._shared import *
from .economy import award_content_approved
from .mentions import notify_mentions_for_comment

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
        content=rich_text.sanitize_rich_text(content),
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
            notify_mentions_for_comment(db, comment)
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
