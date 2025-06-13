import os
import logging # Import logging
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env

from datetime import timedelta, datetime # Import timedelta and datetime
from fastapi import FastAPI, Request, Depends, HTTPException, status, Response # Removed Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import Optional # Import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from starlette.types import ASGIApp
from starlette.middleware.sessions import SessionMiddleware # Import SessionMiddleware

from . import models, schemas, crud, auth, google_oauth
from .database import SessionLocal, engine, get_db
from .categories import CATEGORIES_AND_GENRES, get_main_categories, get_all_categories, get_genres_for_category, get_category_name, get_genre_name, is_valid_category, is_valid_genre
import urllib.parse

# Configure logging
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "calimara_app_python.log")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # Also output to console/syslog
    ]
)
logger = logging.getLogger(__name__)

# Ensure tables are created (this is for development, initdb.py is for explicit reset)
# models.Base.metadata.create_all(bind=engine)

# Configuration from environment variables
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "super-secret-session-key-fallback")
MAIN_DOMAIN = os.getenv("MAIN_DOMAIN", "calimara.ro")
SUBDOMAIN_SUFFIX = os.getenv("SUBDOMAIN_SUFFIX", ".calimara.ro")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

app = FastAPI()

# Add Session Middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=SESSION_SECRET_KEY,
    session_cookie="session", # Default name, but explicit
    max_age=14 * 24 * 60 * 60, # 14 days, default is 2 weeks
    domain=SUBDOMAIN_SUFFIX # Crucial for subdomains
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2Templates
templates = Jinja2Templates(directory="templates")

# Add template global functions
def get_avatar_url(user_or_seed, size=80):
    """Generate DiceBear avatar URL for user or seed"""
    if hasattr(user_or_seed, 'avatar_seed'):
        seed = user_or_seed.avatar_seed or f"{user_or_seed.username}-shapes"
    elif hasattr(user_or_seed, 'username'):
        seed = f"{user_or_seed.username}-shapes"
    else:
        seed = str(user_or_seed)
    
    return f"https://api.dicebear.com/7.x/shapes/svg?seed={seed}&backgroundColor=f1f4f8,d1fae5,dbeafe,fce7f3,f3e8ff&size={size}"

templates.env.globals["get_avatar_url"] = get_avatar_url

# Subdomain Middleware
class SubdomainMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host.endswith(SUBDOMAIN_SUFFIX) and not host.startswith("www.") and host != MAIN_DOMAIN:
            username = host.replace(SUBDOMAIN_SUFFIX, "")
            request.state.is_subdomain = True
            request.state.username = username
        else:
            request.state.is_subdomain = False
            request.state.username = None
        response = await call_next(request)
        return response

app.add_middleware(SubdomainMiddleware)

# Helper function to get common template context
def get_common_context(request: Request, current_user: Optional[models.User] = None):
    return {
        "request": request,
        "current_user": current_user,
        "current_domain": request.url.hostname,
        "main_domain": MAIN_DOMAIN,
        "subdomain_suffix": SUBDOMAIN_SUFFIX
    }

# Dependency to get client IP for anonymous likes
def get_client_ip(request: Request):
    return request.client.host

# URL validation function for social media and donation platforms
def validate_social_url(url: str, platform: str) -> bool:
    """Validate that URL matches the expected platform domain"""
    if not url or not url.strip():
        return True  # Empty URLs are valid (will be stored as None)
    
    try:
        parsed = urllib.parse.urlparse(url.lower())
        domain = parsed.netloc.lower()
        
        # Remove www. prefix for comparison
        if domain.startswith('www.'):
            domain = domain[4:]
        
        platform_domains = {
            'facebook': ['facebook.com', 'fb.com'],
            'instagram': ['instagram.com'],
            'tiktok': ['tiktok.com'],
            'x': ['x.com', 'twitter.com'],
            'bluesky': ['bsky.app'],
            'patreon': ['patreon.com'],
            'paypal': ['paypal.me', 'paypal.com'],
            'buymeacoffee': ['buymeacoffee.com']
        }
        
        if platform not in platform_domains:
            return False
            
        return any(domain.endswith(valid_domain) for valid_domain in platform_domains[platform])
    except:
        return False

# --- API Endpoints (Authentication & User Management) ---

# --- Google OAuth Authentication Endpoints ---

@app.get("/auth/google")
async def google_login(request: Request):
    """Initiate Google OAuth flow"""
    try:
        auth_url = await google_oauth.get_google_auth_url(request)
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    except Exception as e:
        logger.error(f"Error initiating Google OAuth: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate authentication")

@app.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        # Get user info from Google
        google_user = await google_oauth.handle_google_callback(request)
        
        # Check if user exists
        user, is_new = google_oauth.find_or_create_user(db, google_user)
        
        if user:
            # Existing user - log them in directly
            request.session["user_id"] = user.id
            logger.info(f"Google OAuth login successful for existing user: {user.username}")
            return RedirectResponse(url=f"https://{user.username}{SUBDOMAIN_SUFFIX}", status_code=status.HTTP_302_FOUND)
        else:
            # New user - store Google info in session and redirect to setup
            request.session["google_user"] = {
                "google_id": google_user.google_id,
                "email": google_user.email,
                "name": google_user.name,
                "picture": google_user.picture
            }
            logger.info(f"New Google user detected: {google_user.email}. Redirecting to setup.")
            return RedirectResponse(url="/auth/setup", status_code=status.HTTP_302_FOUND)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Google callback: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@app.get("/auth/setup", response_class=HTMLResponse)
async def auth_setup_page(request: Request):
    """Setup page for new Google OAuth users"""
    google_user_data = request.session.get("google_user")
    if not google_user_data:
        # No Google user data in session, redirect to login
        return RedirectResponse(url="/auth/google", status_code=status.HTTP_302_FOUND)
    
    context = get_common_context(request)
    context.update({
        "google_user": google_user_data
    })
    return templates.TemplateResponse("auth_setup.html", context)

@app.post("/api/auth/complete-setup")
async def complete_user_setup(request: Request, setup_data: schemas.UserSetup, db: Session = Depends(get_db)):
    """Complete user setup after Google OAuth"""
    google_user_data = request.session.get("google_user")
    if not google_user_data:
        raise HTTPException(status_code=400, detail="No authentication session found")
    
    try:
        # Validate username
        import re
        if not re.fullmatch(r"^[a-zA-Z0-9]+$", setup_data.username):
            raise HTTPException(status_code=400, detail="Numele de utilizator poate conține doar litere și cifre, fără spații sau simboluri speciale.")
        
        # Create Google user info object
        google_user = schemas.GoogleUserInfo(**google_user_data)
        
        # Create the user
        new_user = google_oauth.create_user_from_google(db, google_user, setup_data)
        
        # Clear Google user data from session and set user session
        request.session.pop("google_user", None)
        request.session["user_id"] = new_user.id
        
        logger.info(f"User setup completed for: {new_user.username}")
        return {"message": "Setup completed successfully", "username": new_user.username}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing user setup: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete setup")

@app.get("/api/user/me")
async def get_current_user_info(current_user: Optional[models.User] = Depends(auth.get_current_user)):
    """Endpoint to check current user authentication status"""
    if current_user:
        return {
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "subtitle": current_user.subtitle
            }
        }
    else:
        return {"authenticated": False, "user": None}

@app.get("/api/logout")
async def logout_user(request: Request):
    request.session.clear() # Clear session
    logger.info("Utilizator deconectat. Sesiune ștearsă.")
    
    # Redirect to main domain instead of returning JSON
    return RedirectResponse(url=f"//{MAIN_DOMAIN}", status_code=status.HTTP_302_FOUND)

@app.put("/api/user/me", response_model=schemas.UserInDB) # Changed back to PUT and response_model
async def update_current_user(
    user_update: schemas.UserBase, # Use UserBase for updatable fields
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea profilului pentru utilizatorul: {current_user.username}")
    
    # Update subtitle
    if user_update.subtitle is not None:
        current_user.subtitle = user_update.subtitle
    
    # Update avatar seed
    if hasattr(user_update, 'avatar_seed') and user_update.avatar_seed is not None:
        current_user.avatar_seed = user_update.avatar_seed
    
    # Update social media links
    if hasattr(user_update, 'facebook_url') and user_update.facebook_url is not None:
        current_user.facebook_url = user_update.facebook_url.strip() or None
    if hasattr(user_update, 'tiktok_url') and user_update.tiktok_url is not None:
        current_user.tiktok_url = user_update.tiktok_url.strip() or None
    if hasattr(user_update, 'instagram_url') and user_update.instagram_url is not None:
        current_user.instagram_url = user_update.instagram_url.strip() or None
    if hasattr(user_update, 'x_url') and user_update.x_url is not None:
        current_user.x_url = user_update.x_url.strip() or None
    if hasattr(user_update, 'bluesky_url') and user_update.bluesky_url is not None:
        current_user.bluesky_url = user_update.bluesky_url.strip() or None
    
    # Update donation links
    if hasattr(user_update, 'patreon_url') and user_update.patreon_url is not None:
        current_user.patreon_url = user_update.patreon_url.strip() or None
    if hasattr(user_update, 'paypal_url') and user_update.paypal_url is not None:
        current_user.paypal_url = user_update.paypal_url.strip() or None
    if hasattr(user_update, 'buymeacoffee_url') and user_update.buymeacoffee_url is not None:
        current_user.buymeacoffee_url = user_update.buymeacoffee_url.strip() or None
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Profil utilizator actualizat cu succes: {current_user.username}")
    return current_user

@app.put("/api/user/social-links", response_model=schemas.UserInDB)
async def update_user_social_links(
    social_update: schemas.SocialLinksUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea link-urilor sociale pentru utilizatorul: {current_user.username}")
    
    # Validate URLs for each platform
    validation_errors = []
    
    if social_update.facebook_url and not validate_social_url(social_update.facebook_url, 'facebook'):
        validation_errors.append("URL-ul Facebook trebuie să conțină facebook.com sau fb.com")
    
    if social_update.instagram_url and not validate_social_url(social_update.instagram_url, 'instagram'):
        validation_errors.append("URL-ul Instagram trebuie să conțină instagram.com")
    
    if social_update.tiktok_url and not validate_social_url(social_update.tiktok_url, 'tiktok'):
        validation_errors.append("URL-ul TikTok trebuie să conțină tiktok.com")
    
    if social_update.x_url and not validate_social_url(social_update.x_url, 'x'):
        validation_errors.append("URL-ul X trebuie să conțină x.com sau twitter.com")
    
    if social_update.bluesky_url and not validate_social_url(social_update.bluesky_url, 'bluesky'):
        validation_errors.append("URL-ul BlueSky trebuie să conțină bsky.app")
    
    if social_update.buymeacoffee_url and not validate_social_url(social_update.buymeacoffee_url, 'buymeacoffee'):
        validation_errors.append("URL-ul Cumpără-mi o cafea trebuie să conțină buymeacoffee.com")
    
    if validation_errors:
        raise HTTPException(status_code=422, detail="; ".join(validation_errors))
    
    # Update social media links
    if social_update.facebook_url is not None:
        current_user.facebook_url = social_update.facebook_url.strip() or None
    if social_update.tiktok_url is not None:
        current_user.tiktok_url = social_update.tiktok_url.strip() or None
    if social_update.instagram_url is not None:
        current_user.instagram_url = social_update.instagram_url.strip() or None
    if social_update.x_url is not None:
        current_user.x_url = social_update.x_url.strip() or None
    if social_update.bluesky_url is not None:
        current_user.bluesky_url = social_update.bluesky_url.strip() or None
    
    # Update donation links
    if social_update.buymeacoffee_url is not None:
        current_user.buymeacoffee_url = social_update.buymeacoffee_url.strip() or None
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Link-uri sociale actualizate cu succes pentru utilizatorul: {current_user.username}")
    return current_user

@app.put("/api/user/best-friends")
async def update_best_friends(
    best_friends_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Update user's best friends list (max 3 friends)"""
    try:
        friend_usernames = best_friends_data.get("friends", [])
        
        # Validate max 3 friends
        if len(friend_usernames) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 best friends allowed")
        
        # Remove existing best friends
        db.execute(text("DELETE FROM best_friends WHERE user_id = :user_id"), {"user_id": current_user.id})
        
        # Add new best friends
        for position, username in enumerate(friend_usernames, 1):
            if username.strip():  # Skip empty usernames
                friend = db.query(models.User).filter(models.User.username == username.strip()).first()
                if friend and friend.id != current_user.id:  # Can't add self as best friend
                    new_friendship = models.BestFriend(
                        user_id=current_user.id,
                        friend_user_id=friend.id,
                        position=position
                    )
                    db.add(new_friendship)
        
        db.commit()
        logger.info(f"Best friends actualizați pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Best friends updated successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea best friends pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update best friends")

@app.get("/api/users/search")
async def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Search for users by username for best friends selection"""
    if len(q.strip()) < 2:
        return []
    
    users = db.query(models.User).filter(
        models.User.username.contains(q.strip()),
        models.User.id != current_user.id  # Exclude current user
    ).limit(10).all()
    
    return [{"username": user.username, "subtitle": user.subtitle} for user in users]

@app.put("/api/user/featured-posts")
async def update_featured_posts(
    featured_posts_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Update user's featured posts list (max 3 posts)"""
    try:
        post_ids = featured_posts_data.get("posts", [])
        
        # Validate max 3 posts
        if len(post_ids) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 featured posts allowed")
        
        # Validate that all posts belong to the user
        for post_id in post_ids:
            if post_id:  # Skip empty IDs
                post = db.query(models.Post).filter(
                    models.Post.id == post_id,
                    models.Post.user_id == current_user.id
                ).first()
                if not post:
                    raise HTTPException(status_code=400, detail=f"Post {post_id} not found or not owned by user")
        
        # Remove existing featured posts
        db.execute(text("DELETE FROM featured_posts WHERE user_id = :user_id"), {"user_id": current_user.id})
        
        # Add new featured posts
        for position, post_id in enumerate(post_ids, 1):
            if post_id:  # Skip empty post IDs
                new_featured = models.FeaturedPost(
                    user_id=current_user.id,
                    post_id=post_id,
                    position=position
                )
                db.add(new_featured)
        
        db.commit()
        logger.info(f"Featured posts actualizate pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Featured posts updated successfully"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea featured posts pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update featured posts")

@app.get("/api/posts/archive")
async def get_posts_archive(
    month: int = None,
    year: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get posts archive for current user, optionally filtered by month/year"""
    try:
        if month and year:
            posts = crud.get_posts_by_month_year(db, current_user.id, month, year)
        else:
            posts = crud.get_latest_posts_for_user(db, current_user.id, limit=50)
        
        # Format posts for frontend
        formatted_posts = []
        for post in posts:
            formatted_posts.append({
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "content": post.content[:200] + "..." if len(post.content) > 200 else post.content,
                "category": post.category,
                "view_count": post.view_count,
                "likes_count": post.likes_count,
                "comments_count": len(post.comments),
                "created_at": post.created_at.strftime('%d %B %Y'),
                "url": f"//{current_user.username}.calimara.ro/{post.slug}"
            })
        
        return {"posts": formatted_posts}
        
    except Exception as e:
        logger.error(f"Eroare la obținerea arhivei pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts archive")

@app.get("/api/posts/months")
async def get_available_months(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get available months/years for user's posts"""
    try:
        months = crud.get_available_months_for_user(db, current_user.id)
        return {"months": months}
    except Exception as e:
        logger.error(f"Eroare la obținerea lunilor pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available months")

# --- API Endpoints (Posts) ---

@app.post("/api/posts/", response_model=schemas.Post) # Re-added response_model
async def create_post(
    post: schemas.PostCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    return crud.create_user_post(db=db, post=post, user_id=current_user.id)

@app.put("/api/posts/{post_id}", response_model=schemas.Post) # Changed back to PUT and response_model
async def update_post_api(
    post_id: int,
    post_update: schemas.PostUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
    
    # Delete existing tags and create new ones if tags are provided
    if post_update.tags is not None:
        crud.delete_tags_for_post(db, post_id)
        for tag_name in post_update.tags:
            crud.create_tag(db, post_id, tag_name.strip())
    
    return crud.update_post(db=db, post_id=post_id, post_update=post_update)

@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT) # Changed back to DELETE
async def delete_post_api(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
    crud.delete_post(db=db, post_id=post_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- API Endpoints (Comments) ---

@app.post("/api/posts/{post_id}/comments", response_model=schemas.Comment) # Re-added response_model
async def add_comment_to_post(
    post_id: int,
    comment: schemas.CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user) # Optional for unlogged users
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    user_id = current_user.id if current_user else None
    if not user_id and (not comment.author_name or not comment.author_email):
        raise HTTPException(status_code=400, detail="Numele și emailul autorului sunt obligatorii pentru comentariile neautentificate")

    return crud.create_comment(db=db, comment=comment, post_id=post_id, user_id=user_id)

@app.put("/api/comments/{comment_id}/approve", response_model=schemas.Comment) # Changed back to PUT and response_model
async def approve_comment_api(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comentariul nu a fost găsit")
    
    # Ensure the current user owns the post associated with the comment
    db_post = crud.get_post(db, post_id=db_comment.post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu sunteți autorizat să aprobați acest comentariu")
    
    return crud.approve_comment(db=db, comment_id=comment_id)

@app.delete("/api/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT) # Changed back to DELETE
async def delete_comment_api(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comentariul nu a fost găsit")
    
    # Ensure the current user owns the post associated with the comment
    db_post = crud.get_post(db, post_id=db_comment.post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu sunteți autorizat să ștergeți acest comentariu")
    
    crud.delete_comment(db=db, comment_id=comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- API Endpoints (Likes) ---
@app.post("/api/posts/{post_id}/likes", response_model=schemas.Like) # Re-added likes endpoints
async def add_like_to_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user) # Optional for unlogged users
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    user_id = current_user.id if current_user else None
    ip_address = get_client_ip(request) if not user_id else None # Only use IP if user is not logged in

    db_like = crud.create_like(db=db, post_id=post_id, user_id=user_id, ip_address=ip_address)
    if not db_like:
        raise HTTPException(status_code=409, detail="Ați apreciat deja această postare")
    return db_like

@app.get("/api/posts/{post_id}/likes/count") # Re-added likes endpoints
async def get_likes_count(post_id: int, db: Session = Depends(get_db)):
    count = crud.get_likes_count_for_post(db, post_id)
    return {"post_id": post_id, "likes_count": count}

# --- HTML Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, category: str = "toate", month: int = None, year: int = None, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    # If it's a subdomain, render the blog page
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")
        
        # Get featured posts for the blog owner
        featured_posts_data = crud.get_featured_posts_for_user(db, user.id)
        featured_posts = [fp.post for fp in featured_posts_data]
        
        # Get latest 3 posts
        latest_posts = crud.get_latest_posts_for_user(db, user.id, limit=3)
        
        # Get all posts for archive with statistics (filtered by month/year if provided)
        if month and year:
            all_posts = crud.get_posts_by_month_year(db, user.id, month, year, limit=50)
        else:
            all_posts = crud.get_latest_posts_for_user(db, user.id, limit=50)
        
        # Get available months for filtering
        available_months = crud.get_available_months_for_user(db, user.id)
        
        # Get best friends for the blog owner
        best_friends = crud.get_best_friends_for_user(db, user.id)
        
        # Get user awards and statistics
        user_awards = crud.get_user_awards(db, user.id)
        total_likes = crud.get_user_total_likes(db, user.id)
        total_comments = crud.get_user_total_comments(db, user.id)
        
        # Get approved comments for featured and latest posts
        for post in featured_posts + latest_posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            # likes_count is automatically calculated by the @property in the model
        
        # Add comments count and tags to all posts for archive display
        for post in all_posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            post.tags = crud.get_tags_for_post(db, post.id)
        
        # Get distinct categories for this user's blog
        blog_categories = crud.get_distinct_categories_used(db, user_id=user.id)
        
        context = get_common_context(request, current_user)
        context.update({
            "blog_owner": user,
            "featured_posts": featured_posts,
            "latest_posts": latest_posts,
            "all_posts": all_posts,
            "available_months": available_months,
            "blog_categories": blog_categories,
            "best_friends": best_friends,
            "user_awards": user_awards,
            "total_likes": total_likes,
            "total_comments": total_comments
        })
        return templates.TemplateResponse("blog.html", context)
    else:
        # If not a subdomain (i.e., calimara.ro), always render the main landing page
        # Filter random posts based on category parameter
        if category == "toate":
            random_posts = crud.get_random_posts(db, limit=10)
        else:
            # Map category filter names to actual category keys
            category_mapping = {
                "poezie": "poezie",
                "proza": "proza", 
                "teatru": "teatru",
                "eseu": "eseu",
                "critica_literara": "critica_literara",
                "jurnal": "jurnal",
                "altele": ["literatura_experimentala", "scrisoare"]  # Multiple categories for "altele"
            }
            
            if category in category_mapping:
                mapped_category = category_mapping[category]
                if isinstance(mapped_category, list):
                    # Handle multiple categories for "altele"
                    random_posts = crud.get_random_posts_by_categories(db, mapped_category, limit=10)
                else:
                    random_posts = crud.get_random_posts_by_category(db, mapped_category, limit=10)
            else:
                random_posts = []
        
        random_users = crud.get_random_users(db, limit=10)
        context = get_common_context(request, current_user)
        context.update({
            "random_posts": random_posts,
            "random_users": random_users,
            "categories": CATEGORIES_AND_GENRES, # Pass predefined categories for navigation
            "main_categories": get_main_categories(), # Pass main categories for navigation
            "selected_category": category # Pass selected category for template
        })
        return templates.TemplateResponse("index.html", context)

# Category and Genre Routes
@app.get("/category/{category_key}", response_class=HTMLResponse)
async def category_page(category_key: str, request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user), sort_by: str = "newest"):
    # Validate category
    if not is_valid_category(category_key):
        raise HTTPException(status_code=404, detail="Categoria nu a fost găsită")
    
    # Get posts for this category
    posts = crud.get_posts_by_category_sorted(db, category_key, sort_by=sort_by, limit=6)
    
    # Get approved comments and likes count for each post
    for post in posts:
        post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
        # likes_count is automatically calculated by the @property in the model
    
    context = get_common_context(request, current_user)
    context.update({
        "category_key": category_key,
        "category_name": get_category_name(category_key),
        "genres": get_genres_for_category(category_key),
        "posts": posts,
        "sort_by": sort_by,
        "categories": CATEGORIES_AND_GENRES
    })
    return templates.TemplateResponse("category.html", context)

@app.get("/category/{category_key}/{genre_key}", response_class=HTMLResponse)
async def genre_page(category_key: str, genre_key: str, request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user), sort_by: str = "newest"):
    # Validate category and genre
    if not is_valid_category(category_key) or not is_valid_genre(category_key, genre_key):
        raise HTTPException(status_code=404, detail="Categoria sau genul nu a fost găsit")
    
    # Get posts for this category and genre
    posts = crud.get_posts_by_category_sorted(db, category_key, genre_key, sort_by=sort_by, limit=6)
    
    # Get approved comments and likes count for each post
    for post in posts:
        post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
        # likes_count is automatically calculated by the @property in the model
    
    context = get_common_context(request, current_user)
    context.update({
        "category_key": category_key,
        "category_name": get_category_name(category_key),
        "genre_key": genre_key,
        "genre_name": get_genre_name(category_key, genre_key),
        "posts": posts,
        "sort_by": sort_by,
        "categories": CATEGORIES_AND_GENRES
    })
    return templates.TemplateResponse("genre.html", context)

# API endpoint to get genres for a category (for dynamic form updates)
@app.get("/api/genres/{category_key}")
async def get_genres_api(category_key: str):
    if not is_valid_category(category_key):
        raise HTTPException(status_code=404, detail="Category not found")
    return {"genres": get_genres_for_category(category_key)}

# --- API Endpoints (Tags) ---

@app.get("/api/tags/suggestions")
async def get_tag_suggestions_api(
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get tag suggestions for autocomplete based on partial query"""
    if not query or len(query.strip()) < 2:
        return {"suggestions": []}
    
    suggestions = crud.get_tag_suggestions(db, query.strip(), limit)
    return {"suggestions": [tag[0] for tag in suggestions]}

@app.get("/api/posts/random")
async def get_random_posts_api(
    category: str = "toate",
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get random posts filtered by category for AJAX requests"""
    try:
        # Filter random posts based on category parameter
        if category == "toate":
            random_posts = crud.get_random_posts(db, limit=limit)
        else:
            # Map category filter names to actual category keys
            category_mapping = {
                "poezie": "poezie",
                "proza": "proza", 
                "teatru": "teatru",
                "eseu": "eseu",
                "critica_literara": "critica_literara",
                "jurnal": "jurnal",
                "altele": ["literatura_experimentala", "scrisoare"]  # Multiple categories for "altele"
            }
            
            if category in category_mapping:
                mapped_category = category_mapping[category]
                if isinstance(mapped_category, list):
                    # Handle multiple categories for "altele"
                    random_posts = crud.get_random_posts_by_categories(db, mapped_category, limit=limit)
                else:
                    random_posts = crud.get_random_posts_by_category(db, mapped_category, limit=limit)
            else:
                random_posts = []
        
        # Format posts for frontend
        formatted_posts = []
        for post in random_posts:
            # Get category name for display
            category_name = ""
            if post.category and post.category in CATEGORIES_AND_GENRES:
                category_name = CATEGORIES_AND_GENRES[post.category]["name"]
                if post.genre and post.genre in CATEGORIES_AND_GENRES[post.category]["genres"]:
                    category_name += f" - {CATEGORIES_AND_GENRES[post.category]['genres'][post.genre]}"
            
            formatted_posts.append({
                "id": post.id,
                "title": post.title,
                "slug": post.slug,
                "content": post.content[:120] + "..." if len(post.content) > 120 else post.content,
                "likes_count": post.likes_count,
                "created_at": post.created_at.strftime('%d %b'),
                "category": post.category,
                "category_name": category_name,
                "owner": {
                    "username": post.owner.username,
                    "avatar_seed": post.owner.avatar_seed or f"{post.owner.username}-shapes"
                }
            })
        
        return {"posts": formatted_posts}
        
    except Exception as e:
        logger.error(f"Error getting random posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get random posts")

# --- API Endpoints (Messages) ---

@app.get("/api/messages/conversations")
async def get_user_conversations_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get all conversations for the current user"""
    try:
        conversations = crud.get_user_conversations(db, current_user.id)
        
        # Format conversations for frontend
        formatted_conversations = []
        for conv in conversations:
            other_user = conv.get_other_user(current_user.id)
            latest_message = getattr(conv, '_latest_message', None)
            
            # Count unread messages from the other user in this conversation
            unread_count = db.query(func.count(models.Message.id)).filter(
                models.Message.conversation_id == conv.id,
                models.Message.sender_id != current_user.id,
                models.Message.is_read == False
            ).scalar() or 0
            
            formatted_conversations.append({
                "id": conv.id,
                "other_user": {
                    "id": other_user.id,
                    "username": other_user.username,
                    "subtitle": other_user.subtitle,
                    "avatar_seed": other_user.avatar_seed
                },
                "latest_message": {
                    "id": latest_message.id,
                    "content": latest_message.content[:100] + "..." if len(latest_message.content) > 100 else latest_message.content,
                    "sender_id": latest_message.sender_id,
                    "created_at": latest_message.created_at.isoformat(),
                    "is_read": latest_message.is_read
                } if latest_message else None,
                "unread_count": unread_count,
                "updated_at": conv.updated_at.isoformat()
            })
        
        return {"conversations": formatted_conversations}
        
    except Exception as e:
        logger.error(f"Eroare la obținerea conversațiilor pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversations")

@app.get("/api/messages/conversations/{conversation_id}")
async def get_conversation_messages_api(
    conversation_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get messages for a specific conversation"""
    try:
        # Verify user has access to this conversation
        conversation = crud.get_conversation_by_id(db, conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = crud.get_conversation_messages(db, conversation_id, current_user.id, limit, offset)
        
        # Mark messages as read
        crud.mark_messages_as_read(db, conversation_id, current_user.id)
        
        # Get other user info
        other_user = conversation.get_other_user(current_user.id)
        
        # Format messages for frontend
        formatted_messages = []
        for message in reversed(messages):  # Reverse to show oldest first
            formatted_messages.append({
                "id": message.id,
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "is_read": message.is_read,
                "created_at": message.created_at.isoformat(),
                "is_mine": message.sender_id == current_user.id
            })
        
        return {
            "conversation": {
                "id": conversation.id,
                "other_user": {
                    "id": other_user.id,
                    "username": other_user.username,
                    "subtitle": other_user.subtitle,
                    "avatar_seed": other_user.avatar_seed
                }
            },
            "messages": formatted_messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la obținerea mesajelor pentru conversația {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get messages")

@app.post("/api/messages/conversations/{conversation_id}")
async def send_message_api(
    conversation_id: int,
    message_data: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Send a message in an existing conversation"""
    try:
        message = crud.create_message(db, conversation_id, current_user.id, message_data.content)
        if not message:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
        
        return {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "is_read": message.is_read,
            "created_at": message.created_at.isoformat(),
            "is_mine": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la trimiterea mesajului în conversația {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@app.post("/api/messages/send")
async def send_message_to_user_api(
    message_data: schemas.MessageToUser,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Send a message to a user by username (creates conversation if needed)"""
    try:
        message = crud.send_message_to_user(
            db, current_user.id, message_data.recipient_username, message_data.content
        )
        if not message:
            raise HTTPException(status_code=404, detail="Recipient not found or cannot message yourself")
        
        return {
            "message": "Message sent successfully",
            "conversation_id": message.conversation_id,
            "message_id": message.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la trimiterea mesajului către {message_data.recipient_username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

@app.get("/api/messages/unread-count")
async def get_unread_count_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get count of unread messages for current user"""
    try:
        count = crud.get_unread_message_count(db, current_user.id)
        return {"unread_count": count}
        
    except Exception as e:
        logger.error(f"Eroare la obținerea numărului de mesaje necitite pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get unread count")

@app.delete("/api/messages/conversations/{conversation_id}")
async def delete_conversation_api(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Delete a conversation"""
    try:
        success = crud.delete_conversation(db, conversation_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la ștergerea conversației {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")

@app.get("/api/messages/search")
async def search_conversations_api(
    q: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Search conversations by user or message content"""
    try:
        conversations = crud.search_conversations(db, current_user.id, q)
        
        # Format conversations for frontend
        formatted_conversations = []
        for conv in conversations:
            other_user = conv.get_other_user(current_user.id)
            latest_message = conv.get_latest_message()
            
            formatted_conversations.append({
                "id": conv.id,
                "other_user": {
                    "id": other_user.id,
                    "username": other_user.username,
                    "subtitle": other_user.subtitle,
                    "avatar_seed": other_user.avatar_seed
                },
                "latest_message": {
                    "content": latest_message.content[:100] + "..." if len(latest_message.content) > 100 else latest_message.content,
                    "created_at": latest_message.created_at.isoformat()
                } if latest_message else None
            })
        
        return {"conversations": formatted_conversations}
        
    except Exception as e:
        logger.error(f"Eroare la căutarea conversațiilor pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search conversations")

@app.get("/debug/login-form")
async def debug_login_form(request: Request):
    """Simple HTML form to test login without JavaScript"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug Login Form</title>
    </head>
    <body>
        <h1>Debug Login Test</h1>
        <form method="post" action="/api/token" enctype="application/x-www-form-urlencoded">
            <div>
                <label>Email:</label>
                <input type="email" name="email" value="sad@sad.sad" required>
            </div>
            <div>
                <label>Password:</label>
                <input type="password" name="password" value="123" required>
            </div>
            <div>
                <button type="submit">Login</button>
            </div>
        </form>
        
        <hr>
        
        <h2>Test Links:</h2>
        <ul>
            <li><a href="/api/debug/session">Check Session</a></li>
            <li><a href="/api/debug/user/test">Test User</a></li>
            <li><a href="/api/debug/session/set">Set Test Session</a></li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/debug/login/test")
async def debug_login_test(request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to test login process manually"""
    try:
        logger.info("Debug login test called")
        
        # Try to get the test user
        user = crud.get_user_by_email(db, "sad@sad.sad")
        if not user:
            return {"error": "User not found"}
        
        # Verify password
        password_valid = crud.verify_password("123", user.password_hash)
        if not password_valid:
            return {"error": "Invalid password"}
        
        # Set session
        request.session["user_id"] = user.id
        logger.info(f"Debug login: Session set with user_id={user.id}")
        logger.info(f"Debug login: Session data after set: {dict(request.session)}")
        
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "session_data": dict(request.session)
        }
    except Exception as e:
        logger.error(f"Debug login test error: {e}")
        return {"error": str(e), "type": type(e).__name__}

@app.get("/api/debug/user/test")
async def debug_user_test(db: Session = Depends(get_db)):
    """Debug endpoint to test user lookup and password verification"""
    try:
        user = crud.get_user_by_email(db, "sad@sad.sad")
        if not user:
            return {"error": "User not found"}
        
        # Test password verification
        password_valid = crud.verify_password("123", user.password_hash)
        
        return {
            "user_found": True,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "password_valid": password_valid,
            "password_hash": user.password_hash[:20] + "..." # Only show first part for security
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@app.get("/api/debug/session/set")
async def debug_session_set(request: Request):
    """Debug endpoint to manually set a test session"""
    try:
        request.session["test_key"] = "test_value"
        request.session["timestamp"] = str(datetime.now())
        return {
            "message": "Test session set",
            "session_data": dict(request.session)
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@app.get("/api/debug/session")
async def debug_session(request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to check session status"""
    try:
        session_data = dict(request.session)
        user_id = request.session.get("user_id")
        
        user = None
        if user_id:
            user = crud.get_user_by_id(db, user_id)
        
        # Also check if a user with sad@sad.sad exists
        test_user = crud.get_user_by_email(db, "sad@sad.sad")
        
        return {
            "session_data": session_data,
            "session_keys": list(request.session.keys()),
            "user_id": user_id,
            "user_found": user is not None,
            "user_details": {"id": user.id, "username": user.username, "email": user.email} if user else None,
            "host": request.headers.get("host", ""),
            "cookies": dict(request.cookies),
            "test_user_exists": test_user is not None,
            "test_user_details": {"id": test_user.id, "username": test_user.username} if test_user else None
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@app.get("/api/debug")
async def debug_info(request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to check system status"""
    try:
        # Test database connection
        user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        
        # Test subdomain detection
        host = request.headers.get("host", "")
        is_subdomain = host.endswith(SUBDOMAIN_SUFFIX) and not host.startswith("www.") and host != MAIN_DOMAIN
        username = host.replace(SUBDOMAIN_SUFFIX, "") if is_subdomain else None
        
        # Test user lookup
        user = None
        if username:
            user = crud.get_user_by_username(db, username=username)
        
        return {
            "database_connection": "OK",
            "user_count": user_count,
            "host": host,
            "is_subdomain": is_subdomain,
            "username": username,
            "user_found": user is not None,
            "user_details": {"id": user.id, "username": user.username} if user else None
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

# --- HTML Routes (Messages) ---

@app.get("/messages", response_class=HTMLResponse)
async def messages_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    """Messages inbox page"""
    # If logged in and on main domain, redirect to subdomain messages
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/messages", status_code=status.HTTP_302_FOUND)

    context = get_common_context(request, current_user)
    return templates.TemplateResponse("messages.html", context)

@app.get("/messages/{conversation_id}", response_class=HTMLResponse)
async def conversation_page(conversation_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    """Individual conversation page"""
    # If logged in and on main domain, redirect to subdomain conversation
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/messages/{conversation_id}", status_code=status.HTTP_302_FOUND)

    # Verify user has access to this conversation
    conversation = crud.get_conversation_by_id(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    context = get_common_context(request, current_user)
    context.update({
        "conversation_id": conversation_id
    })
    return templates.TemplateResponse("conversation.html", context)

@app.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)): # Use get_required_user
    # If logged in and on main domain, redirect to subdomain dashboard
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"https://{current_user.username}{SUBDOMAIN_SUFFIX}/dashboard", status_code=status.HTTP_302_FOUND)

    user_posts = crud.get_posts_by_user(db, current_user.id)
    unapproved_comments = crud.get_unapproved_comments_for_user_posts(db, current_user.id)
    
    context = get_common_context(request, current_user)
    context.update({
        "user_posts": user_posts,
        "unapproved_comments": unapproved_comments
    })
    return templates.TemplateResponse("admin_dashboard.html", context)

@app.get("/create-post", response_class=HTMLResponse)
async def create_post_page(request: Request, current_user: models.User = Depends(auth.get_required_user)): # Use get_required_user
    # If logged in and on main domain, redirect to subdomain create-post
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/create-post", status_code=status.HTTP_302_FOUND)

    context = get_common_context(request, current_user)
    context.update({
        "categories": get_all_categories()
    })
    return templates.TemplateResponse("create_post.html", context)

@app.get("/edit-post/{post_id}", response_class=HTMLResponse)
async def edit_post_page(post_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)): # Use get_required_user
    # If logged in and on main domain, redirect to subdomain edit-post
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/edit-post/{post_id}", status_code=status.HTTP_302_FOUND)

    post = crud.get_post(db, post_id)
    if not post or post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
    context = get_common_context(request, current_user)
    context.update({
        "post": post
    })
    return templates.TemplateResponse("edit_post.html", context)

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: Optional[models.User] = Depends(auth.get_current_user)): # Pass current_user
    # If logged in and on main domain, redirect to their subdomain
    if request.url.hostname == MAIN_DOMAIN and current_user:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("register.html", get_common_context(request, current_user))

# Redirect /login to main page, as login is a modal (this route is now handled by the new /login GET route)
# @app.get("/login", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
# async def login_redirect():
#     return "/"

# Catch-all for subdomains that don't match specific routes (e.g., /static on subdomain)
@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, path: str, month: int = None, year: int = None, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)): # Pass current_user
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")
        
        # Check if path is a post slug
        if path and path != "":
            post = crud.get_post_by_slug(db, path)
            if post and post.user_id == user.id:
                # Increment view count
                crud.increment_post_view(db, post.id)
                
                # Get post comments and related data
                post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
                
                # Get related posts from same user
                related_posts = crud.get_posts_by_user(db, user.id, limit=5)
                related_posts = [p for p in related_posts if p.id != post.id][:3]
                
                context = get_common_context(request, current_user)
                context.update({
                    "blog_owner": user,
                    "post": post,
                    "related_posts": related_posts
                })
                return templates.TemplateResponse("post_detail.html", context)
        
        # If no post slug or post not found, show blog homepage
        # Get featured posts for the blog owner
        featured_posts_data = crud.get_featured_posts_for_user(db, user.id)
        featured_posts = [fp.post for fp in featured_posts_data]
        
        # Get latest 3 posts
        latest_posts = crud.get_latest_posts_for_user(db, user.id, limit=3)
        
        # Get all posts for archive with statistics (filtered by month/year if provided)
        if month and year:
            all_posts = crud.get_posts_by_month_year(db, user.id, month, year, limit=50)
        else:
            all_posts = crud.get_latest_posts_for_user(db, user.id, limit=50)
        
        # Get available months for filtering
        available_months = crud.get_available_months_for_user(db, user.id)
        
        # Get best friends for the blog owner
        best_friends = crud.get_best_friends_for_user(db, user.id)
        
        # Get user awards and statistics
        user_awards = crud.get_user_awards(db, user.id)
        total_likes = crud.get_user_total_likes(db, user.id)
        total_comments = crud.get_user_total_comments(db, user.id)
        
        # Get approved comments for featured and latest posts
        for post in featured_posts + latest_posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            # likes_count is automatically calculated by the @property in the model
        
        # Add comments count and tags to all posts for archive display
        for post in all_posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            post.tags = crud.get_tags_for_post(db, post.id)
        
        context = get_common_context(request, current_user)
        context.update({
            "blog_owner": user,
            "featured_posts": featured_posts,
            "latest_posts": latest_posts,
            "all_posts": all_posts,
            "available_months": available_months,
            "best_friends": best_friends,
            "user_awards": user_awards,
            "total_likes": total_likes,
            "total_comments": total_comments
        })
        return templates.TemplateResponse("blog.html", context)
    else:
        # If not a subdomain and no specific route matched, return 404 for main domain
        raise HTTPException(status_code=404, detail="Pagina nu a fost găsită")
