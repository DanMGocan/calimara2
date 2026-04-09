from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, or_, extract, text
from . import models, schemas, moderation
from typing import Optional, List
import bleach
import random
import re
import unicodedata
import asyncio
import logging

logger = logging.getLogger(__name__)

# HTML sanitization: only allow tags produced by Quill editor
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 's', 'ol', 'ul', 'li',
    'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'img',
    'span', 'pre', 'code', 'sub', 'sup',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height'],
    'span': ['class'],
    'pre': ['class'],
    'code': ['class'],
}

def sanitize_html(content: str) -> str:
    """Sanitize HTML content, allowing only safe tags from the Quill editor."""
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )

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
    return db.query(models.Post).options(
        selectinload(models.Post.comments).joinedload(models.Comment.commenter),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).filter(models.Post.slug == slug).first()

def increment_post_view(db: Session, post_id: int):
    """Increment the view count for a post atomically"""
    db.query(models.Post).filter(models.Post.id == post_id).update(
        {models.Post.view_count: models.Post.view_count + 1},
        synchronize_session="fetch"
    )
    db.commit()
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_posts_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def create_user_post(db: Session, post: schemas.PostCreate, user_id: int):
    # Generate unique slug from title
    base_slug = generate_slug(post.title)
    unique_slug = ensure_unique_slug(db, base_slug)
    
    # Create post with pending status - moderation will be handled at API level
    moderation_status = "pending"
    toxicity_score = 0.0
    moderation_reason = "Awaiting AI moderation"
    
    db_post = models.Post(
        title=post.title,
        slug=unique_slug,
        content=sanitize_html(post.content),
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
    
    logger.info(f"Post created with moderation status: {moderation_status} - awaiting AI moderation")
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
        
        # Sanitize content if being updated
        if 'content' in update_data:
            update_data['content'] = sanitize_html(update_data['content'])

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
    query = db.query(models.Post).options(
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).filter(models.Post.category == category)
    if genre:
        query = query.filter(models.Post.genre == genre)
    return query.order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_posts_by_category_sorted(db: Session, category: str, genre: Optional[str] = None, sort_by: str = "newest", skip: int = 0, limit: int = 6):
    """
    Get posts by category with sorting options: newest, most_liked, random
    """
    query = db.query(models.Post).options(
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).filter(models.Post.category == category)
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
    # Create comment with pending status - moderation will be handled at API level
    moderation_status = "pending"
    approved = False  # Will be set to True by moderation if approved
    toxicity_score = 0.0
    moderation_reason = "Awaiting AI moderation"
    
    db_comment = models.Comment(
        post_id=post_id,
        user_id=user_id,
        author_name=comment.author_name,
        author_email=comment.author_email,
        content=sanitize_html(comment.content),
        approved=approved,
        moderation_status=moderation_status,
        moderation_reason=moderation_reason,
        toxicity_score=toxicity_score
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    logger.info(f"Comment created with moderation status: {moderation_status} - awaiting AI moderation")
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
    """Get posts for moderation dashboard - ALL posts with their moderation status"""
    query = db.query(models.Post)
    
    if status_filter:
        query = query.filter(models.Post.moderation_status == status_filter)
    # If no status filter, return ALL posts to show complete moderation history
    
    return query.order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_comments_for_moderation(db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50):
    """Get comments for moderation dashboard - ALL comments with their moderation status"""
    query = db.query(models.Comment)
    
    if status_filter:
        query = query.filter(models.Comment.moderation_status == status_filter)
    # If no status filter, return ALL comments to show complete moderation history
    
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
    return db.query(models.Post).options(
        joinedload(models.Post.owner),
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).order_by(func.random()).limit(limit).all()

def get_random_posts_by_category(db: Session, category: str, limit: int = 10):
    """Get random posts filtered by a specific category"""
    return db.query(models.Post).options(
        joinedload(models.Post.owner),
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).filter(models.Post.category == category).order_by(func.random()).limit(limit).all()

def get_random_posts_by_categories(db: Session, categories: List[str], limit: int = 10):
    """Get random posts filtered by multiple categories (for 'altele')"""
    return db.query(models.Post).options(
        joinedload(models.Post.owner),
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).filter(models.Post.category.in_(categories)).order_by(func.random()).limit(limit).all()

def get_random_users(db: Session, limit: int = 10):
    return db.query(models.User).order_by(func.random()).limit(limit).all()

def get_latest_posts_for_user(db: Session, user_id: int, limit: int = 10):
    return db.query(models.Post).options(
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).limit(limit).all()

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
    return db.query(models.Post).options(
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).join(models.Tag).filter(
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
    return db.query(models.FeaturedPost).options(
        joinedload(models.FeaturedPost.post).selectinload(models.Post.comments),
        joinedload(models.FeaturedPost.post).selectinload(models.Post.tags),
        joinedload(models.FeaturedPost.post).selectinload(models.Post.likes)
    ).filter(
        models.FeaturedPost.user_id == user_id
    ).order_by(models.FeaturedPost.position).all()

def get_posts_by_month_year(db: Session, user_id: int, month: int, year: int, skip: int = 0, limit: int = 20):
    """Get posts for a specific user filtered by month and year"""
    return db.query(models.Post).options(
        selectinload(models.Post.comments),
        selectinload(models.Post.tags),
        selectinload(models.Post.likes)
    ).filter(
        models.Post.user_id == user_id,
        extract('month', models.Post.created_at) == month,
        extract('year', models.Post.created_at) == year
    ).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_available_months_for_user(db: Session, user_id: int):
    """Get available months/years for a user's posts"""
    result = db.query(
        extract('year', models.Post.created_at).label('year'),
        extract('month', models.Post.created_at).label('month'),
        func.count(models.Post.id).label('post_count')
    ).filter(
        models.Post.user_id == user_id
    ).group_by(
        extract('year', models.Post.created_at),
        extract('month', models.Post.created_at)
    ).order_by(
        extract('year', models.Post.created_at).desc(),
        extract('month', models.Post.created_at).desc()
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
    from sqlalchemy import select
    
    # Get all conversations where user is a participant
    user_conversations_query = select(models.Conversation.id).filter(
        or_(
            models.Conversation.user1_id == user_id,
            models.Conversation.user2_id == user_id
        )
    )
    
    # Count unread messages from other users in those conversations
    return db.query(func.count(models.Message.id)).filter(
        models.Message.conversation_id.in_(user_conversations_query),
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

# --- Moderation Log CRUD Functions ---

def get_moderation_logs(db: Session, limit: int = 100, offset: int = 0):
    """Get all moderation logs with pagination"""
    return db.query(models.ModerationLog)\
        .order_by(models.ModerationLog.created_at.desc())\
        .offset(offset).limit(limit).all()

def get_moderation_logs_for_review(db: Session, limit: int = 50):
    """Get moderation logs that need human review (AI flagged content)"""
    return db.query(models.ModerationLog)\
        .filter(models.ModerationLog.ai_decision == "flagged")\
        .filter(or_(
            models.ModerationLog.human_decision.is_(None),
            models.ModerationLog.human_decision == "pending"
        ))\
        .order_by(models.ModerationLog.created_at.desc())\
        .limit(limit).all()

def get_moderation_logs_by_decision(db: Session, ai_decision: str, limit: int = 50):
    """Get moderation logs filtered by AI decision"""
    return db.query(models.ModerationLog)\
        .filter(models.ModerationLog.ai_decision == ai_decision)\
        .order_by(models.ModerationLog.created_at.desc())\
        .limit(limit).all()

def get_moderation_log_by_content(db: Session, content_type: str, content_id: int):
    """Get moderation log for specific content"""
    return db.query(models.ModerationLog)\
        .filter(models.ModerationLog.content_type == content_type)\
        .filter(models.ModerationLog.content_id == content_id)\
        .first()

def update_moderation_log_human_decision(
    db: Session, 
    log_id: int, 
    human_decision: str, 
    human_reason: str, 
    moderator_id: int
):
    """Update moderation log with human moderator decision"""
    log = db.query(models.ModerationLog).filter(models.ModerationLog.id == log_id).first()
    if log:
        log.human_decision = human_decision
        log.human_reason = human_reason
        log.moderated_by = moderator_id
        log.moderated_at = func.now()
        db.commit()
        db.refresh(log)
    return log

def get_moderation_stats_extended(db: Session):
    """Get extended moderation statistics including logs"""
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # AI decision counts
    ai_approved = db.query(models.ModerationLog).filter(models.ModerationLog.ai_decision == "approved").count()
    ai_flagged = db.query(models.ModerationLog).filter(models.ModerationLog.ai_decision == "flagged").count()
    ai_rejected = db.query(models.ModerationLog).filter(models.ModerationLog.ai_decision == "rejected").count()
    
    # Human review counts
    pending_review = db.query(models.ModerationLog)\
        .filter(models.ModerationLog.ai_decision == "flagged")\
        .filter(or_(
            models.ModerationLog.human_decision.is_(None),
            models.ModerationLog.human_decision == "pending"
        )).count()
    
    human_approved = db.query(models.ModerationLog).filter(models.ModerationLog.human_decision == "approved").count()
    human_rejected = db.query(models.ModerationLog).filter(models.ModerationLog.human_decision == "rejected").count()
    
    # Today's activity
    today_logs = db.query(models.ModerationLog)\
        .filter(func.date(models.ModerationLog.created_at) == today).count()
    
    return {
        "ai_decisions": {
            "approved": ai_approved,
            "flagged": ai_flagged,
            "rejected": ai_rejected
        },
        "human_review": {
            "pending": pending_review,
            "approved": human_approved,
            "rejected": human_rejected
        },
        "today_activity": today_logs,
        "total_logs": ai_approved + ai_flagged + ai_rejected
    }


# --- Theme Analysis ---

def get_distinct_themes(db: Session) -> List[str]:
    """Get all distinct theme values across analyzed posts."""
    result = db.execute(
        text("SELECT DISTINCT jsonb_array_elements_text(themes) AS theme FROM posts WHERE theme_analysis_status = 'completed' AND themes != '[]'::jsonb")
    )
    return [row[0] for row in result]


def get_distinct_feelings(db: Session) -> List[str]:
    """Get all distinct feeling values across analyzed posts."""
    result = db.execute(
        text("SELECT DISTINCT jsonb_array_elements_text(feelings) AS feeling FROM posts WHERE theme_analysis_status = 'completed' AND feelings != '[]'::jsonb")
    )
    return [row[0] for row in result]


def update_post_theme_analysis(db: Session, post_id: int, themes: list, feelings: list, status: str):
    """Update a post's theme analysis results."""
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post:
        post.themes = themes
        post.feelings = feelings
        post.theme_analysis_status = status
        db.commit()


# ===================================
# DRAMA CRUD FUNCTIONS
# ===================================

def create_drama(db: Session, title: str, description: Optional[str], slug: str, user_id: int, character_name: str, character_description: Optional[str] = None) -> models.Drama:
    """Create a new drama and its first character (the creator)"""
    drama = models.Drama(
        user_id=user_id,
        title=title,
        slug=slug,
        description=description
    )
    db.add(drama)
    db.flush()  # Get the drama.id

    character = models.DramaCharacter(
        drama_id=drama.id,
        user_id=user_id,
        character_name=character_name,
        character_description=character_description,
        is_creator=True
    )
    db.add(character)
    db.commit()
    db.refresh(drama)
    return drama

def get_drama_by_slug(db: Session, slug: str) -> Optional[models.Drama]:
    """Get a drama by slug with all relationships eager-loaded"""
    return db.query(models.Drama).options(
        selectinload(models.Drama.characters).joinedload(models.DramaCharacter.user),
        selectinload(models.Drama.acts).selectinload(models.DramaAct.replies).joinedload(models.DramaReply.character),
        selectinload(models.Drama.likes),
        selectinload(models.Drama.comments).joinedload(models.DramaComment.commenter),
        joinedload(models.Drama.owner)
    ).filter(models.Drama.slug == slug).first()

def get_drama_by_id(db: Session, drama_id: int) -> Optional[models.Drama]:
    return db.query(models.Drama).filter(models.Drama.id == drama_id).first()

def get_dramas_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> List[models.Drama]:
    return db.query(models.Drama).options(
        selectinload(models.Drama.characters),
        selectinload(models.Drama.likes),
        joinedload(models.Drama.owner)
    ).filter(models.Drama.user_id == user_id).order_by(models.Drama.created_at.desc()).offset(skip).limit(limit).all()

def get_all_dramas(db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[models.Drama]:
    """Get dramas across the platform for discovery page"""
    query = db.query(models.Drama).options(
        selectinload(models.Drama.characters),
        selectinload(models.Drama.likes),
        joinedload(models.Drama.owner)
    )
    if status_filter:
        query = query.filter(models.Drama.status == status_filter)
    return query.order_by(models.Drama.created_at.desc()).offset(skip).limit(limit).all()

def update_drama(db: Session, drama_id: int, update_data: dict) -> Optional[models.Drama]:
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        for key, value in update_data.items():
            if value is not None:
                setattr(drama, key, value)
        db.commit()
        db.refresh(drama)
    return drama

def delete_drama(db: Session, drama_id: int):
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        db.delete(drama)
        db.commit()
    return drama

def complete_drama(db: Session, drama_id: int) -> Optional[models.Drama]:
    """Mark drama as completed and close all active acts"""
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        drama.status = "completed"
        drama.is_open_for_applications = False
        # Complete any active acts
        for act in drama.acts:
            if act.status == "active":
                act.status = "completed"
        db.commit()
        db.refresh(drama)
    return drama

def increment_drama_view(db: Session, drama_id: int):
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        drama.view_count = drama.view_count + 1
        db.commit()

def ensure_unique_drama_slug(db: Session, base_slug: str, drama_id: Optional[int] = None) -> str:
    """Ensure the drama slug is unique"""
    slug = base_slug
    counter = 1
    while True:
        query = db.query(models.Drama).filter(models.Drama.slug == slug)
        if drama_id:
            query = query.filter(models.Drama.id != drama_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 100:
            slug = f"{base_slug}-{random.randint(1000, 9999)}"
            break
    return slug

def get_drama_character(db: Session, character_id: int) -> Optional[models.DramaCharacter]:
    return db.query(models.DramaCharacter).filter(models.DramaCharacter.id == character_id).first()

def get_character_for_user_in_drama(db: Session, drama_id: int, user_id: int) -> Optional[models.DramaCharacter]:
    return db.query(models.DramaCharacter).filter(
        models.DramaCharacter.drama_id == drama_id,
        models.DramaCharacter.user_id == user_id
    ).first()

def create_drama_character(db: Session, drama_id: int, user_id: int, character_name: str, character_description: Optional[str] = None, is_creator: bool = False) -> models.DramaCharacter:
    character = models.DramaCharacter(
        drama_id=drama_id,
        user_id=user_id,
        character_name=character_name,
        character_description=character_description,
        is_creator=is_creator
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    return character

def delete_drama_character(db: Session, character_id: int):
    character = db.query(models.DramaCharacter).filter(models.DramaCharacter.id == character_id).first()
    if character:
        db.delete(character)
        db.commit()
    return character

def create_drama_act(db: Session, drama_id: int, title: str, setting: Optional[str] = None) -> models.DramaAct:
    """Create a new act, auto-calculating act_number"""
    max_act = db.query(func.max(models.DramaAct.act_number)).filter(
        models.DramaAct.drama_id == drama_id
    ).scalar() or 0
    act = models.DramaAct(
        drama_id=drama_id,
        act_number=max_act + 1,
        title=title,
        setting=setting
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act

def get_drama_act(db: Session, drama_id: int, act_number: int) -> Optional[models.DramaAct]:
    return db.query(models.DramaAct).options(
        selectinload(models.DramaAct.replies).joinedload(models.DramaReply.character)
    ).filter(
        models.DramaAct.drama_id == drama_id,
        models.DramaAct.act_number == act_number
    ).first()

def update_drama_act(db: Session, act_id: int, update_data: dict) -> Optional[models.DramaAct]:
    act = db.query(models.DramaAct).filter(models.DramaAct.id == act_id).first()
    if act:
        for key, value in update_data.items():
            if value is not None:
                setattr(act, key, value)
        db.commit()
        db.refresh(act)
    return act

def complete_drama_act(db: Session, act_id: int) -> Optional[models.DramaAct]:
    act = db.query(models.DramaAct).filter(models.DramaAct.id == act_id).first()
    if act:
        act.status = "completed"
        db.commit()
        db.refresh(act)
    return act

def create_drama_reply(db: Session, act_id: int, character_id: int, content: str, stage_direction: Optional[str] = None) -> models.DramaReply:
    """Create a reply with auto-calculated position"""
    max_position = db.query(func.max(models.DramaReply.position)).filter(
        models.DramaReply.act_id == act_id
    ).scalar() or 0
    reply = models.DramaReply(
        act_id=act_id,
        character_id=character_id,
        content=content,
        stage_direction=stage_direction,
        position=max_position + 1
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply

def get_drama_reply(db: Session, reply_id: int) -> Optional[models.DramaReply]:
    return db.query(models.DramaReply).options(
        joinedload(models.DramaReply.character)
    ).filter(models.DramaReply.id == reply_id).first()

def update_drama_reply(db: Session, reply_id: int, update_data: dict) -> Optional[models.DramaReply]:
    reply = db.query(models.DramaReply).filter(models.DramaReply.id == reply_id).first()
    if reply:
        for key, value in update_data.items():
            if value is not None:
                setattr(reply, key, value)
        db.commit()
        db.refresh(reply)
    return reply

def delete_drama_reply(db: Session, reply_id: int):
    reply = db.query(models.DramaReply).filter(models.DramaReply.id == reply_id).first()
    if reply:
        db.delete(reply)
        db.commit()
    return reply

def reorder_drama_replies(db: Session, act_id: int, reply_ids: List[int]):
    """Reorder replies by updating position based on the order of reply_ids"""
    for index, reply_id in enumerate(reply_ids):
        reply = db.query(models.DramaReply).filter(
            models.DramaReply.id == reply_id,
            models.DramaReply.act_id == act_id
        ).first()
        if reply:
            reply.position = index + 1
    db.commit()

def create_drama_like(db: Session, drama_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None) -> Optional[models.DramaLike]:
    """Create a drama like (checking for duplicates)"""
    existing_like = None
    if user_id:
        existing_like = db.query(models.DramaLike).filter(
            models.DramaLike.drama_id == drama_id, models.DramaLike.user_id == user_id
        ).first()
    elif ip_address:
        existing_like = db.query(models.DramaLike).filter(
            models.DramaLike.drama_id == drama_id, models.DramaLike.ip_address == ip_address
        ).first()
    if existing_like:
        return None
    like = models.DramaLike(drama_id=drama_id, user_id=user_id, ip_address=ip_address)
    db.add(like)
    db.commit()
    db.refresh(like)
    return like

def create_drama_comment(db: Session, drama_id: int, content: str, user_id: Optional[int] = None, author_name: Optional[str] = None) -> models.DramaComment:
    comment = models.DramaComment(
        drama_id=drama_id,
        user_id=user_id,
        author_name=author_name,
        content=content
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

def create_drama_invitation(db: Session, drama_id: int, from_user_id: int, to_user_id: int, inv_type: str, character_name: Optional[str] = None, message: Optional[str] = None) -> models.DramaInvitation:
    invitation = models.DramaInvitation(
        drama_id=drama_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        type=inv_type,
        character_name=character_name,
        message=message
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation

def get_drama_invitation(db: Session, invitation_id: int) -> Optional[models.DramaInvitation]:
    return db.query(models.DramaInvitation).options(
        joinedload(models.DramaInvitation.from_user),
        joinedload(models.DramaInvitation.to_user),
        joinedload(models.DramaInvitation.drama)
    ).filter(models.DramaInvitation.id == invitation_id).first()

def get_pending_invitations_for_drama(db: Session, drama_id: int) -> List[models.DramaInvitation]:
    return db.query(models.DramaInvitation).options(
        joinedload(models.DramaInvitation.from_user),
        joinedload(models.DramaInvitation.to_user)
    ).filter(
        models.DramaInvitation.drama_id == drama_id,
        models.DramaInvitation.status == "pending"
    ).all()

def respond_to_invitation(db: Session, invitation_id: int, status: str) -> Optional[models.DramaInvitation]:
    invitation = db.query(models.DramaInvitation).filter(models.DramaInvitation.id == invitation_id).first()
    if invitation:
        invitation.status = status
        invitation.responded_at = func.now()
        db.commit()
        db.refresh(invitation)
    return invitation

def get_user_dramas_as_participant(db: Session, user_id: int) -> List[models.Drama]:
    """Get all dramas where user is a participant (has a character)"""
    character_drama_ids = db.query(models.DramaCharacter.drama_id).filter(
        models.DramaCharacter.user_id == user_id
    ).subquery()
    return db.query(models.Drama).options(
        selectinload(models.Drama.characters),
        selectinload(models.Drama.likes),
        joinedload(models.Drama.owner)
    ).filter(models.Drama.id.in_(character_drama_ids)).order_by(models.Drama.updated_at.desc()).all()

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

def get_notifications_for_user(db: Session, user_id: int, skip: int = 0, limit: int = 20) -> List[models.Notification]:
    return db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).order_by(models.Notification.created_at.desc()).offset(skip).limit(limit).all()

def get_unread_notification_count(db: Session, user_id: int) -> int:
    return db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).scalar() or 0

def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Optional[models.Notification]:
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
