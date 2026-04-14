import os
import logging
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX
from .routers import auth_routes, user_routes, post_routes, message_routes, moderation_routes, api_pages, notification_routes, stats_routes

# Configure logging
logger = logging.getLogger(__name__)

if not logger.hasHandlers():
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
    LOG_FILE = os.path.join(LOG_DIR, "calimara_app_python.log")

    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)

# Session secret
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
if not SESSION_SECRET_KEY:
    raise RuntimeError(
        "SESSION_SECRET_KEY not configured. Set it in your .env file."
    )

HTTPS_ONLY = os.getenv("HTTPS_ONLY", "True").lower() in ("true", "1", "yes")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(.*\.calimara\.ro|localhost(:\d+)?|.*\.lvh\.me(:\d+)?|lvh\.me(:\d+)?)",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Session Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="calimara_sess",
    max_age=14 * 24 * 60 * 60,  # 14 days
    same_site="lax",
    https_only=HTTPS_ONLY,
    domain=SUBDOMAIN_SUFFIX
)

# Mount legacy static files
app.mount("/static", StaticFiles(directory="static"), name="static")


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

# API routers
app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(post_routes.router)
app.include_router(message_routes.router)
app.include_router(moderation_routes.router)
app.include_router(api_pages.router)
app.include_router(notification_routes.router)
app.include_router(stats_routes.router)

# React frontend — serve built assets from frontend/dist/
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="react-assets")

    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        """Catch-all: serve React index.html for client-side routing"""
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    logger.warning(
        f"React build not found at {FRONTEND_DIST}. "
        "Run 'cd frontend && npm run build' to build the frontend."
    )
