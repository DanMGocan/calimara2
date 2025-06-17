from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from . import models, schemas, moderation
from passlib.context import CryptContext
from typing import Optional, List
import random
import re
import unicodedata
import asyncio
import logging

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_slug(title: str) -> str:
    """Generate a URL-friendly slug from a post title"""
    # Normalize unicode characters (handle Romanian diacritics)
    slug = unicodedata.normalize('NFKD', title)
    
    # Convert Romanian characters
    replacements = {
        'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
        'Ă': 'a', 'Â': 'a', 'Î': 'i', 'Ș': 's', 'Ț': 't'
    }
    for old, new in replacements.items():
        slug = slug.replace(old, new)
    
    # Convert to lowercase
    slug = slug.lower()
    
    # Replace spaces and special characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    
    # Remove leading/trailing hyphens and limit length
    slug = slug.strip('-')[:250]  # Leave room for potential suffixes
    
    # Remove trailing hyphens again after truncation
    slug = slug.rstrip('-')
    
    return slug

def ensure_unique_slug(db: Session, base_slug: str, post_id: Optional[int] = None) -> str:
    """Ensure the slug is unique by adding a number suffix if needed"""
    slug = base_slug
    counter = 1
    
    while True:
        # Check if slug exists (excluding current post if updating)
        query = db.query(models.Post).filter(models.Post.slug == slug)
        if post_id:
            query = query.filter(models.Post.id != post_id)
        
        if not query.first():
            return slug
        
        # Add counter suffix
        slug = f"{base_slug}-{counter}"
        counter += 1
        
        # Prevent infinite loop
        if counter > 100:
            slug = f"{base_slug}-{random.randint(1000, 9999)}"
            break
    
    return slug

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_google_id(db: Session, google_id: str):
    return db.query(models.User).filter(models.User.google_id == google_id).first()

def create_user_from_google(db: Session, user_data: dict):
    """Create user from Google OAuth data"""
    # Generate default avatar seed if not provided
    avatar_seed = user_data.get('avatar_seed') or f"{user_data['username']}-shapes"
    db_user = models.User(
        username=user_data['username'],
        email=user_data['email'],
        google_id=user_data['google_id'],
        subtitle=user_data.get('subtitle'),
        avatar_seed=avatar_seed
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_post(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_post_by_slug(db: Session, slug: str):
    """Get a post by its slug"""
    return db.query(models.Post).filter(models.Post.slug == slug).first()

def increment_post_view(db: Session, post_id: int):
    """Increment the view count for a post"""
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if db_post:
        db_post.view_count = db_post.view_count + 1
        db.commit()
        db.refresh(db_post)
    return db_post

def get_posts_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def create_user_post(db: Session, post: schemas.PostCreate, user_id: int):
    # Generate unique slug from title
    base_slug = generate_slug(post.title)
    unique_slug = ensure_unique_slug(db, base_slug)
    
    # Skip automatic moderation in CRUD - will be handled at API level
    try:
        # For now, approve all posts and handle moderation at API level to avoid asyncio issues
        moderation_status = "approved"
        toxicity_score = 0.0
        moderation_reason = "Auto-approved - moderation handled at API level"
        logger.info("Post auto-approved - moderation will be handled asynchronously")
            
    except Exception as e:
        logger.error(f"Error in post creation: {e}. Defaulting to approved.")
        moderation_status = "approved"
        toxicity_score = 0.0
        moderation_reason = "Auto-approved due to error"
    
    db_post = models.Post(
        title=post.title, 
        slug=unique_slug,
        content=post.content, 
        category=post.category, 
        user_id=user_id,
        view_count=0,
        moderation_status=moderation_status,
        moderation_reason=moderation_reason,
        toxicity_score=toxicity_score
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    
    # Create tags if provided
    if post.tags:
        for tag_name in post.tags:
            db_tag = models.Tag(post_id=db_post.id, tag_name=tag_name.strip())
            db.add(db_tag)
        db.commit()
        db.refresh(db_post)
    
    logger.info(f"Post created with moderation status: {moderation_status} (toxicity: {toxicity_score:.3f})")
    return db_post

def update_post(db: Session, post_id: int, post_update: schemas.PostUpdate):
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if db_post:
        update_data = post_update.model_dump(exclude_unset=True)
        
        # If title is being updated, regenerate slug
        if 'title' in update_data:
            base_slug = generate_slug(update_data['title'])
            unique_slug = ensure_unique_slug(db, base_slug, post_id)
            update_data['slug'] = unique_slug
        
        # Update fields
        for key, value in update_data.items():
            if key != 'tags':  # Handle tags separately
                setattr(db_post, key, value)
        
        db.commit()
        db.refresh(db_post)
    return db_post

def get_posts_by_category(db: Session, category: str, genre: Optional[str] = None, skip: int = 0, limit: int = 6):
    """
    Get posts by category and optionally by genre
    """
    query = db.query(models.Post).filter(models.Post.category == category)
    if genre:
        query = query.filter(models.Post.genre == genre)
    return query.order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_posts_by_category_sorted(db: Session, category: str, genre: Optional[str] = None, sort_by: str = "newest", skip: int = 0, limit: int = 6):
    """
    Get posts by category with sorting options: newest, most_liked, random
    """
    query = db.query(models.Post).filter(models.Post.category == category)
    if genre:
        query = query.filter(models.Post.genre == genre)
    
    if sort_by == "newest":
        query = query.order_by(models.Post.created_at.desc())
    elif sort_by == "most_liked":
        # Order by number of likes (count of likes relationship)
        query = query.outerjoin(models.Like).group_by(models.Post.id).order_by(func.count(models.Like.id).desc())
    elif sort_by == "random":
        query = query.order_by(func.random())
    else:
        # Default to newest
        query = query.order_by(models.Post.created_at.desc())
    
    return query.offset(skip).limit(limit).all()

def get_distinct_categories_used(db: Session, user_id: Optional[int] = None):
    """
    Get distinct categories that are actually used in posts
    """
    query = db.query(models.Post.category).distinct()
    if user_id:
        query = query.filter(models.Post.user_id == user_id)
    
    categories = query.filter(models.Post.category != None, models.Post.category != '').all()
    return [cat.category for cat in categories if cat.category]

def update_user_social_links(db: Session, user_id: int, social_data: dict):
    """
    Update user's social media and donation links
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    
    # Update social media links
    user.facebook_url = social_data.get('facebook_url', '').strip() or None
    user.tiktok_url = social_data.get('tiktok_url', '').strip() or None
    user.instagram_url = social_data.get('instagram_url', '').strip() or None
    user.x_url = social_data.get('x_url', '').strip() or None
    user.bluesky_url = social_data.get('bluesky_url', '').strip() or None
    
    # Update donation links
    user.patreon_url = social_data.get('patreon_url', '').strip() or None
    user.paypal_url = social_data.get('paypal_url', '').strip() or None
    user.buymeacoffee_url = social_data.get('buymeacoffee_url', '').strip() or None
    
    db.commit()
    db.refresh(user)
    return user

def delete_post(db: Session, post_id: int):
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if db_post:
        db.delete(db_post)
        db.commit()
    return db_post

def create_comment(db: Session, comment: schemas.CommentCreate, post_id: int, user_id: Optional[int] = None):
    # Skip automatic moderation in CRUD - will be handled at API level
    try:
        # For now, approve all comments and handle moderation at API level to avoid asyncio issues
        moderation_status = "approved"
        approved = True
        toxicity_score = 0.0
        moderation_reason = "Auto-approved - moderation handled at API level"
        logger.info("Comment auto-approved - moderation will be handled asynchronously")
            
    except Exception as e:
        logger.error(f"Error in comment creation: {e}. Defaulting to approved.")
        moderation_status = "approved"
        approved = True
        toxicity_score = 0.0
        moderation_reason = "Auto-approved due to error"
    
    db_comment = models.Comment(
        post_id=post_id,
        user_id=user_id,
        author_name=comment.author_name,
        author_email=comment.author_email,
        content=comment.content,
        approved=approved,
        moderation_status=moderation_status,
        moderation_reason=moderation_reason,
        toxicity_score=toxicity_score
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    logger.info(f"Comment created with moderation status: {moderation_status} (toxicity: {toxicity_score:.3f})")
    return db_comment

def get_comments_for_post(db: Session, post_id: int, approved_only: bool = True):
    query = db.query(models.Comment).filter(models.Comment.post_id == post_id)
    if approved_only:
        query = query.filter(models.Comment.approved == True)
    return query.order_by(models.Comment.created_at.desc()).all()

def get_unapproved_comments_for_user_posts(db: Session, user_id: int):
    return db.query(models.Comment).join(models.Post).filter(
        models.Post.user_id == user_id,
        models.Comment.approved == False
    ).order_by(models.Comment.created_at.desc()).all()

def get_posts_for_moderation(db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Get posts that need moderation (flagged or rejected)"""
    query = db.query(models.Post)
    
    if status_filter:
        query = query.filter(models.Post.moderation_status == status_filter)
    else:
        # Get posts that need attention (flagged, pending, or rejected)
        query = query.filter(models.Post.moderation_status.in_(["flagged", "pending", "rejected"]))
    
    return query.order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_comments_for_moderation(db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Get comments that need moderation (flagged or rejected)"""
    query = db.query(models.Comment)
    
    if status_filter:
        query = query.filter(models.Comment.moderation_status == status_filter)
    else:
        # Get comments that need attention (flagged, pending, or rejected)
        query = query.filter(models.Comment.moderation_status.in_(["flagged", "pending", "rejected"]))
    
    return query.order_by(models.Comment.created_at.desc()).offset(skip).limit(limit).all()

def get_moderation_stats(db: Session):
    """Get statistics for moderation dashboard"""
    stats = {}
    
    # Count posts by moderation status
    stats['posts_pending'] = db.query(models.Post).filter(models.Post.moderation_status == "pending").count()
    stats['posts_flagged'] = db.query(models.Post).filter(models.Post.moderation_status == "flagged").count()
    stats['posts_rejected'] = db.query(models.Post).filter(models.Post.moderation_status == "rejected").count()
    stats['posts_approved'] = db.query(models.Post).filter(models.Post.moderation_status == "approved").count()
    
    # Count comments by moderation status
    stats['comments_pending'] = db.query(models.Comment).filter(models.Comment.moderation_status == "pending").count()
    stats['comments_flagged'] = db.query(models.Comment).filter(models.Comment.moderation_status == "flagged").count()
    stats['comments_rejected'] = db.query(models.Comment).filter(models.Comment.moderation_status == "rejected").count()
    stats['comments_approved'] = db.query(models.Comment).filter(models.Comment.moderation_status == "approved").count()
    
    # Total counts for dashboard
    stats['total_pending'] = stats['posts_pending'] + stats['comments_pending']
    stats['total_flagged'] = stats['posts_flagged'] + stats['comments_flagged']
    stats['total_rejected'] = stats['posts_rejected'] + stats['comments_rejected']
    
    return stats

def approve_content(db: Session, content_type: str, content_id: int, moderator_id: int, reason: str = ""):
    """Approve a post or comment"""
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
        
        # For comments, also set approved flag
        if content_type == "comment":
            content.approved = True
            
        db.commit()
        db.refresh(content)
        logger.info(f"Content {content_type} {content_id} approved by moderator {moderator_id}")
        return content
    return None

def reject_content(db: Session, content_type: str, content_id: int, moderator_id: int, reason: str = ""):
    """Reject a post or comment"""
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
        
        # For comments, ensure approved flag is False
        if content_type == "comment":
            content.approved = False
            
        db.commit()
        db.refresh(content)
        logger.info(f"Content {content_type} {content_id} rejected by moderator {moderator_id}")
        return content
    return None

def approve_comment(db: Session, comment_id: int):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if db_comment:
        db_comment.approved = True
        db.commit()
        db.refresh(db_comment)
    return db_comment

def delete_comment(db: Session, comment_id: int):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if db_comment:
        db.delete(db_comment)
        db.commit()
    return db_comment

def create_like(db: Session, post_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None):
    # Check if like already exists
    existing_like = None
    if user_id:
        existing_like = db.query(models.Like).filter(
            models.Like.post_id == post_id, models.Like.user_id == user_id
        ).first()
    elif ip_address:
        existing_like = db.query(models.Like).filter(
            models.Like.post_id == post_id, models.Like.ip_address == ip_address
        ).first()
    
    if existing_like:
        return None # Already liked

    db_like = models.Like(post_id=post_id, user_id=user_id, ip_address=ip_address)
    db.add(db_like)
    db.commit()
    db.refresh(db_like)
    return db_like

def get_likes_count_for_post(db: Session, post_id: int):
    return db.query(models.Like).filter(models.Like.post_id == post_id).count()

def get_random_posts(db: Session, limit: int = 10):
    from sqlalchemy.orm import joinedload
    return db.query(models.Post).options(joinedload(models.Post.owner)).order_by(func.rand()).limit(limit).all()

def get_random_posts_by_category(db: Session, category: str, limit: int = 10):
    """Get random posts filtered by a specific category"""
    from sqlalchemy.orm import joinedload
    return db.query(models.Post).options(joinedload(models.Post.owner)).filter(models.Post.category == category).order_by(func.rand()).limit(limit).all()

def get_random_posts_by_categories(db: Session, categories: List[str], limit: int = 10):
    """Get random posts filtered by multiple categories (for 'altele')"""
    from sqlalchemy.orm import joinedload
    return db.query(models.Post).options(joinedload(models.Post.owner)).filter(models.Post.category.in_(categories)).order_by(func.rand()).limit(limit).all()

def get_random_users(db: Session, limit: int = 10):
    return db.query(models.User).order_by(func.rand()).limit(limit).all()

def get_latest_posts_for_user(db: Session, user_id: int, limit: int = 10):
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).limit(limit).all()

def get_post_with_owner(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

# Tag CRUD functions
def create_tag(db: Session, post_id: int, tag_name: str):
    """Create a new tag for a post"""
    db_tag = models.Tag(post_id=post_id, tag_name=tag_name.strip())
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

def get_tags_for_post(db: Session, post_id: int):
    """Get all tags for a specific post"""
    return db.query(models.Tag).filter(models.Tag.post_id == post_id).all()

def get_tag_suggestions(db: Session, query: str, limit: int = 10):
    """Get tag suggestions based on partial query"""
    return db.query(models.Tag.tag_name).distinct().filter(
        models.Tag.tag_name.like(f"%{query}%")
    ).limit(limit).all()

def get_posts_by_tag(db: Session, tag_name: str, skip: int = 0, limit: int = 20):
    """Get posts that have a specific tag"""
    return db.query(models.Post).join(models.Tag).filter(
        models.Tag.tag_name == tag_name
    ).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def delete_tags_for_post(db: Session, post_id: int):
    """Delete all tags for a specific post"""
    db.query(models.Tag).filter(models.Tag.post_id == post_id).delete()
    db.commit()

# Best Friends CRUD functions
def get_best_friends_for_user(db: Session, user_id: int):
    """Get the best friends for a specific user, ordered by position"""
    return db.query(models.BestFriend).filter(
        models.BestFriend.user_id == user_id
    ).order_by(models.BestFriend.position).all()

# Featured Posts CRUD functions
def get_featured_posts_for_user(db: Session, user_id: int):
    """Get the featured posts for a specific user, ordered by position"""
    return db.query(models.FeaturedPost).filter(
        models.FeaturedPost.user_id == user_id
    ).order_by(models.FeaturedPost.position).all()

def get_posts_by_month_year(db: Session, user_id: int, month: int, year: int, skip: int = 0, limit: int = 20):
    """Get posts for a specific user filtered by month and year"""
    return db.query(models.Post).filter(
        models.Post.user_id == user_id,
        func.MONTH(models.Post.created_at) == month,
        func.YEAR(models.Post.created_at) == year
    ).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_available_months_for_user(db: Session, user_id: int):
    """Get available months/years for a user's posts"""
    result = db.query(
        func.YEAR(models.Post.created_at).label('year'),
        func.MONTH(models.Post.created_at).label('month'),
        func.COUNT(models.Post.id).label('post_count')
    ).filter(
        models.Post.user_id == user_id
    ).group_by(
        func.YEAR(models.Post.created_at),
        func.MONTH(models.Post.created_at)
    ).order_by(
        func.YEAR(models.Post.created_at).desc(),
        func.MONTH(models.Post.created_at).desc()
    ).all()
    
    return [{"year": r.year, "month": r.month, "post_count": r.post_count} for r in result]

# User Awards CRUD functions
def get_user_awards(db: Session, user_id: int):
    """Get all awards for a specific user, ordered by date"""
    return db.query(models.UserAward).filter(
        models.UserAward.user_id == user_id
    ).order_by(models.UserAward.award_date.desc()).all()

def get_user_total_likes(db: Session, user_id: int):
    """Get total likes received by a user across all their posts"""
    return db.query(func.count(models.Like.id)).join(
        models.Post, models.Like.post_id == models.Post.id
    ).filter(models.Post.user_id == user_id).scalar() or 0

def get_user_total_comments(db: Session, user_id: int):
    """Get total approved comments received by a user across all their posts"""
    return db.query(func.count(models.Comment.id)).join(
        models.Post, models.Comment.post_id == models.Post.id
    ).filter(
        models.Post.user_id == user_id,
        models.Comment.approved == True
    ).scalar() or 0

# ===================================
# MESSAGES CRUD FUNCTIONS
# ===================================

def get_or_create_conversation(db: Session, user1_id: int, user2_id: int) -> models.Conversation:
    """Get existing conversation between two users or create a new one"""
    # Ensure user1_id is smaller than user2_id for consistent ordering
    if user1_id > user2_id:
        user1_id, user2_id = user2_id, user1_id
    
    # Try to find existing conversation
    conversation = db.query(models.Conversation).filter(
        models.Conversation.user1_id == user1_id,
        models.Conversation.user2_id == user2_id
    ).first()
    
    if not conversation:
        # Create new conversation
        conversation = models.Conversation(
            user1_id=user1_id,
            user2_id=user2_id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    return conversation

def get_user_conversations(db: Session, user_id: int, limit: int = 50):
    """Get all conversations for a user with latest message info"""
    conversations = db.query(models.Conversation).filter(
        or_(
            models.Conversation.user1_id == user_id,
            models.Conversation.user2_id == user_id
        )
    ).order_by(models.Conversation.updated_at.desc()).limit(limit).all()
    
    # Load messages for each conversation to get latest message
    for conversation in conversations:
        latest_message = db.query(models.Message).filter(
            models.Message.conversation_id == conversation.id
        ).order_by(models.Message.created_at.desc()).first()
        conversation._latest_message = latest_message
    
    return conversations

def get_conversation_by_id(db: Session, conversation_id: int, user_id: int) -> Optional[models.Conversation]:
    """Get a conversation by ID, but only if the user is a participant"""
    return db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        or_(
            models.Conversation.user1_id == user_id,
            models.Conversation.user2_id == user_id
        )
    ).first()

def get_conversation_messages(db: Session, conversation_id: int, user_id: int, limit: int = 50, offset: int = 0):
    """Get messages for a conversation, but only if user is a participant"""
    # First verify user is part of the conversation
    conversation = get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        return []
    
    return db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(models.Message.created_at.desc()).limit(limit).offset(offset).all()

def create_message(db: Session, conversation_id: int, sender_id: int, content: str) -> Optional[models.Message]:
    """Create a new message in a conversation"""
    # Verify sender is part of the conversation
    conversation = get_conversation_by_id(db, conversation_id, sender_id)
    if not conversation:
        return None
    
    message = models.Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content.strip(),
        is_read=False
    )
    
    db.add(message)
    
    # Update conversation's updated_at timestamp
    conversation.updated_at = func.now()
    db.add(conversation)
    
    db.commit()
    db.refresh(message)
    
    return message

def send_message_to_user(db: Session, sender_id: int, recipient_username: str, content: str) -> Optional[models.Message]:
    """Send a message to a user by their username"""
    # Get recipient user
    recipient = get_user_by_username(db, recipient_username)
    if not recipient or recipient.id == sender_id:
        return None
    
    # Get or create conversation
    conversation = get_or_create_conversation(db, sender_id, recipient.id)
    
    # Create message
    return create_message(db, conversation.id, sender_id, content)

def mark_messages_as_read(db: Session, conversation_id: int, user_id: int):
    """Mark all unread messages in a conversation as read for a specific user"""
    # Verify user is part of the conversation
    conversation = get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        return False
    
    # Mark messages from the other user as read
    db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id,
        models.Message.sender_id != user_id,
        models.Message.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    return True

def get_unread_message_count(db: Session, user_id: int) -> int:
    """Get count of unread messages for a user"""
    # Get all conversations where user is a participant
    user_conversations = db.query(models.Conversation.id).filter(
        or_(
            models.Conversation.user1_id == user_id,
            models.Conversation.user2_id == user_id
        )
    ).subquery()
    
    # Count unread messages from other users in those conversations
    return db.query(func.count(models.Message.id)).filter(
        models.Message.conversation_id.in_(user_conversations),
        models.Message.sender_id != user_id,
        models.Message.is_read == False
    ).scalar() or 0

def delete_conversation(db: Session, conversation_id: int, user_id: int) -> bool:
    """Delete a conversation (only if user is a participant)"""
    conversation = get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        return False
    
    db.delete(conversation)
    db.commit()
    return True

def search_conversations(db: Session, user_id: int, query: str, limit: int = 20):
    """Search conversations by other user's username or latest message content"""
    if not query or len(query.strip()) < 2:
        return []
    
    query = f"%{query.strip()}%"
    
    # Get conversations where user is a participant
    conversations = db.query(models.Conversation).filter(
        or_(
            models.Conversation.user1_id == user_id,
            models.Conversation.user2_id == user_id
        )
    ).all()
    
    matching_conversations = []
    
    for conv in conversations:
        other_user = conv.get_other_user(user_id)
        
        # Check if other user's username matches
        if query.lower().replace('%', '') in other_user.username.lower():
            matching_conversations.append(conv)
            continue
        
        # Check if any message content matches
        message_match = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id,
            models.Message.content.ilike(query)
        ).first()
        
        if message_match:
            matching_conversations.append(conv)
    
    return matching_conversations[:limit]
