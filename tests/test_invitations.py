import os
import re
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from app import crud, local_auth, models, platform_access, schemas
from app.routers import admin_routes, auth_routes, user_routes
from app.week_util import utcnow_naive


class DummyRequest:
    def __init__(self, session=None, scheme="http", headers=None):
        self.session = session or {}
        self.url = SimpleNamespace(scheme=scheme)
        self.headers = headers or {}
        self.cookies = {}
        self.client = SimpleNamespace(host="127.0.0.1")


class InvitationTests(unittest.TestCase):
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
        self.admin = self.make_user("admin", is_admin=True, is_moderator=True)
        platform_access.set_platform_open(self.db, is_open=False, actor=self.admin)

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

    def invite(self, email="invitee@example.com", tier="free", days=None):
        response = admin_routes.create_platform_invitations(
            schemas.AdminInvitationCreate(
                emails=[email],
                premium_tier=tier,
                premium_days=days,
                note="pilot",
            ),
            request=None,
            db=self.db,
            current_user=self.admin,
        )
        row = self.db.query(models.EmailOutbox).order_by(models.EmailOutbox.id.desc()).first()
        token = re.search(r"/invitatie/([^\s]+)", row.text_content).group(1)
        password = re.search(r"Parolă temporară: ([^\n]+)", row.text_content).group(1)
        invitation = self.db.query(models.PlatformInvitation).filter(models.PlatformInvitation.email == email).one()
        return response, invitation, token, password, row

    def test_admin_invitation_queues_email_without_plaintext_secret_on_invitation(self):
        response, invitation, token, password, row = self.invite("writer@example.com", tier="cronicar", days=45)

        self.assertEqual(response["created_count"], 1)
        self.assertEqual(invitation.email, "writer@example.com")
        self.assertEqual(invitation.premium_tier, "cronicar")
        self.assertEqual(invitation.premium_days, 45)
        self.assertNotIn(token, invitation.token_hash)
        self.assertNotIn(password, invitation.temporary_password_hash)
        self.assertIn("Parolă temporară:", row.text_content)
        self.assertIn("o poți schimba oricând", row.text_content)
        self.assertIn("Acceptă invitația:", row.text_content)
        self.assertIn("Dacă butonul nu se afișează corect", row.html_content)
        self.assertIn('role="presentation"', row.html_content)
        self.assertIn("word-break:break-all", row.html_content)

    def test_invited_password_signup_accepts_invitation_and_activates_premium(self):
        _response, invitation, token, password, _row = self.invite("premium@example.com", tier="rapsod", days=60)
        request = DummyRequest({})

        password_response = auth_routes.login_with_invitation_password.__wrapped__(
            request,
            schemas.InvitationPasswordLoginRequest(
                token=token,
                email="premium@example.com",
                password=password,
            ),
            self.db,
        )
        self.assertIn("/autentificare/configurare", password_response["setup_url"])

        setup_response = auth_routes.complete_user_setup(
            request,
            schemas.UserSetup(
                username="premiuminvitee",
                subtitle="<p>Bună.</p>",
                avatar_seed="premiuminvitee-shapes",
                cover_seed="premiuminvitee-cover-sky",
                accept_terms_and_privacy=True,
            ),
            self.db,
        )

        user = self.db.query(models.User).filter(models.User.email == "premium@example.com").one()
        self.db.refresh(invitation)
        self.assertEqual(setup_response["username"], "premiuminvitee")
        self.assertEqual(invitation.status, "accepted")
        self.assertEqual(invitation.accepted_user_id, user.id)
        self.assertEqual(user.premium_tier, "rapsod")
        self.assertTrue(user.is_premium)

        login_response = auth_routes.login_with_password.__wrapped__(
            DummyRequest({}),
            schemas.PasswordLoginRequest(email="premium@example.com", password=password),
            self.db,
        )
        self.assertEqual(login_response["username"], "premiuminvitee")

    def test_invitation_setup_redirects_to_blog_when_return_target_is_invitation(self):
        _response, _invitation, token, password, _row = self.invite("redirect@example.com")
        request = DummyRequest({auth_routes.AUTH_RETURN_TO_SESSION_KEY: "http://calimara.ro/invitatie/old-token"})

        auth_routes.login_with_invitation_password.__wrapped__(
            request,
            schemas.InvitationPasswordLoginRequest(
                token=token,
                email="redirect@example.com",
                password=password,
            ),
            self.db,
        )

        setup_response = auth_routes.complete_user_setup(
            request,
            schemas.UserSetup(
                username="redirectinvitee",
                subtitle="",
                avatar_seed="calimara-avatar-shapes",
                cover_seed="calimara-cover-sky",
                accept_terms_and_privacy=True,
            ),
            self.db,
        )

        self.assertEqual(setup_response["redirect_url"], "https://redirectinvitee.calimara.ro")

    def test_invitation_setup_preserves_valid_content_return_target(self):
        _response, _invitation, token, password, _row = self.invite("return@example.com")
        request = DummyRequest({auth_routes.AUTH_RETURN_TO_SESSION_KEY: "http://calimara.ro/?post=42"})

        auth_routes.login_with_invitation_password.__wrapped__(
            request,
            schemas.InvitationPasswordLoginRequest(
                token=token,
                email="return@example.com",
                password=password,
            ),
            self.db,
        )

        setup_response = auth_routes.complete_user_setup(
            request,
            schemas.UserSetup(
                username="returninvitee",
                subtitle="",
                avatar_seed="calimara-avatar-ink",
                cover_seed="calimara-cover-forest",
                accept_terms_and_privacy=True,
            ),
            self.db,
        )

        self.assertEqual(setup_response["redirect_url"], "http://calimara.ro/?post=42")

    def test_password_signup_can_use_referral_code_while_platform_is_closed(self):
        referrer = self.make_user("referrer")
        referral_code = crud.ensure_referral_code(self.db, referrer)

        with self.assertRaises(HTTPException) as invalid_error:
            auth_routes.register_with_password.__wrapped__(
                DummyRequest({}),
                schemas.PasswordRegisterRequest(
                    email="blocked@example.com",
                    password="long-enough-password",
                    referral_code="bad-code",
                ),
                self.db,
            )
        self.assertEqual(invalid_error.exception.status_code, 403)

        request = DummyRequest({})
        response = auth_routes.register_with_password.__wrapped__(
            request,
            schemas.PasswordRegisterRequest(
                email="referred@example.com",
                password="long-enough-password",
                referral_code=referral_code,
            ),
            self.db,
        )
        self.assertEqual(response["next"], "activation_code")

        row = self.db.query(models.EmailOutbox).order_by(models.EmailOutbox.id.desc()).first()
        code = re.search(r"\n\n(\d{8})\n\n", row.text_content).group(1)
        auth_routes.activate_password_signup.__wrapped__(
            request,
            schemas.AuthCodeVerifyRequest(email="referred@example.com", code=code),
            self.db,
        )
        auth_routes.complete_user_setup(
            request,
            schemas.UserSetup(
                username="referredwriter",
                subtitle="",
                avatar_seed="referredwriter-shapes",
                cover_seed="referredwriter-cover-sky",
                accept_terms_and_privacy=True,
            ),
            self.db,
        )

        referred = self.db.query(models.User).filter(models.User.email == "referred@example.com").one()
        self.assertEqual(referred.referred_by_user_id, referrer.id)

    def test_revoked_invitation_cannot_be_used(self):
        _response, invitation, token, password, _row = self.invite("revoked@example.com")
        admin_routes.revoke_platform_invitation(invitation.id, request=None, db=self.db, current_user=self.admin)

        with self.assertRaises(HTTPException) as error:
            auth_routes.login_with_invitation_password.__wrapped__(
                DummyRequest({}),
                schemas.InvitationPasswordLoginRequest(token=token, email="revoked@example.com", password=password),
                self.db,
            )

        self.assertEqual(error.exception.status_code, 400)

    def test_existing_user_email_is_skipped(self):
        self.make_user("existing")

        response = admin_routes.create_platform_invitations(
            schemas.AdminInvitationCreate(emails=["existing@example.com"], premium_tier="free"),
            request=None,
            db=self.db,
            current_user=self.admin,
        )

        self.assertEqual(response["created_count"], 0)
        self.assertEqual(response["skipped_count"], 1)
        self.assertEqual(self.db.query(models.PlatformInvitation).count(), 0)

    def test_logged_in_user_can_change_invitation_password_optionally(self):
        _response, _invitation, token, password, _row = self.invite("change@example.com")
        request = DummyRequest({})
        auth_routes.login_with_invitation_password.__wrapped__(
            request,
            schemas.InvitationPasswordLoginRequest(token=token, email="change@example.com", password=password),
            self.db,
        )
        auth_routes.complete_user_setup(
            request,
            schemas.UserSetup(
                username="changepass",
                subtitle="",
                avatar_seed="changepass-shapes",
                cover_seed="changepass-cover-sky",
                accept_terms_and_privacy=True,
            ),
            self.db,
        )
        user = self.db.query(models.User).filter(models.User.email == "change@example.com").one()

        response = user_routes.update_current_user_password(
            schemas.PasswordChangeRequest(current_password=password, new_password="new-long-password"),
            db=self.db,
            current_user=user,
        )

        self.assertEqual(response["message"], "Parola a fost actualizată.")
        self.db.refresh(user)
        self.assertFalse(local_auth.verify_password(password, user.password_hash))
        self.assertTrue(local_auth.verify_password("new-long-password", user.password_hash))


if __name__ == "__main__":
    unittest.main()
