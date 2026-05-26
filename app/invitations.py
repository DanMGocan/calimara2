from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import admin, local_auth, models
from .week_util import utcnow_naive

INVITATION_STATUSES = {"pending", "accepted", "revoked"}
PREMIUM_TIERS = {"free", "trubadur", "cronicar", "rapsod"}
DEFAULT_INVITATION_DAYS = 30
DEFAULT_PREMIUM_DAYS = 30


def _secret_key() -> bytes:
    secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("EMAIL_UNSUBSCRIBE_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET_KEY is required for invitation tokens.")
    return secret.encode("utf-8")


def _tables_available(db: Session) -> bool:
    table = models.PlatformInvitation.__tablename__
    if admin.db_table_exists(db, table):
        return True
    admin.warn_missing_table_once(
        table,
        "platform invitations are unavailable until schema.sql has created the table",
    )
    return False


def normalize_invitation_email(email: str) -> str:
    return local_auth.normalize_email(email)


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def hash_invitation_token(token: str) -> str:
    digest = hmac.new(_secret_key(), str(token or "").encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac_sha256${digest}"


def invitation_display_status(invitation: models.PlatformInvitation) -> str:
    if invitation.status != "pending":
        return invitation.status
    return "expired" if invitation.expires_at <= utcnow_naive() else "pending"


def list_invitations(db: Session) -> list[models.PlatformInvitation]:
    if not _tables_available(db):
        return []
    return (
        db.query(models.PlatformInvitation)
        .order_by(models.PlatformInvitation.created_at.desc(), models.PlatformInvitation.id.desc())
        .all()
    )


def get_invitation(db: Session, invitation_id: int) -> Optional[models.PlatformInvitation]:
    if not _tables_available(db):
        return None
    return db.query(models.PlatformInvitation).filter(models.PlatformInvitation.id == invitation_id).first()


def get_invitation_by_email(db: Session, email: str) -> Optional[models.PlatformInvitation]:
    if not _tables_available(db):
        return None
    normalized = normalize_invitation_email(email)
    if not normalized:
        return None
    return db.query(models.PlatformInvitation).filter(models.PlatformInvitation.email == normalized).first()


def get_invitation_by_token(db: Session, token: str) -> Optional[models.PlatformInvitation]:
    if not _tables_available(db):
        return None
    token_hash = hash_invitation_token(token)
    return db.query(models.PlatformInvitation).filter(models.PlatformInvitation.token_hash == token_hash).first()


def active_invitation_for_email(db: Session, email: str) -> Optional[models.PlatformInvitation]:
    invitation = get_invitation_by_email(db, email)
    if not invitation or invitation.status != "pending":
        return None
    if invitation.expires_at <= utcnow_naive():
        return None
    return invitation


def email_has_invitation_access(db: Session, email: str) -> bool:
    invitation = get_invitation_by_email(db, email)
    if not invitation:
        return False
    if invitation.status == "accepted":
        return True
    return bool(invitation.status == "pending" and invitation.expires_at > utcnow_naive())


def _normalized_premium(premium_tier: str, premium_days: Optional[int]) -> tuple[str, Optional[int]]:
    tier = (premium_tier or "free").strip().lower()
    if tier not in PREMIUM_TIERS:
        raise ValueError("Tier premium invalid.")
    if tier == "free":
        return "free", None
    days = int(premium_days or DEFAULT_PREMIUM_DAYS)
    if days < 1 or days > 3650:
        raise ValueError("Valabilitatea premium trebuie să fie între 1 și 3650 de zile.")
    return tier, days


def _new_credentials() -> tuple[str, str, str, str]:
    token = generate_invitation_token()
    temporary_password = local_auth.generate_temporary_password()
    return token, hash_invitation_token(token), temporary_password, local_auth.password_hash(temporary_password)


def upsert_invitation(
    db: Session,
    *,
    email: str,
    premium_tier: str,
    premium_days: Optional[int],
    note: Optional[str] = None,
    actor: Optional[models.User] = None,
    invitation_days: int = DEFAULT_INVITATION_DAYS,
) -> tuple[models.PlatformInvitation, str, str, str]:
    if not _tables_available(db):
        raise RuntimeError("Platform invitation table is missing.")
    normalized = normalize_invitation_email(email)
    if not normalized:
        raise ValueError("Emailul este obligatoriu.")
    tier, days = _normalized_premium(premium_tier, premium_days)
    token, token_hash, temporary_password, temporary_password_hash = _new_credentials()
    now = utcnow_naive()
    expires_at = now + timedelta(days=max(1, int(invitation_days or DEFAULT_INVITATION_DAYS)))
    invitation = get_invitation_by_email(db, normalized)
    action = "created"
    if invitation and invitation.status == "accepted":
        raise ValueError("Invitația a fost deja acceptată.")
    if invitation:
        action = "updated"
        invitation.token_hash = token_hash
        invitation.temporary_password_hash = temporary_password_hash
        invitation.status = "pending"
        invitation.premium_tier = tier
        invitation.premium_days = days
        invitation.note = (note or "").strip() or None
        invitation.created_by = actor.id if actor else invitation.created_by
        invitation.expires_at = expires_at
        invitation.revoked_at = None
        invitation.resent_at = now
    else:
        invitation = models.PlatformInvitation(
            email=normalized,
            token_hash=token_hash,
            temporary_password_hash=temporary_password_hash,
            status="pending",
            premium_tier=tier,
            premium_days=days,
            note=(note or "").strip() or None,
            created_by=actor.id if actor else None,
            expires_at=expires_at,
        )
        db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation, token, temporary_password, action


def rotate_invitation(db: Session, invitation: models.PlatformInvitation) -> tuple[models.PlatformInvitation, str, str]:
    if invitation.status == "accepted":
        raise ValueError("Invitația a fost deja acceptată.")
    token, token_hash, temporary_password, temporary_password_hash = _new_credentials()
    invitation.token_hash = token_hash
    invitation.temporary_password_hash = temporary_password_hash
    invitation.status = "pending"
    invitation.revoked_at = None
    invitation.resent_at = utcnow_naive()
    invitation.expires_at = utcnow_naive() + timedelta(days=DEFAULT_INVITATION_DAYS)
    db.commit()
    db.refresh(invitation)
    return invitation, token, temporary_password


def revoke_invitation(db: Session, invitation: models.PlatformInvitation) -> models.PlatformInvitation:
    if invitation.status == "accepted":
        raise ValueError("Invitația a fost deja acceptată și nu poate fi revocată.")
    invitation.status = "revoked"
    invitation.revoked_at = utcnow_naive()
    db.commit()
    db.refresh(invitation)
    return invitation


def verify_invitation_password(db: Session, *, token: str, email: str, password: str) -> models.PlatformInvitation:
    invitation = get_invitation_by_token(db, token)
    normalized = normalize_invitation_email(email)
    if (
        not invitation
        or invitation.email != normalized
        or invitation.status != "pending"
        or invitation.expires_at <= utcnow_naive()
        or not local_auth.verify_password(password, invitation.temporary_password_hash)
    ):
        raise ValueError("Invitația sau parola temporară nu sunt valide.")
    return invitation


def apply_invitation_to_user(db: Session, invitation: models.PlatformInvitation, user: models.User) -> None:
    now = utcnow_naive()
    invitation.status = "accepted"
    invitation.accepted_user_id = user.id
    invitation.accepted_at = now
    if invitation.premium_tier != "free":
        user.premium_tier = invitation.premium_tier
        user.premium_period_start = now
        user.premium_until = now + timedelta(days=max(1, int(invitation.premium_days or DEFAULT_PREMIUM_DAYS)))
        user.stripe_subscription_id = None
    db.add(invitation)
    db.add(user)
    db.commit()


def apply_invitation_for_email(db: Session, *, email: str, user: models.User) -> Optional[models.PlatformInvitation]:
    invitation = active_invitation_for_email(db, email)
    if not invitation:
        return None
    apply_invitation_to_user(db, invitation, user)
    db.refresh(invitation)
    db.refresh(user)
    return invitation
