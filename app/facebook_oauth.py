import base64
import json
import logging
import os
import secrets
import time
import urllib.parse
from typing import Optional

import httpx
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .utils import default_cover_seed
from .week_util import utcnow_naive

logger = logging.getLogger(__name__)

FACEBOOK_CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
FACEBOOK_CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")
FACEBOOK_REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")
FACEBOOK_GRAPH_VERSION = os.getenv("FACEBOOK_GRAPH_VERSION", "v19.0")

if not all([FACEBOOK_CLIENT_ID, FACEBOOK_CLIENT_SECRET, FACEBOOK_REDIRECT_URI]):
    logger.warning("Facebook OAuth credentials not fully configured")


def _state_payload(request: Request) -> dict:
    return {
        "csrf_token": secrets.token_urlsafe(32),
        "timestamp": int(time.time()),
        "host": request.headers.get("host", "calimara.ro"),
    }


def get_facebook_auth_url(request: Request) -> str:
    state_data = _state_payload(request)
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    request.session["facebook_oauth_csrf"] = state_data["csrf_token"]
    request.session["facebook_oauth_timestamp"] = state_data["timestamp"]
    params = {
        "client_id": FACEBOOK_CLIENT_ID,
        "redirect_uri": FACEBOOK_REDIRECT_URI,
        "scope": "email,public_profile",
        "response_type": "code",
        "state": state,
    }
    return f"https://www.facebook.com/{FACEBOOK_GRAPH_VERSION}/dialog/oauth?{urllib.parse.urlencode(params)}"


def _validate_state(request: Request, received_state: Optional[str]) -> None:
    if not received_state:
        raise HTTPException(status_code=400, detail="Lipsește parametrul OAuth state")
    try:
        state_data = json.loads(base64.urlsafe_b64decode(received_state.encode()).decode())
        csrf_token = state_data.get("csrf_token")
        timestamp = state_data.get("timestamp")
    except Exception as exc:
        logger.error("Failed to decode Facebook OAuth state: %s", exc)
        raise HTTPException(status_code=400, detail="Format OAuth state invalid")
    stored_csrf = request.session.get("facebook_oauth_csrf")
    stored_timestamp = request.session.get("facebook_oauth_timestamp")
    if stored_csrf and stored_timestamp:
        if csrf_token != stored_csrf or timestamp != stored_timestamp:
            raise HTTPException(status_code=400, detail="Parametru OAuth state invalid")
    elif int(time.time()) - int(timestamp or 0) > 600:
        raise HTTPException(status_code=400, detail="Parametrul OAuth state a expirat")
    request.session.pop("facebook_oauth_csrf", None)
    request.session.pop("facebook_oauth_timestamp", None)


async def handle_facebook_callback(request: Request) -> schemas.FacebookUserInfo:
    query_params = dict(request.query_params)
    _validate_state(request, query_params.get("state"))
    if query_params.get("error"):
        raise HTTPException(status_code=400, detail=query_params.get("error_description") or "Autentificarea Facebook a eșuat")
    auth_code = query_params.get("code")
    if not auth_code:
        raise HTTPException(status_code=400, detail="Lipsește codul de autorizare")
    token_url = f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/oauth/access_token"
    user_url = f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/me"
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.get(
                token_url,
                params={
                    "client_id": FACEBOOK_CLIENT_ID,
                    "client_secret": FACEBOOK_CLIENT_SECRET,
                    "redirect_uri": FACEBOOK_REDIRECT_URI,
                    "code": auth_code,
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="Nu am putut obține tokenul Facebook")
            user_response = await client.get(
                user_url,
                params={
                    "fields": "id,name,email,picture",
                    "access_token": access_token,
                },
            )
            user_response.raise_for_status()
            user_info = user_response.json()
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.error("HTTP error during Facebook OAuth: %s", exc)
        raise HTTPException(status_code=400, detail="Autentificarea Facebook a eșuat")
    except Exception as exc:
        logger.error("Unexpected error during Facebook callback: %s", exc)
        raise HTTPException(status_code=500, detail="Autentificarea Facebook a eșuat")

    email = (user_info.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Contul Facebook nu oferă o adresă de email.")
    picture = ((user_info.get("picture") or {}).get("data") or {}).get("url")
    return schemas.FacebookUserInfo(
        facebook_id=str(user_info["id"]),
        email=email,
        name=user_info.get("name", ""),
        picture=picture,
        email_verified=True,
    )


def find_or_create_user(db: Session, facebook_user: schemas.FacebookUserInfo) -> tuple[Optional[models.User], bool]:
    user = crud.get_user_by_facebook_id(db, facebook_user.facebook_id)
    if user:
        changed = False
        if facebook_user.email_verified and user.email != facebook_user.email.lower():
            user.email = facebook_user.email.lower()
            changed = True
        if facebook_user.email_verified and not user.email_verified_at:
            user.email_verified_at = utcnow_naive()
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
        return user, False

    user = crud.get_user_by_email(db, facebook_user.email) if facebook_user.email_verified else None
    if user:
        user.facebook_id = facebook_user.facebook_id
        if not user.email_verified_at:
            user.email_verified_at = utcnow_naive()
        db.commit()
        db.refresh(user)
        return user, False
    return None, True


def create_user_from_facebook(db: Session, facebook_user: schemas.FacebookUserInfo, setup_data: schemas.UserSetup) -> models.User:
    existing_user = crud.get_user_by_username(db, setup_data.username.lower())
    if existing_user:
        raise HTTPException(status_code=400, detail="Numele de utilizator este deja folosit")
    existing_email = crud.get_user_by_email(db, facebook_user.email)
    if existing_email:
        raise HTTPException(status_code=400, detail="Există deja un cont cu această adresă")
    user_data = {
        "username": setup_data.username.lower(),
        "email": facebook_user.email.lower(),
        "facebook_id": facebook_user.facebook_id,
        "subtitle": setup_data.subtitle,
        "avatar_seed": setup_data.avatar_seed,
        "cover_seed": setup_data.cover_seed or default_cover_seed(setup_data.username.lower()),
        "email_verified_at": utcnow_naive(),
    }
    new_user = crud.create_user_from_google(db, user_data)
    logger.info("Created new user from Facebook OAuth: %s", new_user.username)
    return new_user
