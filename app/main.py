import os
import re
import logging
from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import Headers
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .error_logging import configure_error_logging
from . import admin, models
from .utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX
from .domains import DOMAIN_ROUTERS

# Configure logging
configure_error_logging()
logger = logging.getLogger(__name__)

if not logger.handlers:
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
ADSENSE_PUBLISHER_ID = os.getenv("ADSENSE_PUBLISHER_ID", "").strip()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(docs_url=None, redoc_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _request_context(request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "-")
    return f"{request.method} {request.url.path} client={client} user_agent={user_agent!r}"


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code >= 500:
        logger.error(
            "HTTP %s while handling %s: %s",
            exc.status_code,
            _request_context(request),
            exc.detail,
            exc_info=True,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error while handling %s: %s", _request_context(request), exc)
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception while handling %s", _request_context(request))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# CORS Middleware — build origin regex from env-configured domain.
_allowed_origin_hosts = [re.escape(MAIN_DOMAIN)]
if SUBDOMAIN_SUFFIX:
    _allowed_origin_hosts.insert(0, rf".*{re.escape(SUBDOMAIN_SUFFIX)}")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=rf"https?://({'|'.join(_allowed_origin_hosts)})(:\d+)?",
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
    domain=SUBDOMAIN_SUFFIX or None,
)

# Mount legacy static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/ads.txt", response_class=PlainTextResponse, include_in_schema=False)
def ads_txt():
    if not ADSENSE_PUBLISHER_ID:
        return PlainTextResponse("", status_code=404)
    return PlainTextResponse(
        f"google.com, {ADSENSE_PUBLISHER_ID}, DIRECT, f08c47fec0942fa0\n"
    )


# Subdomain Middleware
class SubdomainMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            host = headers.get("host", "").split(":", 1)[0]
            state = scope.setdefault("state", {})
            if SUBDOMAIN_SUFFIX and host.endswith(SUBDOMAIN_SUFFIX) and not host.startswith("www.") and host != MAIN_DOMAIN:
                state["is_subdomain"] = True
                state["username"] = host.replace(SUBDOMAIN_SUFFIX, "")
            else:
                state["is_subdomain"] = False
                state["username"] = None
        await self.app(scope, receive, send)


app.add_middleware(SubdomainMiddleware)

# API routers
for router in DOMAIN_ROUTERS:
    app.include_router(router)

# React frontend — serve built assets from frontend/dist/
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
LEGACY_FRONTEND_PATHS = {
    "/admin",
    "/dashboard",
    "/create-post",
    "/messages",
    "/shop",
    "/inventory",
    "/privacy",
    "/terms",
}
LEGACY_FRONTEND_PREFIXES = (
    "/auth",
    "/category",
    "/colectii",
    "/collections",
    "/forum",
)


def _legacy_frontend_path(path: str) -> bool:
    if path in LEGACY_FRONTEND_PATHS:
        return True
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in LEGACY_FRONTEND_PREFIXES)


def _react_index_response() -> FileResponse:
    response = FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/docs", include_in_schema=False)
def serve_admin_documentation(current_user: models.User = Depends(admin.require_admin)):
    if not os.path.isdir(FRONTEND_DIST):
        return JSONResponse(status_code=404, content={"detail": "Frontend build not found"})
    return _react_index_response()

if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="react-assets")

    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        """Catch-all: serve React index.html for client-side routing"""
        normalized_path = f"/{full_path.strip('/')}" if full_path else "/"
        if normalized_path.startswith("/api/") or _legacy_frontend_path(normalized_path):
            return JSONResponse(status_code=404, content={"detail": "Ruta nu a fost găsită"})
        return _react_index_response()
else:
    logger.warning(
        f"React build not found at {FRONTEND_DIST}. "
        "Run 'cd frontend && npm run build' to build the frontend."
    )
