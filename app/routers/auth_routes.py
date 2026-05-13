import re
import logging
import os
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import crud, email_service, facebook_oauth, google_oauth, local_auth, models, platform_access, schemas
from ..auth import get_db_epoch
from ..database import get_db
from ..utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX, default_cover_seed
from ..week_util import utcnow_naive

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["auth"])
AUTH_RETURN_TO_SESSION_KEY = "auth_return_to"


def _frontend_base_url(request: Request) -> str:
    configured_callback = os.getenv("GOOGLE_REDIRECT_URI", "")
    parsed_callback = urlparse(configured_callback)
    scheme = parsed_callback.scheme or request.url.scheme
    return f"{scheme}://{MAIN_DOMAIN}"


def _user_blog_url(request: Request, user) -> str:
    configured_callback = os.getenv("GOOGLE_REDIRECT_URI", "")
    parsed_callback = urlparse(configured_callback)
    scheme = parsed_callback.scheme or request.url.scheme
    suffix = SUBDOMAIN_SUFFIX if SUBDOMAIN_SUFFIX.startswith(".") else f".{SUBDOMAIN_SUFFIX}"
    return f"{scheme}://{user.username}{suffix}"


def _auth_failure_url(request: Request, provider: str = "auth") -> str:
    return f"{_frontend_base_url(request)}/?auth_error={provider}"


def _safe_return_url(request: Request, return_to: str | None) -> str | None:
    if not return_to:
        return None
    target = str(return_to).strip()
    if not target or len(target) > 2048 or any(ord(char) < 32 for char in target):
        return None
    if target.startswith("/") and not target.startswith("//"):
        return f"{_frontend_base_url(request)}{target}"

    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    netloc = parsed.netloc.lower()
    main_domain = MAIN_DOMAIN.lower()
    suffix = SUBDOMAIN_SUFFIX.lower()
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"
    frontend_netloc = urlparse(_frontend_base_url(request)).netloc.lower()
    if netloc == main_domain or netloc == frontend_netloc:
        return target
    if suffix and netloc.endswith(suffix):
        return target
    return None


def _store_auth_return_to(request: Request, return_to: str | None) -> str | None:
    redirect_url = _safe_return_url(request, return_to)
    if redirect_url:
        request.session[AUTH_RETURN_TO_SESSION_KEY] = redirect_url
    return redirect_url


def _session_auth_return_to(request: Request) -> str | None:
    return _safe_return_url(request, request.session.get(AUTH_RETURN_TO_SESSION_KEY))


def _login_user(request: Request, db: Session, user: models.User) -> None:
    user.last_login_at = utcnow_naive()
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["db_epoch"] = get_db_epoch()


def _pending_provider_payload(provider_user) -> dict:
    if hasattr(provider_user, "model_dump"):
        return provider_user.model_dump()
    return {
        "google_id": getattr(provider_user, "google_id", None),
        "facebook_id": getattr(provider_user, "facebook_id", None),
        "email": getattr(provider_user, "email", None),
        "name": getattr(provider_user, "name", ""),
        "picture": getattr(provider_user, "picture", None),
        "email_verified": bool(getattr(provider_user, "email_verified", True)),
    }


def _store_pending_auth(request: Request, source: str, payload: dict) -> None:
    return_to = request.session.get(AUTH_RETURN_TO_SESSION_KEY)
    request.session.clear()
    if return_to:
        request.session[AUTH_RETURN_TO_SESSION_KEY] = return_to
    request.session["pending_auth"] = {"source": source, **payload}


def _pending_auth_from_session(request: Request) -> dict:
    pending_auth = request.session.get("pending_auth")
    if pending_auth:
        return pending_auth
    google_user_data = request.session.get("google_user")
    if google_user_data:
        return {"source": "google", "provider_user": google_user_data}
    return {}


def _auth_response_payload(request: Request, user: models.User, redirect_url: str | None = None) -> dict:
    return {
        "message": "Autentificare reușită",
        "username": user.username,
        "redirect_url": redirect_url or _user_blog_url(request, user),
    }


def _queue_activation_code(db: Session, *, email: str, password_hash: str) -> None:
    _, code = local_auth.create_email_code(
        db,
        email=email,
        purpose=local_auth.PURPOSE_SIGNUP_ACTIVATION,
        payload={"password_hash": password_hash},
    )
    outbox_row = email_service.queue_auth_code_email(
        db,
        recipient_email=email,
        code=code,
        purpose=local_auth.PURPOSE_SIGNUP_ACTIVATION,
    )
    email_service.send_queued_email_now(
        db,
        outbox_row,
        worker=f"auth:{local_auth.PURPOSE_SIGNUP_ACTIVATION}",
    )


def _auth_code_error_response(error: local_auth.AuthCodeError) -> HTTPException:
    messages = {
        "invalid_code": "Codul nu este valid.",
        "expired_code": "Codul a expirat. Cere un cod nou.",
        "too_many_attempts": "Ai încercat codul de prea multe ori. Cere un cod nou.",
    }
    return HTTPException(status_code=400, detail=messages.get(error.reason, "Codul nu este valid."))


def _access_denied_response() -> HTTPException:
    return HTTPException(status_code=403, detail=platform_access.ACCESS_DENIED_MESSAGE)


def _require_platform_access(db: Session, email: str, user: models.User | None = None) -> None:
    if not platform_access.can_access_platform(db, email=email, user=user):
        raise _access_denied_response()


def _existing_google_user_for_access(db: Session, google_user: schemas.GoogleUserInfo) -> models.User | None:
    google_id = getattr(google_user, "google_id", None)
    if google_id:
        user = crud.get_user_by_google_id(db, google_id)
        if user:
            return user
    if bool(getattr(google_user, "email_verified", True)):
        return crud.get_user_by_email(db, google_user.email)
    return None


def _existing_facebook_user_for_access(db: Session, facebook_user: schemas.FacebookUserInfo) -> models.User | None:
    facebook_id = getattr(facebook_user, "facebook_id", None)
    if facebook_id:
        user = crud.get_user_by_facebook_id(db, facebook_id)
        if user:
            return user
    if facebook_user.email_verified:
        return crud.get_user_by_email(db, facebook_user.email)
    return None


def _react_index_response() -> FileResponse:
    frontend_index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist", "index.html")
    response = FileResponse(frontend_index)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/autentificare/google")
@limiter.limit("5/minute")
async def google_login(request: Request, return_to: str | None = None):
    """Initiate Google OAuth flow"""
    try:
        _store_auth_return_to(request, return_to)
        auth_url = google_oauth.get_google_auth_url(request)
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error(f"Eroare la inițierea autentificării Google: {e}")
        return RedirectResponse(url=_auth_failure_url(request, "google"), status_code=status.HTTP_302_FOUND)


@router.get("/autentificare/facebook")
@limiter.limit("5/minute")
async def facebook_login(request: Request, return_to: str | None = None):
    """Initiate Facebook OAuth flow"""
    try:
        _store_auth_return_to(request, return_to)
        auth_url = facebook_oauth.get_facebook_auth_url(request)
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error(f"Eroare la inițierea autentificării Facebook: {e}")
        return RedirectResponse(url=_auth_failure_url(request, "facebook"), status_code=status.HTTP_302_FOUND)


@router.get("/auth/google/callback", include_in_schema=False)
@router.get("/autentificare/google/raspuns")
@limiter.limit("5/minute")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        # Get user info from Google
        google_user = await google_oauth.handle_google_callback(request)
        existing_user = _existing_google_user_for_access(db, google_user)
        if not platform_access.can_access_platform(db, email=google_user.email, user=existing_user):
            logger.warning("Google OAuth blocked by invite-only access gate for email: %s", google_user.email)
            return RedirectResponse(url=_auth_failure_url(request, "access"), status_code=status.HTTP_302_FOUND)

        # Check if user exists. Test and fallback paths may provide only an
        # email-bearing provider object; in that case the access lookup already
        # identified the existing account, and the provider-specific linker
        # cannot run without a provider id.
        if existing_user and not getattr(google_user, "google_id", None):
            user, is_new = existing_user, False
        else:
            user, is_new = google_oauth.find_or_create_user(db, google_user)

        if user:
            # Existing user - log them in (clear session first to prevent fixation)
            redirect_url = _session_auth_return_to(request) or _user_blog_url(request, user)
            _login_user(request, db, user)
            logger.info(f"Google OAuth login successful for existing user: {user.username}")
            return RedirectResponse(
                url=redirect_url,
                status_code=status.HTTP_302_FOUND
            )
        else:
            # New user - store Google info in session and redirect to setup
            google_payload = {
                "google_id": google_user.google_id,
                "email": google_user.email.lower(),
                "name": google_user.name,
                "picture": google_user.picture,
                "email_verified": bool(getattr(google_user, "email_verified", True)),
            }
            _store_pending_auth(request, "google", {"provider_user": google_payload})
            request.session["google_user"] = google_payload
            logger.info(f"New Google user detected: {google_user.email}. Redirecting to setup.")
            return RedirectResponse(
                url=f"{_frontend_base_url(request)}/autentificare/configurare",
                status_code=status.HTTP_302_FOUND
            )

    except HTTPException as exc:
        logger.warning(f"Autentificarea Google a eșuat: {exc.detail}")
        return RedirectResponse(url=_auth_failure_url(request, "google"), status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error(f"Eroare în răspunsul Google: {e}")
        return RedirectResponse(url=_auth_failure_url(request, "google"), status_code=status.HTTP_302_FOUND)


@router.get("/auth/facebook/callback", include_in_schema=False)
@router.get("/autentificare/facebook/raspuns")
@limiter.limit("5/minute")
async def facebook_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Facebook OAuth callback"""
    try:
        facebook_user = await facebook_oauth.handle_facebook_callback(request)
        existing_user = _existing_facebook_user_for_access(db, facebook_user)
        if not platform_access.can_access_platform(db, email=facebook_user.email, user=existing_user):
            logger.warning("Facebook OAuth blocked by invite-only access gate for email: %s", facebook_user.email)
            return RedirectResponse(url=_auth_failure_url(request, "access"), status_code=status.HTTP_302_FOUND)
        if existing_user and not getattr(facebook_user, "facebook_id", None):
            user, is_new = existing_user, False
        else:
            user, is_new = facebook_oauth.find_or_create_user(db, facebook_user)
        if user:
            redirect_url = _session_auth_return_to(request) or _user_blog_url(request, user)
            _login_user(request, db, user)
            logger.info("Facebook OAuth login successful for existing user: %s", user.username)
            return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
        _store_pending_auth(
            request,
            "facebook",
            {"provider_user": _pending_provider_payload(facebook_user)},
        )
        logger.info("New Facebook user detected: %s. Redirecting to setup.", facebook_user.email)
        return RedirectResponse(
            url=f"{_frontend_base_url(request)}/autentificare/configurare",
            status_code=status.HTTP_302_FOUND,
        )
    except HTTPException as exc:
        logger.warning("Autentificarea Facebook a eșuat: %s", exc.detail)
        return RedirectResponse(url=_auth_failure_url(request, "facebook"), status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error("Eroare în răspunsul Facebook: %s", e)
        return RedirectResponse(url=_auth_failure_url(request, "facebook"), status_code=status.HTTP_302_FOUND)


@router.post("/api/autentificare/parola/inregistrare")
@limiter.limit("5/minute")
def register_with_password(
    request: Request,
    data: schemas.PasswordRegisterRequest,
    db: Session = Depends(get_db),
):
    email = local_auth.normalize_email(str(data.email))
    if crud.get_user_by_email(db, email):
        raise HTTPException(
            status_code=400,
            detail="Există deja un cont cu această adresă. Folosește resetarea parolei ca să setezi o parolă.",
        )
    _require_platform_access(db, email)
    try:
        hashed_password = local_auth.password_hash(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _queue_activation_code(db, email=email, password_hash=hashed_password)
    return {
        "message": "Ți-am trimis un cod de activare pe email.",
        "email": email,
        "next": "activation_code",
    }


@router.post("/api/autentificare/parola/activeaza")
@limiter.limit("8/minute")
def activate_password_signup(
    request: Request,
    data: schemas.AuthCodeVerifyRequest,
    db: Session = Depends(get_db),
):
    email = local_auth.normalize_email(str(data.email))
    if crud.get_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Există deja un cont cu această adresă.")
    _require_platform_access(db, email)
    try:
        code_row = local_auth.verify_email_code(
            db,
            email=email,
            purpose=local_auth.PURPOSE_SIGNUP_ACTIVATION,
            code=data.code,
        )
    except local_auth.AuthCodeError as exc:
        raise _auth_code_error_response(exc)
    password_hash = (code_row.payload or {}).get("password_hash")
    if not password_hash:
        raise HTTPException(status_code=400, detail="Codul nu mai poate fi folosit. Reia înregistrarea.")
    _store_pending_auth(
        request,
        "password",
        {"email": email, "password_hash": password_hash},
    )
    return {
        "message": "Email verificat. Continuă configurarea contului.",
        "setup_url": f"{_frontend_base_url(request)}/autentificare/configurare",
    }


@router.post("/api/autentificare/parola/retrimite-cod")
@limiter.limit("4/minute")
def resend_activation_code(
    request: Request,
    data: schemas.PasswordResetRequest,
    db: Session = Depends(get_db),
):
    email = local_auth.normalize_email(str(data.email))
    if crud.get_user_by_email(db, email):
        raise HTTPException(status_code=400, detail="Există deja un cont cu această adresă.")
    _require_platform_access(db, email)
    active_code = local_auth.latest_active_email_code(
        db,
        email=email,
        purpose=local_auth.PURPOSE_SIGNUP_ACTIVATION,
    )
    password_hash = (active_code.payload or {}).get("password_hash") if active_code else None
    if not password_hash:
        raise HTTPException(status_code=400, detail="Reia înregistrarea ca să primești un cod nou.")
    _queue_activation_code(db, email=email, password_hash=password_hash)
    return {"message": "Ți-am trimis un cod nou pe email.", "email": email}


@router.post("/api/autentificare/parola/login")
@limiter.limit("10/minute")
def login_with_password(
    request: Request,
    data: schemas.PasswordLoginRequest,
    db: Session = Depends(get_db),
):
    email = local_auth.normalize_email(str(data.email))
    user = crud.get_user_by_email(db, email)
    if not user or not local_auth.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Email sau parolă incorecte.")
    if not user.email_verified_at:
        raise HTTPException(status_code=403, detail="Adresa de email nu este verificată.")
    _require_platform_access(db, email, user)
    redirect_url = _safe_return_url(request, data.return_to) or _user_blog_url(request, user)
    _login_user(request, db, user)
    logger.info("Password login successful for user: %s", user.username)
    return _auth_response_payload(request, user, redirect_url=redirect_url)


@router.post("/api/autentificare/parola/resetare")
@limiter.limit("5/minute")
def request_password_reset(
    request: Request,
    data: schemas.PasswordResetRequest,
    db: Session = Depends(get_db),
):
    email = local_auth.normalize_email(str(data.email))
    user = crud.get_user_by_email(db, email)
    if user and platform_access.can_access_platform(db, email=email, user=user):
        _, code = local_auth.create_email_code(
            db,
            email=email,
            purpose=local_auth.PURPOSE_PASSWORD_RESET,
            user_id=user.id,
        )
        outbox_row = email_service.queue_auth_code_email(
            db,
            recipient_user_id=user.id,
            recipient_email=user.email,
            recipient_name=user.username,
            code=code,
            purpose=local_auth.PURPOSE_PASSWORD_RESET,
        )
        email_service.send_queued_email_now(
            db,
            outbox_row,
            worker=f"auth:{local_auth.PURPOSE_PASSWORD_RESET}",
        )
    return {
        "message": "Dacă adresa există, vei primi un cod de resetare.",
        "email": email,
        "next": "reset_code",
    }


@router.post("/api/autentificare/parola/resetare/confirma")
@limiter.limit("8/minute")
def confirm_password_reset(
    request: Request,
    data: schemas.PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
):
    email = local_auth.normalize_email(str(data.email))
    user = crud.get_user_by_email(db, email)
    if user:
        _require_platform_access(db, email, user)
    try:
        code_row = local_auth.verify_email_code(
            db,
            email=email,
            purpose=local_auth.PURPOSE_PASSWORD_RESET,
            code=data.code,
        )
    except local_auth.AuthCodeError as exc:
        raise _auth_code_error_response(exc)
    user = code_row.user or user
    if not user:
        raise HTTPException(status_code=400, detail="Codul nu este valid.")
    try:
        user.password_hash = local_auth.password_hash(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    now = utcnow_naive()
    user.password_updated_at = now
    if not user.email_verified_at:
        user.email_verified_at = now
    _login_user(request, db, user)
    return _auth_response_payload(request, user)


@router.get("/autentificare/configurare")
def auth_setup_page(request: Request):
    """Setup page for new authenticated users — served by React frontend"""
    pending_auth = _pending_auth_from_session(request)
    if not pending_auth:
        return RedirectResponse(url=f"{_frontend_base_url(request)}/?auth_modal=1", status_code=status.HTTP_302_FOUND)
    return _react_index_response()


@router.post("/api/autentificare/finalizeaza-configurarea")
def complete_user_setup(request: Request, setup_data: schemas.UserSetup, db: Session = Depends(get_db)):
    """Complete user setup after OAuth or password email activation"""
    pending_auth = _pending_auth_from_session(request)
    if not pending_auth:
        raise HTTPException(status_code=400, detail="Nu există o sesiune de autentificare")

    try:
        # Validate username
        if not re.fullmatch(r"^[a-zA-Z0-9]+$", setup_data.username):
            raise HTTPException(status_code=400, detail="Numele de utilizator poate conține doar litere și cifre, fără spații sau simboluri speciale.")

        source = pending_auth.get("source")
        provider_user_data = pending_auth.get("provider_user") or {}
        pending_email = ""
        if source == "google":
            pending_email = str(provider_user_data.get("email") or "")
        elif source == "facebook":
            pending_email = str(provider_user_data.get("email") or "")
        elif source == "password":
            pending_email = str(pending_auth.get("email") or "")
        if pending_email:
            _require_platform_access(db, pending_email)
        if source == "google":
            google_user = schemas.GoogleUserInfo(**provider_user_data)
            new_user = google_oauth.create_user_from_google(db, google_user, setup_data)
            if google_user.email_verified and not new_user.email_verified_at:
                new_user.email_verified_at = utcnow_naive()
        elif source == "facebook":
            facebook_user = schemas.FacebookUserInfo(**provider_user_data)
            new_user = facebook_oauth.create_user_from_facebook(db, facebook_user, setup_data)
        elif source == "password":
            email = local_auth.normalize_email(str(pending_auth.get("email") or ""))
            password_hash = pending_auth.get("password_hash")
            if not email or not password_hash:
                raise HTTPException(status_code=400, detail="Sesiunea de activare nu este validă")
            if crud.get_user_by_email(db, email):
                raise HTTPException(status_code=400, detail="Există deja un cont cu această adresă")
            existing_user = crud.get_user_by_username(db, setup_data.username.lower())
            if existing_user:
                raise HTTPException(status_code=400, detail="Numele de utilizator este deja folosit")
            new_user = crud.create_user_from_google(
                db,
                {
                    "username": setup_data.username.lower(),
                    "email": email,
                    "password_hash": password_hash,
                    "email_verified_at": utcnow_naive(),
                    "password_updated_at": utcnow_naive(),
                    "subtitle": setup_data.subtitle,
                    "avatar_seed": setup_data.avatar_seed,
                    "cover_seed": setup_data.cover_seed or default_cover_seed(setup_data.username.lower()),
                },
            )
        else:
            raise HTTPException(status_code=400, detail="Sesiunea de autentificare nu este validă")
        new_user.last_login_at = utcnow_naive()
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        redirect_url = _session_auth_return_to(request) or _user_blog_url(request, new_user)
        request.session.clear()
        request.session["user_id"] = new_user.id
        request.session["db_epoch"] = get_db_epoch()

        logger.info(f"User setup completed for: {new_user.username}")
        return {"message": "Configurarea a fost finalizată", "username": new_user.username, "redirect_url": redirect_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la finalizarea configurării utilizatorului: {e}")
        raise HTTPException(status_code=500, detail="Nu am putut finaliza configurarea")


@router.get("/api/deconectare")
def logout_user(request: Request):
    request.session.clear()  # Clear session
    logger.info("Utilizator deconectat. Sesiune stearsa.")

    # Return JSON for React SPA, or redirect for direct browser access
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"success": True}
    return RedirectResponse(url=f"//{MAIN_DOMAIN}", status_code=status.HTTP_302_FOUND)
