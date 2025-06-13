import os
import logging
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.starlette_client import OAuthError
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from . import crud, models, schemas

logger = logging.getLogger(__name__)

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI]):
    logger.warning("Google OAuth credentials not fully configured")

# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

async def get_google_auth_url(request: Request) -> str:
    """Generate Google OAuth authorization URL"""
    try:
        redirect_uri = GOOGLE_REDIRECT_URI
        authorization_url = await oauth.google.create_authorization_url(
            request, redirect_uri
        )
        return authorization_url['url']
    except Exception as e:
        logger.error(f"Error creating Google auth URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to create authorization URL")

async def handle_google_callback(request: Request) -> schemas.GoogleUserInfo:
    """Handle Google OAuth callback and extract user info"""
    try:
        # Get the authorization code from the callback
        token = await oauth.google.authorize_access_token(request)
        
        # Get user information from Google
        user_info = token.get('userinfo')
        if not user_info:
            # If userinfo is not in token, fetch it
            resp = await oauth.google.parse_id_token(request, token)
            user_info = resp
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user information from Google")
        
        # Extract relevant information
        google_user = schemas.GoogleUserInfo(
            google_id=user_info['sub'],  # Google's unique identifier
            email=user_info['email'],
            name=user_info.get('name', ''),
            picture=user_info.get('picture')
        )
        
        logger.info(f"Successfully authenticated Google user: {google_user.email}")
        return google_user
        
    except OAuthError as e:
        logger.error(f"OAuth error during Google callback: {e}")
        raise HTTPException(status_code=400, detail="OAuth authentication failed")
    except Exception as e:
        logger.error(f"Unexpected error during Google callback: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

def find_or_create_user(db: Session, google_user: schemas.GoogleUserInfo) -> tuple[models.User, bool]:
    """
    Find existing user by Google ID or email, or return None if not found.
    Returns (user, is_new) tuple where is_new indicates if this is a new user
    """
    # First try to find by Google ID
    user = crud.get_user_by_google_id(db, google_user.google_id)
    if user:
        # Update email if it has changed
        if user.email != google_user.email:
            user.email = google_user.email
            db.commit()
            db.refresh(user)
        return user, False
    
    # Then try to find by email (for migration of existing users)
    user = crud.get_user_by_email(db, google_user.email)
    if user:
        # Update the user with Google ID for future logins
        user.google_id = google_user.google_id
        db.commit()
        db.refresh(user)
        return user, False
    
    # User doesn't exist, return None to indicate setup is needed
    return None, True

def create_user_from_google(db: Session, google_user: schemas.GoogleUserInfo, setup_data: schemas.UserSetup) -> models.User:
    """Create a new user from Google OAuth data and setup information"""
    
    # Validate username is available
    existing_user = crud.get_user_by_username(db, setup_data.username.lower())
    if existing_user:
        raise HTTPException(status_code=400, detail="Username is already taken")
    
    # Create new user
    user_data = {
        'username': setup_data.username.lower(),
        'email': google_user.email.lower(),
        'google_id': google_user.google_id,
        'subtitle': setup_data.subtitle,
        'avatar_seed': setup_data.avatar_seed
    }
    
    new_user = crud.create_user_from_google(db, user_data)
    logger.info(f"Created new user from Google OAuth: {new_user.username}")
    return new_user