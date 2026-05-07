import re
import logging
import os
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import schemas, google_oauth
from ..auth import get_db_epoch
from ..database import get_db
from ..utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX
from ..week_util import utcnow_naive

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["auth"])


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


def _auth_failure_url(request: Request) -> str:
    return f"{_frontend_base_url(request)}/?auth_error=google"


def _react_index_response() -> FileResponse:
    frontend_index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist", "index.html")
    response = FileResponse(frontend_index)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get("/autentificare/google")
@limiter.limit("5/minute")
async def google_login(request: Request):
    """Initiate Google OAuth flow"""
    try:
        auth_url = google_oauth.get_google_auth_url(request)
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error(f"Eroare la inițierea autentificării Google: {e}")
        return RedirectResponse(url=_auth_failure_url(request), status_code=status.HTTP_302_FOUND)


@router.get("/auth/google/callback", include_in_schema=False)
@router.get("/autentificare/google/raspuns")
@limiter.limit("5/minute")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        # Get user info from Google
        google_user = await google_oauth.handle_google_callback(request)

        # Check if user exists
        user, is_new = google_oauth.find_or_create_user(db, google_user)

        if user:
            # Existing user - log them in (clear session first to prevent fixation)
            user.last_login_at = utcnow_naive()
            db.add(user)
            db.commit()
            db.refresh(user)
            request.session.clear()
            request.session["user_id"] = user.id
            request.session["db_epoch"] = get_db_epoch()
            logger.info(f"Google OAuth login successful for existing user: {user.username}")
            return RedirectResponse(
                url=_user_blog_url(request, user),
                status_code=status.HTTP_302_FOUND
            )
        else:
            # New user - store Google info in session and redirect to setup
            request.session.clear()
            request.session["google_user"] = {
                "google_id": google_user.google_id,
                "email": google_user.email,
                "name": google_user.name,
                "picture": google_user.picture
            }
            logger.info(f"New Google user detected: {google_user.email}. Redirecting to setup.")
            return RedirectResponse(
                url=f"{_frontend_base_url(request)}/autentificare/configurare",
                status_code=status.HTTP_302_FOUND
            )

    except HTTPException as exc:
        logger.warning(f"Autentificarea Google a eșuat: {exc.detail}")
        return RedirectResponse(url=_auth_failure_url(request), status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error(f"Eroare în răspunsul Google: {e}")
        return RedirectResponse(url=_auth_failure_url(request), status_code=status.HTTP_302_FOUND)


@router.get("/autentificare/configurare")
def auth_setup_page(request: Request):
    """Setup page for new Google OAuth users — served by React frontend"""
    google_user_data = request.session.get("google_user")
    if not google_user_data:
        return RedirectResponse(url="/autentificare/google", status_code=status.HTTP_302_FOUND)
    return _react_index_response()


@router.post("/api/autentificare/finalizeaza-configurarea")
def complete_user_setup(request: Request, setup_data: schemas.UserSetup, db: Session = Depends(get_db)):
    """Complete user setup after Google OAuth"""
    google_user_data = request.session.get("google_user")
    if not google_user_data:
        raise HTTPException(status_code=400, detail="Nu există o sesiune de autentificare")

    try:
        # Validate username
        if not re.fullmatch(r"^[a-zA-Z0-9]+$", setup_data.username):
            raise HTTPException(status_code=400, detail="Numele de utilizator poate conține doar litere și cifre, fără spații sau simboluri speciale.")

        # Create Google user info object
        google_user = schemas.GoogleUserInfo(**google_user_data)

        # Create the user
        new_user = google_oauth.create_user_from_google(db, google_user, setup_data)
        new_user.last_login_at = utcnow_naive()
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Clear session and set authenticated user
        request.session.clear()
        request.session["user_id"] = new_user.id
        request.session["db_epoch"] = get_db_epoch()

        logger.info(f"User setup completed for: {new_user.username}")
        return {"message": "Configurarea a fost finalizată", "username": new_user.username}

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
