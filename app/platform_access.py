from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import admin, local_auth, models

SETTING_ID = 1
ACCESS_DENIED_MESSAGE = "Platforma este momentan disponibilă doar pentru emailurile adăugate în lista de acces."


def normalize_access_email(email: str) -> str:
    return local_auth.normalize_email(email)


def _tables_available(db: Session) -> bool:
    settings_table = models.PlatformAccessSetting.__tablename__
    emails_table = models.PlatformAllowedEmail.__tablename__
    if admin.db_table_exists(db, settings_table) and admin.db_table_exists(db, emails_table):
        return True
    admin.warn_missing_table_once(
        settings_table,
        "platform access gate is treated as closed until schema.sql has created the access tables",
    )
    return False


def get_setting(db: Session, *, create: bool = False) -> Optional[models.PlatformAccessSetting]:
    if not _tables_available(db):
        return None
    setting = db.query(models.PlatformAccessSetting).filter(models.PlatformAccessSetting.id == SETTING_ID).first()
    if setting or not create:
        return setting
    setting = models.PlatformAccessSetting(id=SETTING_ID, is_open=False)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def is_platform_open(db: Session) -> bool:
    setting = get_setting(db)
    return False if setting is None else bool(setting.is_open)


def is_email_allowed(db: Session, email: str) -> bool:
    if not _tables_available(db):
        return False
    normalized = normalize_access_email(email)
    if not normalized:
        return False
    return db.query(models.PlatformAllowedEmail).filter(models.PlatformAllowedEmail.email == normalized).first() is not None


def can_access_platform(db: Session, *, email: str, user: Optional[models.User] = None) -> bool:
    if is_platform_open(db):
        return True
    return is_email_allowed(db, email)


def set_platform_open(db: Session, *, is_open: bool, actor: Optional[models.User] = None) -> models.PlatformAccessSetting:
    setting = get_setting(db, create=True)
    if setting is None:
        raise RuntimeError("Platform access tables are missing.")
    setting.is_open = bool(is_open)
    setting.updated_by = actor.id if actor else None
    db.commit()
    db.refresh(setting)
    return setting


def list_allowed_emails(db: Session) -> list[models.PlatformAllowedEmail]:
    if not _tables_available(db):
        return []
    return (
        db.query(models.PlatformAllowedEmail)
        .order_by(models.PlatformAllowedEmail.created_at.desc(), models.PlatformAllowedEmail.id.desc())
        .all()
    )


def add_allowed_email(
    db: Session,
    *,
    email: str,
    note: Optional[str] = None,
    actor: Optional[models.User] = None,
) -> models.PlatformAllowedEmail:
    if not _tables_available(db):
        raise RuntimeError("Platform access tables are missing.")
    normalized = normalize_access_email(email)
    if not normalized:
        raise ValueError("Emailul este obligatoriu.")
    existing = db.query(models.PlatformAllowedEmail).filter(models.PlatformAllowedEmail.email == normalized).first()
    if existing:
        raise ValueError("Emailul este deja în lista de acces.")
    row = models.PlatformAllowedEmail(
        email=normalized,
        note=(note or "").strip() or None,
        created_by=actor.id if actor else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def remove_allowed_email(db: Session, email_id: int) -> Optional[models.PlatformAllowedEmail]:
    if not _tables_available(db):
        return None
    row = db.query(models.PlatformAllowedEmail).filter(models.PlatformAllowedEmail.id == email_id).first()
    if not row:
        return None
    db.delete(row)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return row
