import os
import logging
from datetime import datetime
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
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

async def get_google_auth_url(request: Request) -> str:
    """Generate Google OAuth authorization URL"""
    # Always use manual URL generation to avoid Authlib parameter conflicts
    import urllib.parse
    import secrets
    import base64
    import json
    
    # Generate state with embedded session info for cross-domain validation
    state_data = {
        'csrf_token': secrets.token_urlsafe(32),
        'timestamp': int(datetime.now().timestamp()),
        'host': request.headers.get('host', 'calimara.ro')
    }
    
    # Encode state as base64 JSON for cross-domain compatibility
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()
    
    # Store minimal info in session as backup
    request.session['oauth_csrf'] = state_data['csrf_token']
    request.session['oauth_timestamp'] = state_data['timestamp']
    
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'scope': 'openid email profile',
        'response_type': 'code',
        'access_type': 'offline',
        'state': state
    }
    auth_url = 'https://accounts.google.com/o/oauth2/auth?' + urllib.parse.urlencode(params)
    logger.info(f"Generated OAuth URL with embedded state from host: {state_data['host']}")
    return auth_url

async def handle_google_callback(request: Request) -> schemas.GoogleUserInfo:
    """Handle Google OAuth callback and extract user info"""
    try:
        import base64
        import json
        
        # Validate state parameter for CSRF protection
        query_params = dict(request.query_params)
        if 'state' not in query_params:
            raise HTTPException(status_code=400, detail="Missing OAuth state parameter")
            
        received_state = query_params['state']
        
        # Decode the embedded state
        try:
            state_data = json.loads(base64.urlsafe_b64decode(received_state.encode()).decode())
            csrf_token = state_data.get('csrf_token')
            timestamp = state_data.get('timestamp')
            original_host = state_data.get('host')
        except Exception as e:
            logger.error(f"Failed to decode OAuth state: {e}")
            raise HTTPException(status_code=400, detail="Invalid OAuth state format")
        
        # Validate against session (if available) or use embedded validation
        stored_csrf = request.session.get('oauth_csrf')
        stored_timestamp = request.session.get('oauth_timestamp')
        
        # Use session validation if available, otherwise validate embedded state
        if stored_csrf and stored_timestamp:
            if csrf_token != stored_csrf or timestamp != stored_timestamp:
                logger.error(f"OAuth state mismatch via session: csrf={csrf_token[:8]}... vs {stored_csrf[:8] if stored_csrf else None}...")
                raise HTTPException(status_code=400, detail="Invalid OAuth state parameter")
        else:
            # Validate timestamp is recent (within 10 minutes) as fallback
            current_time = int(datetime.now().timestamp())
            if current_time - timestamp > 600:  # 10 minutes
                logger.error(f"OAuth state expired: {current_time - timestamp} seconds old")
                raise HTTPException(status_code=400, detail="OAuth state expired")
        
        # Clear the stored state
        request.session.pop('oauth_csrf', None)
        request.session.pop('oauth_timestamp', None)
        
        logger.info(f"OAuth state validated successfully for host: {original_host}")
        
        # Get the authorization code
        if 'code' not in query_params:
            raise HTTPException(status_code=400, detail="Missing authorization code")
            
        auth_code = query_params['code']
        
        # Manual token exchange to avoid Authlib issues
        import httpx
        
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': auth_code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_response = await client.post(
                'https://oauth2.googleapis.com/token',
                data=token_data
            )
            token_response.raise_for_status()
            tokens = token_response.json()
            
            # Get user info using access token
            user_response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f"Bearer {tokens['access_token']}"}
            )
            user_response.raise_for_status()
            user_info = user_response.json()
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user information from Google")
        
        # Extract relevant information
        google_user = schemas.GoogleUserInfo(
            google_id=user_info['id'],  # Google's unique identifier
            email=user_info['email'],
            name=user_info.get('name', ''),
            picture=user_info.get('picture')
        )
        
        logger.info(f"Successfully authenticated Google user: {google_user.email}")
        return google_user
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error during Google OAuth: {e}")
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