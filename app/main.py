import os
import logging # Import logging
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env

from datetime import timedelta # Import timedelta
from fastapi import FastAPI, Request, Depends, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional # Import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from starlette.types import ASGIApp
from starlette.middleware.sessions import SessionMiddleware # Import SessionMiddleware

from . import models, schemas, crud, auth
from .database import SessionLocal, engine, get_db

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

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "super-secret-session-key-fallback")

app = FastAPI()

# Add Session Middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=SESSION_SECRET_KEY,
    session_cookie="session", # Default name, but explicit
    max_age=14 * 24 * 60 * 60, # 14 days, default is 2 weeks
    domain=".calimara.ro" # Crucial for subdomains
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2Templates
templates = Jinja2Templates(directory="templates")

# Subdomain Middleware
class SubdomainMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host.endswith(".calimara.ro") and not host.startswith("www.") and host != "calimara.ro":
            username = host.replace(".calimara.ro", "")
            request.state.is_subdomain = True
            request.state.username = username
        else:
            request.state.is_subdomain = False
            request.state.username = None
        response = await call_next(request)
        return response

app.add_middleware(SubdomainMiddleware)

# Dependency to get client IP for anonymous likes
def get_client_ip(request: Request):
    return request.client.host

# --- API Endpoints (Authentication & User Management) ---

@app.post("/api/register", response_model=schemas.UserInDB)
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Attempting to register user: {user.email} with username: {user.username}")
    db_user_email = crud.get_user_by_email(db, email=user.email)
    if db_user_email:
        logger.warning(f"Registration failed: Email {user.email} already registered.")
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user_username = crud.get_user_by_username(db, username=user.username)
    if db_user_username:
        logger.warning(f"Registration failed: Username {user.username} already taken.")
        raise HTTPException(status_code=400, detail="Username already taken")
    
    new_user = crud.create_user(db=db, user=user)
    logger.info(f"User registered successfully: {new_user.email}")
    return new_user

@app.post("/api/token")
async def login_for_access_token(request: Request, form_data: schemas.UserLogin, db: Session = Depends(get_db)):
    logger.info(f"Attempting login for email: {form_data.email}")
    user = crud.get_user_by_email(db, email=form_data.email)
    if not user or not crud.verify_password(form_data.password, user.password_hash):
        logger.warning(f"Login failed: Incorrect credentials for {form_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Set user ID in session
    request.session["user_id"] = user.id
    logger.info(f"Login successful for {user.email}. Session set.")
    return {"message": "Logged in successfully", "username": user.username} # Return username for client-side redirect

@app.get("/api/logout")
async def logout_user(request: Request):
    request.session.clear() # Clear session
    logger.info("User logged out. Session cleared.")
    return {"message": "Logged out successfully"}

# --- API Endpoints (Posts) ---

@app.post("/api/posts/", response_model=schemas.Post)
async def create_post(
    post: schemas.PostCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    return crud.create_user_post(db=db, post=post, user_id=current_user.id)

@app.put("/api/posts/{post_id}", response_model=schemas.Post)
async def update_post_api(
    post_id: int,
    post_update: schemas.PostUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found or not owned by user")
    return crud.update_post(db=db, post_id=post_id, post_update=post_update)

@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_api(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found or not owned by user")
    crud.delete_post(db=db, post_id=post_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- API Endpoints (Comments) ---

@app.post("/api/posts/{post_id}/comments", response_model=schemas.Comment)
async def add_comment_to_post(
    post_id: int,
    comment: schemas.CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user) # Optional for unlogged users
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    user_id = current_user.id if current_user else None
    if not user_id and (not comment.author_name or not comment.author_email):
        raise HTTPException(status_code=400, detail="Author name and email are required for unlogged comments")

    return crud.create_comment(db=db, comment=comment, post_id=post_id, user_id=user_id)

@app.put("/api/comments/{comment_id}/approve", response_model=schemas.Comment)
async def approve_comment_api(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Ensure the current user owns the post associated with the comment
    db_post = crud.get_post(db, post_id=db_comment.post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to approve this comment")
    
    return crud.approve_comment(db=db, comment_id=comment_id)

@app.delete("/api/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment_api(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Ensure the current user owns the post associated with the comment
    db_post = crud.get_post(db, post_id=db_comment.post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    
    crud.delete_comment(db=db, comment_id=comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- API Endpoints (Likes) ---

@app.post("/api/posts/{post_id}/likes", response_model=schemas.Like)
async def add_like_to_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user) # Optional for unlogged users
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    user_id = current_user.id if current_user else None
    ip_address = get_client_ip(request) if not user_id else None # Only use IP if user is not logged in

    db_like = crud.create_like(db=db, post_id=post_id, user_id=user_id, ip_address=ip_address)
    if not db_like:
        raise HTTPException(status_code=409, detail="Already liked this post")
    return db_like

@app.get("/api/posts/{post_id}/likes/count")
async def get_likes_count(post_id: int, db: Session = Depends(get_db)):
    count = crud.get_likes_count_for_post(db, post_id)
    return {"post_id": post_id, "likes_count": count}

# --- HTML Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        posts = crud.get_latest_posts_for_user(db, user.id, limit=5) # Get latest 5 posts for the blog
        random_posts = crud.get_random_posts(db, limit=10)
        random_users = crud.get_random_users(db, limit=10)

        # Get approved comments for each post
        for post in posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            post.likes_count = crud.get_likes_count_for_post(db, post.id)

        return templates.TemplateResponse(
            "blog.html",
            {
                "request": request,
                "blog_owner": user,
                "posts": posts,
                "random_posts": random_posts,
                "random_users": random_users,
                "current_user": current_user, # Pass actual current_user
                "current_domain": request.url.hostname # Pass current domain
            }
        )
    else:
        # Main domain logic
        random_posts = crud.get_random_posts(db, limit=10)
        random_users = crud.get_random_users(db, limit=10)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "random_posts": random_posts,
                "random_users": random_users,
                "current_user": current_user, # Pass actual current_user
                "current_domain": request.url.hostname # Pass current domain
            }
        )

@app.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)): # Use get_required_user
    user_posts = crud.get_posts_by_user(db, current_user.id)
    unapproved_comments = crud.get_unapproved_comments_for_user_posts(db, current_user.id)
    
    # Add likes count to posts
    for post in user_posts:
        post.likes_count = crud.get_likes_count_for_post(db, post.id)

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "user_posts": user_posts,
            "unapproved_comments": unapproved_comments,
            "current_domain": request.url.hostname # Pass current domain
        }
    )

@app.get("/create-post", response_class=HTMLResponse)
async def create_post_page(request: Request, current_user: models.User = Depends(auth.get_required_user)): # Use get_required_user
    return templates.TemplateResponse(
        "create_post.html",
        {
            "request": request,
            "current_user": current_user,
            "current_domain": request.url.hostname # Pass current domain
        }
    )

@app.get("/edit-post/{post_id}", response_class=HTMLResponse)
async def edit_post_page(post_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)): # Use get_required_user
    post = crud.get_post(db, post_id)
    if not post or post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found or not owned by user")
    return templates.TemplateResponse(
        "edit_post.html",
        {
            "request": request,
            "current_user": current_user,
            "post": post,
            "current_domain": request.url.hostname # Pass current domain
        }
    )

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: Optional[models.User] = Depends(auth.get_current_user)): # Pass current_user
    return templates.TemplateResponse("register.html", {
        "request": request,
        "current_user": current_user, # Pass actual current_user
        "current_domain": request.url.hostname # Pass current domain
    })

# Redirect /login to main page, as login is a modal
@app.get("/login", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
async def login_redirect():
    return "/"

# Catch-all for subdomains that don't match specific routes (e.g., /static on subdomain)
@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, path: str, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)): # Pass current_user
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blog not found")
        
        posts = crud.get_latest_posts_for_user(db, user.id, limit=5)
        random_posts = crud.get_random_posts(db, limit=10)
        random_users = crud.get_random_users(db, limit=10)

        for post in posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            post.likes_count = crud.get_likes_count_for_post(db, post.id)

        return templates.TemplateResponse(
            "blog.html",
            {
                "request": request,
                "blog_owner": user,
                "posts": posts,
                "random_posts": random_posts,
                "random_users": random_users,
                "current_user": current_user, # Pass actual current_user
                "current_domain": request.url.hostname # Pass current domain
            }
        )
    else:
        # If not a subdomain and no specific route matched, return 404 for main domain
        raise HTTPException(status_code=404, detail="Page not found")
