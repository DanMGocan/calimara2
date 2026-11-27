import os
import re
import logging
import time
from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import Headers
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .error_logging import CappedFileHandler, configure_error_logging
from . import admin, models, seo
from .database import get_db
from .utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX
from .domains import DOMAIN_ROUTERS

# Configure logging
configure_error_logging()
logger = logging.getLogger(__name__)

if not logger.handlers:
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
    LOG_FILE = os.path.join(LOG_DIR, "calimara_app_python.log")

    os.makedirs(LOG_DIR, exist_ok=True)

    file_handler = CappedFileHandler(LOG_FILE)
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


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


SLOW_REQUEST_MS = _env_int("SLOW_REQUEST_MS", 750)


def session_cookie_domain(subdomain_suffix: str) -> str | None:
    suffix = (subdomain_suffix or "").strip()
    host = suffix.lstrip(".").split(":", 1)[0].lower()
    if not suffix or host == "localhost" or re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        return None
    return suffix


SESSION_COOKIE_DOMAIN = session_cookie_domain(SUBDOMAIN_SUFFIX)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(docs_url=None, redoc_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _validation_error_payload(exc: RequestValidationError) -> dict:
    errors = []
    for error in exc.errors():
        item = dict(error)
        ctx = item.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            item["ctx"] = {**ctx, "error": str(ctx["error"])}
        errors.append(item)
    return {"detail": errors}


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
    return JSONResponse(status_code=422, content=jsonable_encoder(_validation_error_payload(exc)))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception while handling %s", _request_context(request))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.middleware("http")
async def slow_request_logger(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if SLOW_REQUEST_MS > 0 and elapsed_ms >= SLOW_REQUEST_MS:
        logger.warning("Slow request %sms while handling %s", elapsed_ms, _request_context(request))
    return response

# CORS Middleware: build origin regex from env-configured domain.
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
    domain=SESSION_COOKIE_DOMAIN,
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


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt():
    return PlainTextResponse(
        seo.build_robots_txt(),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(db=Depends(get_db)):
    return PlainTextResponse(
        seo.build_sitemap_xml(db),
        media_type="application/xml; charset=utf-8",
    )


# Subdomain Middleware
class SubdomainMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            host = headers.get("host", "").split(":", 1)[0].lower()
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

# React frontend: serve built assets from frontend/dist/
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


NOT_FOUND_MARKER = '<meta name="calimara-status" content="404" />'


def _not_found_page(title: str = "Pagină negăsită"):
    """The SPA shell with a 404 status; the frontend renders its not-found page."""
    return _react_index_response(
        metadata=seo.PageMetadata(
            title=f"{title} | {seo.SITE_NAME}",
            description="Pagina căutată nu există pe Călimara.",
            canonical_url=seo.main_url("/"),
            robots="noindex, nofollow",
            not_found=True,
        ),
        fallback_detail=title,
    )


def _author_subdomain_not_found_response(request: Request, db):
    username = getattr(getattr(request, "state", None), "username", None)
    if not username:
        return None
    user_exists = (
        db.query(models.User.id)
        .filter(models.User.username == username)
        .first()
        is not None
    )
    if user_exists:
        return None
    return _not_found_page("Autorul nu a fost găsit")


def _apply_no_store_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _react_index_response(
    request: Request | None = None,
    db=None,
    metadata: seo.PageMetadata | None = None,
    fallback_detail: str = "Frontend build not found",
):
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if not os.path.isfile(index_path):
        return JSONResponse(status_code=404, content={"detail": fallback_detail})
    if metadata is None and request is not None and db is not None:
        metadata = seo.build_page_metadata(db, request)
    if metadata is None:
        return _apply_no_store_headers(FileResponse(index_path))
    with open(index_path, "r", encoding="utf-8") as file:
        html = file.read()
    rendered = seo.render_index_html(html, metadata)
    if metadata.not_found:
        rendered = rendered.replace("</head>", f"  {NOT_FOUND_MARKER}\n  </head>", 1)
    response = HTMLResponse(rendered, status_code=404 if metadata.not_found else 200)
    if metadata.noindex:
        response.headers["X-Robots-Tag"] = metadata.robots
    return _apply_no_store_headers(response)


@app.get("/docs", include_in_schema=False)
def serve_admin_documentation(
    request: Request,
    current_user: models.User = Depends(admin.require_admin),
):
    if not os.path.isdir(FRONTEND_DIST):
        return JSONResponse(status_code=404, content={"detail": "Frontend build not found"})
    return _react_index_response(
        request=request,
        metadata=seo.PageMetadata(
            title=f"Documentație admin | {seo.SITE_NAME}",
            description="Documentație internă pentru administratorii Călimara.",
            canonical_url=seo.main_url("/docs"),
            robots="noindex, nofollow",
        ),
    )


@app.get("/favicon.png", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
def serve_favicon():
    favicon_path = os.path.join(FRONTEND_DIST, "favicon.png")
    if not os.path.isfile(favicon_path):
        return JSONResponse(status_code=404, content={"detail": "Favicon not found"})
    return FileResponse(favicon_path, media_type="image/png")


if os.path.isdir(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="react-assets")

    @app.get("/{full_path:path}")
    def serve_react(full_path: str, request: Request, db=Depends(get_db)):
        """Catch-all: serve React index.html for client-side routing"""
        normalized_path = f"/{full_path.strip('/')}" if full_path else "/"
        if normalized_path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": "Ruta nu a fost găsită"})
        if _legacy_frontend_path(normalized_path):
            return _not_found_page()
        missing_author = _author_subdomain_not_found_response(request, db)
        if missing_author is not None:
            return missing_author
        return _react_index_response(request=request, db=db)
else:
    logger.warning(
        f"React build not found at {FRONTEND_DIST}. "
        "Run 'cd frontend && npm run build' to build the frontend."
    )
