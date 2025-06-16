import logging
from typing import Optional
from fastapi import HTTPException, status, Depends, Request
from sqlalchemy.orm import Session
from . import models, auth

logger = logging.getLogger(__name__)

def is_admin(user: Optional[models.User]) -> bool:
    """Check if user has admin privileges"""
    if not user:
        return False
    return user.is_admin

def is_moderator(user: Optional[models.User]) -> bool:
    """Check if user has moderation privileges"""
    if not user:
        return False
    return user.is_moderator or user.is_admin

def require_admin(current_user: Optional[models.User] = Depends(auth.get_current_user)) -> models.User:
    """Dependency that requires admin authentication"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if not is_admin(current_user):
        logger.warning(f"Unauthorized admin access attempt by {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user

def require_moderator(current_user: Optional[models.User] = Depends(auth.get_current_user)) -> models.User:
    """Dependency that requires moderation privileges"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if not is_moderator(current_user):
        logger.warning(f"Unauthorized moderation access attempt by {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderation access required"
        )
    
    return current_user

# Backward compatibility aliases
require_god_admin = require_admin
is_god_admin = is_admin

def log_admin_action(admin_user: models.User, action: str, target_type: str, target_id: int, details: Optional[str] = None):
    """Log administrative actions for audit trail"""
    log_message = f"ADMIN ACTION: {admin_user.email} performed '{action}' on {target_type} ID {target_id}"
    if details:
        log_message += f" - {details}"
    logger.info(log_message)

def can_moderate_content(user: Optional[models.User]) -> bool:
    """Check if user can moderate content (currently only god admin)"""
    return is_god_admin(user)

def can_suspend_users(user: Optional[models.User]) -> bool:
    """Check if user can suspend other users (currently only god admin)"""
    return is_god_admin(user)