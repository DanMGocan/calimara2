import logging
from typing import Optional
from fastapi import HTTPException, status, Depends, Request
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from . import models, auth

logger = logging.getLogger(__name__)
_missing_table_warnings: set[str] = set()

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
            detail="Autentificare necesară"
        )
    
    if not is_admin(current_user):
        logger.warning(f"Unauthorized admin access attempt by {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces de administrare necesar"
        )
    
    return current_user

def require_moderator(current_user: Optional[models.User] = Depends(auth.get_current_user)) -> models.User:
    """Dependency that requires moderation privileges"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentificare necesară"
        )
    
    if not is_moderator(current_user):
        logger.warning(f"Unauthorized moderation access attempt by {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces de moderare necesar"
        )
    
    return current_user

def log_admin_action(admin_user: models.User, action: str, target_type: str, target_id: int, details: Optional[str] = None):
    """Log administrative actions for audit trail"""
    log_message = f"ADMIN ACTION: {admin_user.email} performed '{action}' on {target_type} ID {target_id}"
    if details:
        log_message += f" - {details}"
    logger.info(log_message)


def db_table_exists(db: Session, table_name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(table_name)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not inspect database table %s", table_name)
        return False


def warn_missing_table_once(table_name: str, context: str) -> None:
    key = f"{table_name}:{context}"
    if key in _missing_table_warnings:
        return
    _missing_table_warnings.add(key)
    logger.warning("%s table is missing; %s", table_name, context)


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if not request:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def write_admin_audit_log(
    db: Session,
    actor: models.User,
    *,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    reason: Optional[str] = None,
    request: Optional[Request] = None,
    extra_data: Optional[dict] = None,
) -> Optional[models.AdminAuditLog]:
    if not db_table_exists(db, models.AdminAuditLog.__tablename__):
        warn_missing_table_once(models.AdminAuditLog.__tablename__, "admin audit logging is disabled")
        return None
    try:
        entry = models.AdminAuditLog(
            actor_user_id=actor.id,
            actor_username=actor.username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            ip_address=_client_ip(request),
            user_agent=(request.headers.get("user-agent")[:2000] if request and request.headers.get("user-agent") else None),
            extra_data=extra_data or {},
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to write admin audit log action=%s target=%s id=%s", action, target_type, target_id)
        return None

def can_moderate_content(user: Optional[models.User]) -> bool:
    """Check if user can moderate content (currently only admin)"""
    return is_admin(user)

def can_suspend_users(user: Optional[models.User]) -> bool:
    """Check if user can suspend other users (currently only admin)"""
    return is_admin(user)
