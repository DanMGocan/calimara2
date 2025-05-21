from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from . import models, schemas
from passlib.context import CryptContext
from typing import Optional, List
import random

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    db_user = models.User(username=user.username, email=user.email, password_hash=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_post(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_posts_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Post).filter(models.Post.user_id == user_id).offset(skip).limit(limit).all()

def create_user_post(db: Session, post: schemas.PostCreate, user_id: int):
    db_post = models.Post(title=post.title, content=post.content, user_id=user_id)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def update_post(db: Session, post_id: int, post_update: schemas.PostUpdate):
    db_post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if db_post:
        for key, value in post_update.model_dump(exclude_unset=True).items():
            setattr(db_post, key, value)
        db.commit()
        db.refresh(db_post)
    return db_post

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

def get_random_users(db: Session, limit: int = 10):
    return db.query(models.User).order_by(func.rand()).limit(limit).all()

def get_latest_posts_for_user(db: Session, user_id: int, limit: int = 10):
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).limit(limit).all()

def get_post_with_owner(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()
