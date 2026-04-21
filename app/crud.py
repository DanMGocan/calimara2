import logging
import os
import re
from datetime import datetime, date as date_type
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, desc, extract
from . import models, schemas

logger = logging.getLogger(__name__)

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
    return (
        db.query(models.User)
        .join(models.Post, models.Post.user_id == models.User.id)
        .filter(models.Post.moderation_status == "approved")
        .distinct()
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
        **post.model_dump(exclude={"tags"}),
        user_id=user_id,
        slug=slug,
        category=category,
        moderation_status="pending"
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    if post.tags:
        for tag_name in post.tags:
            create_tag(db, db_post.id, tag_name.strip())
            
    return db_post

def update_post(db: Session, post_id: int, post_update: schemas.PostUpdate, category: Optional[str] = None):
    db_post = get_post(db, post_id)
    if not db_post:
        return None
    
    update_data = post_update.model_dump(exclude_unset=True, exclude={"tags"})
    for key, value in update_data.items():
        setattr(db_post, key, value)
    
    if category:
        db_post.category = category
        
    db_post.moderation_status = "pending"
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

def get_random_posts(db: Session, limit: int = 10):
    return db.query(models.Post).filter(models.Post.moderation_status == "approved").order_by(func.random()).limit(limit).all()

def get_random_posts_by_category(db: Session, category: str, limit: int = 10):
    return db.query(models.Post).filter(
        models.Post.category == category,
        models.Post.moderation_status == "approved"
    ).order_by(func.random()).limit(limit).all()

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

def get_latest_posts_for_user(db: Session, user_id: int, limit: int = 5):
    return db.query(models.Post).filter(
        models.Post.user_id == user_id,
        models.Post.moderation_status == "approved"
    ).order_by(models.Post.created_at.desc()).limit(limit).all()

def get_posts_by_month_year(db: Session, user_id: int, month: int, year: int, limit: int = 50):
    return db.query(models.Post).filter(
        models.Post.user_id == user_id,
        models.Post.moderation_status == "approved",
        extract('month', models.Post.created_at) == month,
        extract('year', models.Post.created_at) == year
    ).order_by(models.Post.created_at.desc()).limit(limit).all()

def get_available_months_for_user(db: Session, user_id: int):
    results = db.query(
        extract('month', models.Post.created_at).label('month'),
        extract('year', models.Post.created_at).label('year'),
        func.count(models.Post.id).label('post_count')
    ).filter(
        models.Post.user_id == user_id,
        models.Post.moderation_status == "approved"
    ).group_by('year', 'month').order_by(desc('year'), desc('month')).all()
    
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

def get_comments_for_post(db: Session, post_id: int, approved_only: bool = True):
    query = db.query(models.Comment).filter(models.Comment.post_id == post_id)
    if approved_only:
        query = query.filter(models.Comment.approved == True)
    return query.order_by(models.Comment.created_at.desc()).all()

def approve_comment(db: Session, comment_id: int):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if comment:
        comment.approved = True
        comment.moderation_status = "approved"
        db.commit()
        db.refresh(comment)
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
    
    stats['total_pending'] = stats['posts_pending'] + stats['comments_pending']
    stats['total_flagged'] = stats['posts_flagged'] + stats['comments_flagged']
    stats['total_rejected'] = stats['posts_rejected'] + stats['comments_rejected']
    return stats

def approve_content(db: Session, content_type: str, content_id: int, moderator_id: int, reason: str = ""):
    if content_type == "post":
        content = db.query(models.Post).filter(models.Post.id == content_id).first()
    else:
        content = db.query(models.Comment).filter(models.Comment.id == content_id).first()
    
    if content:
        content.moderation_status = "approved"
        content.moderated_by = moderator_id
        content.moderated_at = func.now()
        if reason:
            content.moderation_reason = reason
        if content_type == "comment":
            content.approved = True
            
        db.commit()
        db.refresh(content)

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
                user_id=content.user_id, ai_decision="approved",
                human_decision="approved", human_reason=reason,
                moderated_by=moderator_id, moderated_at=func.now()
            )
            db.add(log_entry)
        db.commit()

        # Notify
        if content.user_id:
            create_notification(
                db=db, user_id=content.user_id, notif_type="moderation_approved",
                title="Conținut aprobat",
                message=f"{'Postarea' if content_type == 'post' else 'Comentariul'} tău a fost aprobat și publicat. {reason}",
                link=f"/piese/{content.slug}" if content_type == "post" else None
            )
        return content
    return None

def reject_content(db: Session, content_type: str, content_id: int, moderator_id: int, reason: str = ""):
    if content_type == "post":
        content = db.query(models.Post).filter(models.Post.id == content_id).first()
    else:
        content = db.query(models.Comment).filter(models.Comment.id == content_id).first()
    
    if content:
        content.moderation_status = "rejected"
        content.moderated_by = moderator_id
        content.moderated_at = func.now()
        if reason:
            content.moderation_reason = reason
        if content_type == "comment":
            content.approved = False
            
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
                user_id=content.user_id, ai_decision="approved",
                human_decision="rejected", human_reason=reason,
                moderated_by=moderator_id, moderated_at=func.now()
            )
            db.add(log_entry)
        db.commit()

        # Notify
        if content.user_id:
            create_notification(
                db=db, user_id=content.user_id, notif_type="moderation_rejected",
                title="Conținut respins",
                message=f"{'Postarea' if content_type == 'post' else 'Comentariul'} tău a fost respins. Motiv: {reason}",
                link=None
            )
        return content
    return None

# ===================================
# TAG CRUD FUNCTIONS
# ===================================

def create_tag(db: Session, post_id: int, tag_name: str):
    db_tag = models.Tag(post_id=post_id, tag_name=tag_name)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

def delete_tags_for_post(db: Session, post_id: int):
    db.query(models.Tag).filter(models.Tag.post_id == post_id).delete()
    db.commit()

def get_tag_suggestions(db: Session, query: str, limit: int = 10):
    normalized_query = query.strip().lower()
    if len(normalized_query) < 2:
        return []

    normalized_tag = func.lower(models.Tag.tag_name)
    usage_count = func.count(models.Tag.id)
    suggestions = db.query(
        normalized_tag.label("tag_name"),
        usage_count.label("usage_count"),
    ).filter(
        normalized_tag.like(f"{normalized_query}%")
    ).group_by(
        normalized_tag
    ).order_by(
        usage_count.desc(),
        normalized_tag.asc(),
    ).limit(limit).all()

    return [row.tag_name for row in suggestions]

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

def get_notifications(db: Session, user_id: int, limit: int = 20):
    return get_notifications_for_user(db, user_id, 0, limit)

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
