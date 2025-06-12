from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from . import models, schemas
from passlib.context import CryptContext
from typing import Optional, List
import random
import re
import unicodedata

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

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    # Generate default avatar seed if not provided
    avatar_seed = user.avatar_seed or f"{user.username}-shapes"
    db_user = models.User(
        username=user.username, 
        email=user.email, 
        password_hash=hashed_password, 
        subtitle=user.subtitle,
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
    
    db_post = models.Post(
        title=post.title, 
        slug=unique_slug,
        content=post.content, 
        category=post.category, 
        user_id=user_id,
        view_count=0
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
    db_comment = models.Comment(
        post_id=post_id,
        user_id=user_id,
        author_name=comment.author_name,
        author_email=comment.author_email,
        content=comment.content
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

def get_unapproved_comments_for_user_posts(db: Session, user_id: int):
    return db.query(models.Comment).join(models.Post).filter(
        models.Post.user_id == user_id,
        models.Comment.approved == False
    ).order_by(models.Comment.created_at.desc()).all()

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
    return db.query(models.Post).order_by(func.rand()).limit(limit).all()

def get_random_posts_by_category(db: Session, category: str, limit: int = 10):
    """Get random posts filtered by a specific category"""
    return db.query(models.Post).filter(models.Post.category == category).order_by(func.rand()).limit(limit).all()

def get_random_posts_by_categories(db: Session, categories: List[str], limit: int = 10):
    """Get random posts filtered by multiple categories (for 'altele')"""
    return db.query(models.Post).filter(models.Post.category.in_(categories)).order_by(func.rand()).limit(limit).all()

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
