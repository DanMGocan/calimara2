import os
import logging
from typing import Optional
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from . import models, auth

logger = logging.getLogger(__name__)

# Get god admin email from environment
GOD_ADMIN_EMAIL = os.getenv("GOD_ADMIN_EMAIL", "").lower()

def is_god_admin(user: Optional[models.User]) -> bool:
    """Check if user is the god admin"""
    if not user or not GOD_ADMIN_EMAIL:
        return False
    return user.email.lower() == GOD_ADMIN_EMAIL

def require_god_admin(current_user: Optional[models.User] = Depends(auth.get_current_user)) -> models.User:
    """Dependency that requires god admin authentication"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if not is_god_admin(current_user):
        logger.warning(f"Unauthorized admin access attempt by {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="God admin access required"
        )
    
    return current_user

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