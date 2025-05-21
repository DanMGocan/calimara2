import os
import logging # Import logging
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env

from datetime import timedelta # Import timedelta
from fastapi import FastAPI, Request, Depends, HTTPException, status, Response, Form # Import Form
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

# Dependency to get client IP for anonymous likes (no longer used for likes, but kept for potential future use)
def get_client_ip(request: Request):
    return request.client.host

# --- API Endpoints (Authentication & User Management) ---

@app.post("/api/register") # No response_model, as it redirects
async def register_user(
    request: Request,
    username: str = Form(...),
    subtitle: Optional[str] = Form(None),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Se încearcă înregistrarea utilizatorului: {email} cu numele de utilizator: {username}")
    db_user_email = crud.get_user_by_email(db, email=email.lower()) # Ensure email is lowercased for uniqueness
    if db_user_email:
        logger.warning(f"Înregistrare eșuată: Emailul {email} este deja înregistrat.")
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error_message": "Emailul este deja înregistrat", "current_user": None, "current_domain": request.url.hostname},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    db_user_username = crud.get_user_by_username(db, username=username.lower()) # Ensure username is lowercased for uniqueness
    if db_user_username:
        logger.warning(f"Înregistrare eșuată: Numele de utilizator {username} este deja luat.")
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error_message": "Numele de utilizator este deja luat", "current_user": None, "current_domain": request.url.hostname},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    user_create_schema = schemas.UserCreate(
        username=username.lower(),
        email=email.lower(),
        password=password,
        subtitle=subtitle
    )
    new_user = crud.create_user(db=db, user=user_create_schema)
    logger.info(f"Utilizator înregistrat cu succes: {new_user.email}")

    # Auto-login after registration
    request.session["user_id"] = new_user.id
    logger.info(f"Autentificare automată reușită pentru {new_user.email}. Sesiune setată.")
    return RedirectResponse(url=f"//{new_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: Optional[models.User] = Depends(auth.get_current_user)):
    if current_user: # If already logged in, redirect to their blog
        return RedirectResponse(url=f"//{current_user.username}.calimara.ro", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/token")
async def login_for_access_token(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    logger.info(f"Se încearcă autentificarea pentru email: {email}")
    user = crud.get_user_by_email(db, email=email)
    if not user or not crud.verify_password(password, user.password_hash):
        logger.warning(f"Autentificare eșuată: Credențiale incorecte pentru {email}")
        # Redirect back to login page with an error message
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error_message": "Email sau parolă incorecte"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    # Set user ID in session
    request.session["user_id"] = user.id
    logger.info(f"Autentificare reușită pentru {user.email}. Sesiune setată.")
    # Redirect to user's subdomain dashboard after successful login
    return RedirectResponse(url=f"//{user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

@app.get("/api/logout")
async def logout_user(request: Request):
    request.session.clear() # Clear session
    logger.info("Utilizator deconectat. Sesiune ștearsă.")
    # Redirect to main domain after logout
    return RedirectResponse(url="//calimara.ro", status_code=status.HTTP_302_FOUND)

@app.post("/api/users/me") # Changed to POST for form submission
async def update_current_user(
    request: Request,
    subtitle: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea profilului pentru utilizatorul: {current_user.username}")
    current_user.subtitle = subtitle # Update subtitle
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Profil utilizator actualizat cu succes: {current_user.username}")
    return RedirectResponse(url=f"//{current_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

# --- API Endpoints (Posts) ---

@app.post("/api/posts/") # No response_model, as it redirects
async def create_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    categories: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    post_create_schema = schemas.PostCreate(title=title, content=content, categories=categories)
    crud.create_user_post(db=db, post=post_create_schema, user_id=current_user.id)
    return RedirectResponse(url=f"//{current_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/api/posts/{post_id}/update") # Changed to POST for form submission
async def update_post_api(
    post_id: int,
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    categories: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
    
    post_update_schema = schemas.PostUpdate(title=title, content=content, categories=categories)
    crud.update_post(db=db, post_id=post_id, post_update=post_update_schema)
    return RedirectResponse(url=f"//{current_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/api/posts/{post_id}/delete") # Changed to POST for form submission
async def delete_post_api(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user) # Use get_required_user
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post or db_post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
    crud.delete_post(db=db, post_id=post_id)
    return RedirectResponse(url=f"//{current_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

# --- API Endpoints (Comments) ---

@app.post("/api/posts/{post_id}/comments") # No response_model, as it redirects
async def add_comment_to_post(
    post_id: int,
    request: Request,
    content: str = Form(...),
    author_name: Optional[str] = Form(None),
    author_email: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user) # Optional for unlogged users
):
    db_post = crud.get_post(db, post_id=post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    user_id = current_user.id if current_user else None
    if not user_id and (not author_name or not author_email):
        # If unlogged and no author details, redirect back with error
        return templates.TemplateResponse(
            "blog.html",
            {
                "request": request,
                "blog_owner": db_post.owner,
                "posts": [db_post], # Pass the single post back
                "random_posts": crud.get_random_posts(db, limit=10),
                "random_users": crud.get_random_users(db, limit=10),
                "blog_categories": crud.get_distinct_categories(db, user_id=db_post.user_id),
                "current_user": current_user,
                "current_domain": request.url.hostname,
                "comment_error": "Numele și emailul autorului sunt obligatorii pentru comentariile neautentificate"
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    comment_create_schema = schemas.CommentCreate(
        content=content,
        author_name=author_name,
        author_email=author_email
    )
    crud.create_comment(db=db, comment=comment_create_schema, post_id=post_id, user_id=user_id)
    return RedirectResponse(url=request.url.path + f"#post-{post_id}", status_code=status.HTTP_302_FOUND) # Redirect back to the post

@app.post("/api/comments/{comment_id}/approve") # Changed to POST for form submission
async def approve_comment_api(
    comment_id: int,
    request: Request,
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
    
    crud.approve_comment(db=db, comment_id=comment_id)
    return RedirectResponse(url=f"//{current_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/api/comments/{comment_id}/delete") # Changed to POST for form submission
async def delete_comment_api(
    comment_id: int,
    request: Request,
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
    return RedirectResponse(url=f"//{current_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

# --- API Endpoints (Likes) ---
# Removed likes endpoints as per user request for server-side only.

# --- HTML Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    # If user is logged in and on the main domain, redirect to their subdomain
    if not request.state.is_subdomain and current_user:
        return RedirectResponse(url=f"//{current_user.username}.calimara.ro", status_code=status.HTTP_302_FOUND)

    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")
        
        posts = crud.get_latest_posts_for_user(db, user.id, limit=1) # Get only the last post
        random_posts = crud.get_random_posts(db, limit=10)
        random_users = crud.get_random_users(db, limit=10)
        
        # Get distinct categories for this user's blog
        blog_categories = crud.get_distinct_categories(db, user_id=user.id)

        # Get approved comments for each post
        for post in posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            # No likes count needed if likes are removed
            # post.likes_count = crud.get_likes_count_for_post(db, post.id)

        return templates.TemplateResponse(
            "blog.html",
            {
                "request": request,
                "blog_owner": user,
                "posts": posts,
                "random_posts": random_posts,
                "random_users": random_users,
                "blog_categories": blog_categories, # Pass blog categories
                "current_user": current_user, # Pass actual current_user
                "current_domain": request.url.hostname # Pass current domain
            }
        )
    else:
        # Main domain logic (if not logged in)
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
    # If logged in and on main domain, redirect to subdomain dashboard
    if request.url.hostname == "calimara.ro":
        return RedirectResponse(url=f"//{current_user.username}.calimara.ro/dashboard", status_code=status.HTTP_302_FOUND)

    user_posts = crud.get_posts_by_user(db, current_user.id)
    unapproved_comments = crud.get_unapproved_comments_for_user_posts(db, current_user.id)
    
    # Add likes count to posts (no longer needed if likes are removed)
    # for post in user_posts:
    #     post.likes_count = crud.get_likes_count_for_post(db, post.id)

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
    # If logged in and on main domain, redirect to subdomain create-post
    if request.url.hostname == "calimara.ro":
        return RedirectResponse(url=f"//{current_user.username}.calimara.ro/create-post", status_code=status.HTTP_302_FOUND)

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
    # If logged in and on main domain, redirect to subdomain edit-post
    if request.url.hostname == "calimara.ro":
        return RedirectResponse(url=f"//{current_user.username}.calimara.ro/edit-post/{post_id}", status_code=status.HTTP_302_FOUND)

    post = crud.get_post(db, post_id)
    if not post or post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
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
    # If logged in and on main domain, redirect to their subdomain
    if request.url.hostname == "calimara.ro" and current_user:
        return RedirectResponse(url=f"//{current_user.username}.calimara.ro", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse("register.html", {
        "request": request,
        "current_user": current_user, # Pass actual current_user
        "current_domain": request.url.hostname # Pass current domain
    })

# Redirect /login to main page, as login is a modal (this route is now handled by the new /login GET route)
# @app.get("/login", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
# async def login_redirect():
#     return "/"

# Catch-all for subdomains that don't match specific routes (e.g., /static on subdomain)
@app.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, path: str, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)): # Pass current_user
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")
        
        posts = crud.get_latest_posts_for_user(db, user.id, limit=5)
        random_posts = crud.get_random_posts(db, limit=10)
        random_users = crud.get_random_users(db, limit=10)

        for post in posts:
            post.comments = crud.get_comments_for_post(db, post.id, approved_only=True)
            # No likes count needed if likes are removed
            # post.likes_count = crud.get_likes_count_for_post(db, post.id)

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
        raise HTTPException(status_code=404, detail="Pagina nu a fost găsită")
