from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .week_util import utcnow_naive

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
except Exception:  # pragma: no cover - exercised only when optional dep is absent
    PasswordHasher = None
    VerifyMismatchError = Exception


PURPOSE_SIGNUP_ACTIVATION = "signup_activation"
PURPOSE_PASSWORD_RESET = "password_reset"
CODE_TTL_MINUTES = 15
CODE_MAX_ATTEMPTS = 5
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128
_PBKDF2_ITERATIONS = 260_000
_PBKDF2_PREFIX = "pbkdf2_sha256"
_CODE_PREFIX = "hmac_sha256"
_password_hasher = PasswordHasher() if PasswordHasher else None


class AuthCodeError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise ValueError("Parola este obligatorie.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Parola trebuie să aibă cel puțin {PASSWORD_MIN_LENGTH} caractere.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Parola poate avea cel mult {PASSWORD_MAX_LENGTH} caractere.")


def password_hash(password: str) -> str:
    validate_password(password)
    if _password_hasher:
        return _password_hasher.hash(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "$".join(
        [
            _PBKDF2_PREFIX,
            str(_PBKDF2_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    if not password or not stored_hash:
        return False
    if stored_hash.startswith("$argon2"):
        if not _password_hasher:
            return False
        try:
            return _password_hasher.verify(stored_hash, password)
        except VerifyMismatchError:
            return False
        except Exception:
            return False
    try:
        prefix, iterations, salt_text, digest_text = stored_hash.split("$", 3)
        if prefix != _PBKDF2_PREFIX:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _secret_key() -> bytes:
    secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("EMAIL_UNSUBSCRIBE_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET_KEY is required for authentication codes.")
    return secret.encode("utf-8")


def generate_email_code() -> str:
    return f"{secrets.randbelow(100_000_000):08d}"


def hash_email_code(code: str, salt: Optional[str] = None) -> str:
    normalized = "".join(ch for ch in str(code or "") if ch.isdigit())
    salt = salt or secrets.token_urlsafe(18)
    digest = hmac.new(_secret_key(), f"{salt}:{normalized}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{_CODE_PREFIX}${salt}${digest}"


def verify_email_code_hash(code: str, stored_hash: str) -> bool:
    try:
        prefix, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if prefix != _CODE_PREFIX:
        return False
    actual = hash_email_code(code, salt).split("$", 2)[2]
    return hmac.compare_digest(actual, expected)


def create_email_code(
    db: Session,
    *,
    email: str,
    purpose: str,
    user_id: Optional[int] = None,
    payload: Optional[dict] = None,
) -> tuple[models.AuthEmailCode, str]:
    normalized_email = normalize_email(email)
    now = utcnow_naive()
    (
        db.query(models.AuthEmailCode)
        .filter(
            models.AuthEmailCode.email == normalized_email,
            models.AuthEmailCode.purpose == purpose,
            models.AuthEmailCode.consumed_at.is_(None),
        )
        .update({"consumed_at": now}, synchronize_session=False)
    )
    code = generate_email_code()
    row = models.AuthEmailCode(
        user_id=user_id,
        email=normalized_email,
        purpose=purpose,
        code_hash=hash_email_code(code),
        payload=payload or {},
        attempts=0,
        max_attempts=CODE_MAX_ATTEMPTS,
        expires_at=now + timedelta(minutes=CODE_TTL_MINUTES),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, code


def latest_active_email_code(db: Session, *, email: str, purpose: str) -> Optional[models.AuthEmailCode]:
    return (
        db.query(models.AuthEmailCode)
        .filter(
            models.AuthEmailCode.email == normalize_email(email),
            models.AuthEmailCode.purpose == purpose,
            models.AuthEmailCode.consumed_at.is_(None),
        )
        .order_by(models.AuthEmailCode.created_at.desc(), models.AuthEmailCode.id.desc())
        .first()
    )


def verify_email_code(db: Session, *, email: str, purpose: str, code: str) -> models.AuthEmailCode:
    normalized_code = "".join(ch for ch in str(code or "") if ch.isdigit())
    if len(normalized_code) != 8:
        raise AuthCodeError("invalid_code")
    row = latest_active_email_code(db, email=email, purpose=purpose)
    if not row:
        raise AuthCodeError("invalid_code")
    now = utcnow_naive()
    if row.expires_at <= now:
        row.consumed_at = now
        db.commit()
        raise AuthCodeError("expired_code")
    if int(row.attempts or 0) >= int(row.max_attempts or CODE_MAX_ATTEMPTS):
        raise AuthCodeError("too_many_attempts")
    if not verify_email_code_hash(normalized_code, row.code_hash):
        row.attempts = int(row.attempts or 0) + 1
        db.add(row)
        db.commit()
        raise AuthCodeError("invalid_code")
    row.consumed_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
