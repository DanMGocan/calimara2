import os
import logging # Import logging
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env

from datetime import timedelta # Import timedelta
from fastapi import FastAPI, Request, Depends, HTTPException, status, Response # Removed Form
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

@app.post("/api/register", response_model=schemas.UserInDB) # Re-added response_model
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    logger.info(f"Se încearcă înregistrarea utilizatorului: {user.email} cu numele de utilizator: {user.username}")
    
    # Validate username: must be one word (no spaces)
    if " " in user.username:
        logger.warning(f"Înregistrare eșuată: Numele de utilizator '{user.username}' conține spații.")
        raise HTTPException(status_code=400, detail="Numele de utilizator nu poate conține spații. Vă rugăm să folosiți un singur cuvânt.")

    db_user_email = crud.get_user_by_email(db, email=user.email.lower()) # Ensure email is lowercased for uniqueness
    if db_user_email:
        logger.warning(f"Înregistrare eșuată: Emailul {user.email} este deja înregistrat.")
        raise HTTPException(status_code=400, detail="Emailul este deja înregistrat")
    db_user_username = crud.get_user_by_username(db, username=user.username.lower()) # Ensure username is lowercased for uniqueness
    if db_user_username:
        logger.warning(f"Înregistrare eșuată: Numele de utilizator {user.username} este deja luat.")
        raise HTTPException(status_code=400, detail="Numele de utilizator este deja luat")
    
    # Ensure username and email are stored in lowercase
    user.username = user.username.lower()
    user.email = user.email.lower()

    new_user = crud.create_user(db=db, user=user)
    logger.info(f"Utilizator înregistrat cu succes: {new_user.email}")
    return new_user

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: Optional[models.User] = Depends(auth.get_current_user)):
    if current_user: # If already logged in, redirect to their blog
        return RedirectResponse(url=f"//{current_user.username}.calimara.ro", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/token")
async def login_for_access_token(request: Request, form_data: schemas.UserLogin, db: Session = Depends(get_db)): # Changed back to schemas.UserLogin
    logger.info(f"Se încearcă autentificarea pentru email: {form_data.email}")
    user = crud.get_user_by_email(db, email=form_data.email)
    if not user or not crud.verify_password(form_data.password, user.password_hash):
        logger.warning(f"Autentificare eșuată: Credențiale incorecte pentru {form_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email sau parolă incorecte",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Set user ID in session
    request.session["user_id"] = user.id
    logger.info(f"Autentificare reușită pentru {user.email}. Sesiune setată.")
    return {"message": "Autentificat cu succes", "username": user.username} # Return username for client-side redirect

@app.get("/api/logout")
async def logout_user(request: Request):
    request.session.clear() # Clear session
    logger.info("Utilizator deconectat. Sesiune ștearsă.")
    return {"message": "Deconectat cu succes"} # Changed back to message for JS handling

@app.put("/api/users/me", response_model=schemas.UserInDB) # Changed back to PUT and response_model
async def update_current_user(
    user_update: schemas.UserBase, # Use UserBase for updatable fields
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea profilului pentru utilizatorul: {current_user.username}")
    # Only allow updating subtitle for now
    if user_update.subtitle is not None:
        current_user.subtitle = user_update.subtitle
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Profil utilizator actualizat cu succes: {current_user.username}")
    return current_user

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
async def read_root(request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    # If it's a subdomain, render the blog page
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
            post.likes_count = crud.get_likes_count_for_post(db, post.id) # Re-added likes count

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
        # If not a subdomain (i.e., calimara.ro), always render the main landing page
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
            post.likes_count = crud.get_likes_count_for_post(db, post.id) # Re-added likes count

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
