import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from app import local_auth, models, platform_access, schemas
from app.routers import admin_routes, auth_routes
from app.week_util import utcnow_naive


class DummyRequest:
    def __init__(self, session=None, scheme="http", headers=None):
        self.session = session or {}
        self.url = SimpleNamespace(scheme=scheme)
        self.headers = headers or {}
        self.cookies = {}
        self.client = SimpleNamespace(host="127.0.0.1")


class PlatformAccessTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def make_user(self, username: str, **kwargs) -> models.User:
        password = kwargs.pop("password", "long-enough-password")
        user = models.User(
            username=username,
            email=f"{username}@example.com",
            password_hash=local_auth.password_hash(password),
            email_verified_at=utcnow_naive(),
            **kwargs,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def close_platform(self) -> None:
        platform_access.set_platform_open(self.db, is_open=False)

    def login(self, email: str, password: str = "long-enough-password"):
        return auth_routes.login_with_password.__wrapped__(
            DummyRequest({}),
            schemas.PasswordLoginRequest(email=email, password=password),
            self.db,
        )

    def async_run(self, value):
        return asyncio.run(value)

    def test_missing_setting_defaults_to_closed_for_password_login(self):
        user = self.make_user("openuser")

        with self.assertRaises(HTTPException) as login_error:
            self.login(user.email)
        self.assertEqual(login_error.exception.status_code, 403)

        platform_access.add_allowed_email(self.db, email=user.email)
        response = self.login(user.email)
        self.assertEqual(response["username"], user.username)

    def test_closed_platform_blocks_password_login_and_registration(self):
        user = self.make_user("closeduser")
        self.close_platform()

        with self.assertRaises(HTTPException) as login_error:
            self.login(user.email)
        self.assertEqual(login_error.exception.status_code, 403)

        with self.assertRaises(HTTPException) as register_error:
            auth_routes.register_with_password.__wrapped__(
                DummyRequest({}),
                schemas.PasswordRegisterRequest(email="newclosed@example.com", password="long-enough-password"),
                self.db,
            )
        self.assertEqual(register_error.exception.status_code, 403)
        self.assertEqual(self.db.query(models.EmailOutbox).count(), 0)

    def test_closed_platform_allows_case_insensitive_allowlisted_login(self):
        user = self.make_user("alloweduser")
        self.close_platform()
        platform_access.add_allowed_email(self.db, email="ALLOWEDUSER@example.com")

        response = self.login("AllowedUser@Example.com")

        self.assertEqual(response["username"], user.username)

    def test_closed_platform_requires_admin_email_in_allowlist(self):
        admin_user = self.make_user("adminuser", is_admin=True)
        self.close_platform()

        with self.assertRaises(HTTPException) as login_error:
            self.login(admin_user.email)
        self.assertEqual(login_error.exception.status_code, 403)

        platform_access.add_allowed_email(self.db, email=admin_user.email)
        response = self.login(admin_user.email)

        self.assertEqual(response["username"], admin_user.username)

    def test_closed_platform_blocks_activation_and_reset_confirm(self):
        user = self.make_user("resetblocked")
        original_hash = user.password_hash
        _, reset_code = local_auth.create_email_code(
            self.db,
            email=user.email,
            purpose=local_auth.PURPOSE_PASSWORD_RESET,
            user_id=user.id,
        )
        _, activation_code = local_auth.create_email_code(
            self.db,
            email="signupblocked@example.com",
            purpose=local_auth.PURPOSE_SIGNUP_ACTIVATION,
            payload={"password_hash": local_auth.password_hash("long-enough-password")},
        )
        self.close_platform()

        with self.assertRaises(HTTPException) as activation_error:
            auth_routes.activate_password_signup.__wrapped__(
                DummyRequest({}),
                schemas.AuthCodeVerifyRequest(email="signupblocked@example.com", code=activation_code),
                self.db,
            )
        self.assertEqual(activation_error.exception.status_code, 403)

        with self.assertRaises(HTTPException) as reset_error:
            auth_routes.confirm_password_reset.__wrapped__(
                DummyRequest({}),
                schemas.PasswordResetConfirmRequest(
                    email=user.email,
                    code=reset_code,
                    password="new-long-password",
                ),
                self.db,
            )
        self.assertEqual(reset_error.exception.status_code, 403)
        self.db.refresh(user)
        self.assertEqual(user.password_hash, original_hash)

    def test_closed_platform_blocks_google_oauth_with_access_error(self):
        self.close_platform()
        google_user = schemas.GoogleUserInfo(
            google_id="google-blocked",
            email="blocked@example.com",
            name="Blocked",
            email_verified=True,
        )

        with patch.object(auth_routes.google_oauth, "handle_google_callback", new=AsyncMock(return_value=google_user)):
            response = self.async_run(auth_routes.google_callback.__wrapped__(DummyRequest({}), self.db))

        self.assertIn("auth_error=access", response.headers["location"])
        self.assertIsNone(self.db.query(models.User).filter(models.User.email == "blocked@example.com").first())

    def test_admin_platform_access_endpoints_manage_toggle_and_allowlist(self):
        admin_user = self.make_user("accessadmin", is_admin=True)
        initial = admin_routes.get_platform_access(db=self.db, current_user=admin_user)
        self.assertFalse(initial["open"])

        closed = admin_routes.update_platform_access(
            schemas.AdminPlatformAccessUpdate(open=False),
            request=None,
            db=self.db,
            current_user=admin_user,
        )
        self.assertFalse(closed["open"])

        added = admin_routes.add_platform_allowed_email(
            schemas.AdminPlatformAllowedEmailCreate(email="Invitee@Example.com", note="pilot"),
            request=None,
            db=self.db,
            current_user=admin_user,
        )
        self.assertEqual(added["allowed_count"], 1)
        self.assertEqual(added["emails"][0]["email"], "invitee@example.com")
        self.assertEqual(added["emails"][0]["note"], "pilot")

        fetched = admin_routes.get_platform_access(db=self.db, current_user=admin_user)
        self.assertFalse(fetched["open"])
        self.assertEqual(fetched["allowed_count"], 1)

        removed = admin_routes.delete_platform_allowed_email(
            added["emails"][0]["id"],
            request=None,
            db=self.db,
            current_user=admin_user,
        )
        self.assertEqual(removed["allowed_count"], 0)


if __name__ == "__main__":
    unittest.main()
