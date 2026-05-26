from ._shared import *
from .economy import award_content_approved
from .mentions import notify_mentions_for_comment
from .. import email_service

COMMENT_REACTION_TYPES = ("helpful", "funny", "insightful")


class CommentReactionSelfError(Exception):
    pass


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
            email_service.queue_comment_approved_email(db, comment)
    return comment

def delete_comment(db: Session, comment_id: int):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment:
        db.delete(comment)
        db.commit()
    return comment

def get_user_total_comments(db: Session, user_id: int):
    return db.query(models.Comment).join(models.Post).filter(models.Post.user_id == user_id).count()


def empty_comment_reaction_counts() -> dict[str, int]:
    return {reaction_type: 0 for reaction_type in COMMENT_REACTION_TYPES}


def comment_reaction_summary(db: Session, comment_id: int, viewer_user_id: Optional[int] = None) -> dict:
    counts = empty_comment_reaction_counts()
    for reaction_type, count in (
        db.query(models.CommentReaction.reaction_type, func.count(models.CommentReaction.id))
        .filter(models.CommentReaction.comment_id == comment_id)
        .group_by(models.CommentReaction.reaction_type)
        .all()
    ):
        if reaction_type in counts:
            counts[reaction_type] = int(count or 0)

    viewer_reaction = None
    if viewer_user_id:
        viewer_reaction = (
            db.query(models.CommentReaction.reaction_type)
            .filter(
                models.CommentReaction.comment_id == comment_id,
                models.CommentReaction.user_id == viewer_user_id,
            )
            .scalar()
        )

    return {
        "comment_id": comment_id,
        "counts": counts,
        "total": sum(counts.values()),
        "viewer_reaction": viewer_reaction,
    }


def get_approved_comment(db: Session, comment_id: int) -> Optional[models.Comment]:
    return (
        db.query(models.Comment)
        .filter(models.Comment.id == comment_id, models.Comment.approved == True)
        .first()
    )


def upsert_comment_reaction(db: Session, comment_id: int, user_id: int, reaction_type: str) -> Optional[dict]:
    if reaction_type not in COMMENT_REACTION_TYPES:
        raise ValueError("Invalid comment reaction type")
    comment = get_approved_comment(db, comment_id)
    if not comment:
        return None
    if comment.user_id == user_id:
        raise CommentReactionSelfError

    existing = (
        db.query(models.CommentReaction)
        .filter(
            models.CommentReaction.comment_id == comment_id,
            models.CommentReaction.user_id == user_id,
        )
        .first()
    )
    if existing:
        existing.reaction_type = reaction_type
    else:
        db.add(
            models.CommentReaction(
                comment_id=comment_id,
                user_id=user_id,
                reaction_type=reaction_type,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return comment_reaction_summary(db, comment_id, viewer_user_id=user_id)


def delete_comment_reaction(db: Session, comment_id: int, user_id: int) -> Optional[dict]:
    comment = get_approved_comment(db, comment_id)
    if not comment:
        return None

    reaction = (
        db.query(models.CommentReaction)
        .filter(
            models.CommentReaction.comment_id == comment_id,
            models.CommentReaction.user_id == user_id,
        )
        .first()
    )
    if not reaction:
        return None
    db.delete(reaction)
    db.commit()
    return comment_reaction_summary(db, comment_id, viewer_user_id=user_id)

# ===================================
# MODERATION CRUD FUNCTIONS
# ===================================
