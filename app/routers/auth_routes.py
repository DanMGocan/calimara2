import re
import logging

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import models, schemas, google_oauth, auth
from ..auth import get_db_epoch
from ..database import get_db
from ..utils import SUBDOMAIN_SUFFIX, MAIN_DOMAIN

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["auth"])


@router.get("/auth/google")
@limiter.limit("5/minute")
async def google_login(request: Request):
    """Initiate Google OAuth flow"""
    try:
        auth_url = google_oauth.get_google_auth_url(request)
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error(f"Error initiating Google OAuth: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate authentication")


@router.get("/auth/google/callback")
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
            request.session.clear()
            request.session["user_id"] = user.id
            request.session["db_epoch"] = get_db_epoch()
            logger.info(f"Google OAuth login successful for existing user: {user.username}")
            protocol = "https" if "localhost" not in MAIN_DOMAIN else "http"
            return RedirectResponse(
                url=f"{protocol}://{MAIN_DOMAIN}/auth/callback?status=success",
                status_code=status.HTTP_302_FOUND
            )
        else:
            # New user - store Google info in session and redirect to setup
            request.session["google_user"] = {
                "google_id": google_user.google_id,
                "email": google_user.email,
                "name": google_user.name,
                "picture": google_user.picture
            }
            logger.info(f"New Google user detected: {google_user.email}. Redirecting to setup.")
            protocol = "https" if "localhost" not in MAIN_DOMAIN else "http"
            return RedirectResponse(
                url=f"{protocol}://{MAIN_DOMAIN}/auth/callback?status=setup",
                status_code=status.HTTP_302_FOUND
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Google callback: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/auth/setup")
def auth_setup_page(request: Request):
    """Setup page for new Google OAuth users — served by React frontend"""
    google_user_data = request.session.get("google_user")
    if not google_user_data:
        return RedirectResponse(url="/auth/google", status_code=status.HTTP_302_FOUND)
    # React catch-all will serve the frontend for this route
    from fastapi.responses import FileResponse
    import os
    frontend_index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist", "index.html")
    return FileResponse(frontend_index)


@router.post("/api/auth/complete-setup")
def complete_user_setup(request: Request, setup_data: schemas.UserSetup, db: Session = Depends(get_db)):
    """Complete user setup after Google OAuth"""
    google_user_data = request.session.get("google_user")
    if not google_user_data:
        raise HTTPException(status_code=400, detail="No authentication session found")

    try:
        # Validate username
        if not re.fullmatch(r"^[a-zA-Z0-9]+$", setup_data.username):
            raise HTTPException(status_code=400, detail="Numele de utilizator poate conține doar litere și cifre, fără spații sau simboluri speciale.")

        # Create Google user info object
        google_user = schemas.GoogleUserInfo(**google_user_data)

        # Create the user
        new_user = google_oauth.create_user_from_google(db, google_user, setup_data)

        # Clear session and set authenticated user
        request.session.clear()
        request.session["user_id"] = new_user.id
        request.session["db_epoch"] = get_db_epoch()

        logger.info(f"User setup completed for: {new_user.username}")
        return {"message": "Setup completed successfully", "username": new_user.username}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing user setup: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete setup")


@router.get("/api/logout")
def logout_user(request: Request):
    request.session.clear()  # Clear session
    logger.info("Utilizator deconectat. Sesiune stearsa.")

    # Return JSON for React SPA, or redirect for direct browser access
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"success": True}
    return RedirectResponse(url=f"//{MAIN_DOMAIN}", status_code=status.HTTP_302_FOUND)
