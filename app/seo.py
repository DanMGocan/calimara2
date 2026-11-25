from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from . import models, profile_media, rich_text
from .categories import get_category_name
from .utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX, default_cover_seed, get_avatar_url, get_cover_url

SITE_NAME = "călimara.ro"
SITE_LANGUAGE = "ro"
DEFAULT_TITLE = "călimara.ro, platformă modernă de poezie și proză"
DEFAULT_DESCRIPTION = "Călimara este o platformă literară pentru poezie, proză scurtă, profiluri de autori, teatru colaborativ și discuții."
DEFAULT_IMAGE_PATH = "/favicon.png"
SITEMAP_LIMIT = 50_000

# Kept in sync with frontend/src/app/router.jsx (see tests/test_not_found_pages.py).
SUBDOMAIN_PRIVATE_PATHS = {"/panou", "/profil", "/scrie", "/mesaje", "/prieteni", "/utilizatori"}
MAIN_PRIVATE_EXACT_PATHS = {
    "/panou", "/profil", "/scrie", "/mesaje", "/prieteni", "/utilizatori", "/moderare", "/docs",
    "/cluburi", "/stafeta", "/stafeta/nou", "/magazin", "/inventar", "/playlisturi", "/invitatii",
    "/autentificare", "/autentificare/configurare", "/autentificare/raspuns",
}
MAIN_PRIVATE_SLUG_PREFIXES = ("/cluburi/", "/stafeta/", "/invitatie/")

STATIC_PUBLIC_PAGES = {
    "/": {
        "title": DEFAULT_TITLE,
        "description": DEFAULT_DESCRIPTION,
    },
    "/ce-este-calimara": {
        "title": f"Ce este Călimara | {SITE_NAME}",
        "description": "Călimara este un spațiu pentru publicarea și descoperirea textelor literare românești.",
    },
    "/confidentialitate": {
        "title": f"Confidențialitate | {SITE_NAME}",
        "description": "Politica de confidențialitate pentru conturi, conținut, emailuri, cookies și reclame pe Călimara.",
    },
    "/termeni": {
        "title": f"Termeni | {SITE_NAME}",
        "description": "Termenii de utilizare pentru publicare, moderare, conținut și conturi pe Călimara.",
    },
    "/premium": {
        "title": f"Premium | {SITE_NAME}",
        "description": "Planurile Premium Călimara pentru autori, ascultare audio, Super-apreciez și instrumente literare.",
    },
    "/discutii": {
        "title": f"Discuții literare | {SITE_NAME}",
        "description": "Forumuri pentru poezie, proză scurtă, anunțuri și conversații între autorii Călimara.",
    },
    "/teatru": {
        "title": f"Teatru colaborativ | {SITE_NAME}",
        "description": "Piese scrise pe rând, cu personaje, scene și autori care colaborează pe Călimara.",
    },
}


@dataclass
class SitemapEntry:
    loc: str
    lastmod: datetime | date | None = None
    changefreq: str | None = None
    priority: str | None = None


@dataclass
class PageMetadata:
    title: str = DEFAULT_TITLE
    description: str = DEFAULT_DESCRIPTION
    canonical_url: str = ""
    image_url: str = ""
    og_type: str = "website"
    robots: str = "index, follow"
    json_ld: list[dict] = field(default_factory=list)
    not_found: bool = False

    @property
    def noindex(self) -> bool:
        return "noindex" in self.robots.lower()


def _configured_origin() -> str:
    configured = (os.getenv("SEO_SITE_URL") or os.getenv("PUBLIC_BASE_URL") or "").strip()
    if configured:
        return configured.rstrip("/")
    if MAIN_DOMAIN.startswith(("http://", "https://")):
        return MAIN_DOMAIN.rstrip("/")
    scheme = os.getenv("PUBLIC_SCHEME", "https").strip() or "https"
    return f"{scheme}://{MAIN_DOMAIN}".rstrip("/")


def _subdomain_suffix() -> str:
    suffix = (SUBDOMAIN_SUFFIX or "").strip()
    if not suffix:
        return f".{MAIN_DOMAIN}".replace("..", ".")
    return suffix if suffix.startswith(".") else f".{suffix}"


def main_url(path: str = "/") -> str:
    return _join_url(_configured_origin(), path)


def author_url(username: str, path: str = "/") -> str:
    clean_username = str(username or "").strip().lower()
    origin = _configured_origin()
    if clean_username:
        if MAIN_DOMAIN.startswith(("http://", "https://")):
            scheme = origin.split("://", 1)[0]
        else:
            scheme = os.getenv("PUBLIC_SCHEME", "https").strip() or "https"
        origin = f"{scheme}://{clean_username}{_subdomain_suffix()}".rstrip("/")
    return _join_url(origin, path)


def _join_url(origin: str, path: str = "/") -> str:
    normalized_path = "/" + str(path or "/").strip("/")
    if normalized_path == "//":
        normalized_path = "/"
    return f"{origin.rstrip()}{quote(normalized_path, safe='/:@._~%-')}"


def _absolute_url(value: str | None) -> str:
    if not value:
        return main_url(DEFAULT_IMAGE_PATH)
    candidate = str(value)
    if candidate.startswith("//"):
        return f"https:{candidate}"
    if candidate.startswith(("http://", "https://")):
        return candidate
    return main_url(candidate if candidate.startswith("/") else f"/{candidate}")


def _excerpt(value: str | None, *, fallback: str = DEFAULT_DESCRIPTION, limit: int = 165) -> str:
    text = rich_text.rich_text_to_plain_text(value)
    if not text:
        text = fallback
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" .,;:") + "…"


def _profile_image_url(user: models.User, *, cover: bool = False) -> str:
    if cover:
        if getattr(user, "is_premium", False) and getattr(user, "cover_photo_storage_key", None):
            return _absolute_url(profile_media.public_media_url(user.username, "coperta"))
        return get_cover_url(getattr(user, "cover_seed", None) or default_cover_seed(user), size=1600)
    if getattr(user, "is_premium", False) and getattr(user, "profile_photo_storage_key", None):
        return _absolute_url(profile_media.public_media_url(user.username, "profil"))
    return get_avatar_url(user, size=512)


def _base_json_ld(canonical_url: str) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": main_url("/"),
        "inLanguage": SITE_LANGUAGE,
        "mainEntityOfPage": canonical_url,
    }


def _static_page_metadata(path: str) -> PageMetadata:
    config = STATIC_PUBLIC_PAGES[path]
    canonical = main_url(path)
    return PageMetadata(
        title=config["title"],
        description=config["description"],
        canonical_url=canonical,
        image_url=main_url(DEFAULT_IMAGE_PATH),
        og_type="website",
        json_ld=[_base_json_ld(canonical)],
    )


def _noindex_metadata(path: str, *, title: str = "Pagină privată", not_found: bool = False) -> PageMetadata:
    canonical = main_url(path or "/")
    return PageMetadata(
        not_found=not_found,
        title=f"{title} | {SITE_NAME}",
        description="Această pagină nu este destinată indexării publice.",
        canonical_url=canonical,
        image_url=main_url(DEFAULT_IMAGE_PATH),
        robots="noindex, nofollow",
        json_ld=[],
    )


def _profile_metadata(user: models.User, *, path: str = "/") -> PageMetadata:
    canonical = author_url(user.username, path)
    handle = f"@{user.username}"
    subtitle = _excerpt(
        getattr(user, "subtitle", None),
        fallback=f"Profilul public al autorului {handle} pe Călimara.",
    )
    image = _profile_image_url(user, cover=True)
    title = f"{handle} | {SITE_NAME}" if path == "/" else f"Toate operele lui {handle} | {SITE_NAME}"
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "ProfilePage",
            "url": canonical,
            "name": title.replace(f" | {SITE_NAME}", ""),
            "description": subtitle,
            "inLanguage": SITE_LANGUAGE,
            "mainEntity": {
                "@type": "Person",
                "name": user.username,
                "alternateName": handle,
                "url": author_url(user.username, "/"),
                "image": _profile_image_url(user),
            },
        }
    ]
    return PageMetadata(
        title=title,
        description=subtitle,
        canonical_url=canonical,
        image_url=image,
        og_type="profile",
        json_ld=json_ld,
    )


def _post_metadata(post: models.Post, user: models.User) -> PageMetadata:
    canonical = author_url(user.username, f"/{post.slug}")
    category = get_category_name(post.category) if post.category else "Text"
    description = _excerpt(
        post.content,
        fallback=f"{category} de @{user.username} pe Călimara.",
    )
    title = f"{post.title} de @{user.username} | {SITE_NAME}"
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "CreativeWork",
            "name": post.title,
            "headline": post.title,
            "text": _excerpt(post.content, fallback="", limit=600),
            "url": canonical,
            "inLanguage": SITE_LANGUAGE,
            "genre": category,
            "datePublished": _iso_datetime(post.created_at),
            "dateModified": _iso_datetime(post.updated_at),
            "author": {
                "@type": "Person",
                "name": user.username,
                "url": author_url(user.username, "/"),
            },
            "interactionStatistic": [
                {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/ViewAction",
                    "userInteractionCount": int(getattr(post, "view_count", 0) or 0),
                },
                {
                    "@type": "InteractionCounter",
                    "interactionType": "https://schema.org/LikeAction",
                    "userInteractionCount": int(getattr(post, "likes_count", 0) or 0),
                },
            ],
        }
    ]
    return PageMetadata(
        title=title,
        description=description,
        canonical_url=canonical,
        image_url=_profile_image_url(user, cover=True),
        og_type="article",
        json_ld=json_ld,
    )


def _series_metadata(series: models.Series, post_count: int) -> PageMetadata:
    canonical = main_url(f"/serii/{series.slug}")
    owner = series.owner
    owner_label = f" de @{owner.username}" if owner else ""
    description = _excerpt(
        series.description,
        fallback=f"Serie literară{owner_label} cu {post_count} texte publice pe Călimara.",
    )
    title = f"{series.title}{owner_label} | {SITE_NAME}"
    return PageMetadata(
        title=title,
        description=description,
        canonical_url=canonical,
        image_url=_profile_image_url(owner, cover=True) if owner else main_url(DEFAULT_IMAGE_PATH),
        og_type="book",
        json_ld=[
            {
                "@context": "https://schema.org",
                "@type": "CreativeWorkSeries",
                "name": series.title,
                "description": description,
                "url": canonical,
                "inLanguage": SITE_LANGUAGE,
                "author": {
                    "@type": "Person",
                    "name": owner.username,
                    "url": author_url(owner.username, "/"),
                } if owner else None,
                "numberOfItems": post_count,
            }
        ],
    )


def _theatre_metadata(play: models.TheatrePlay) -> PageMetadata:
    canonical = main_url(f"/teatru/{play.slug}")
    creator = play.creator
    description = _excerpt(
        play.description,
        fallback=f"Piesă de teatru colaborativ pe Călimara{f' creată de @{creator.username}' if creator else ''}.",
    )
    return PageMetadata(
        title=f"{play.title} | Teatru colaborativ | {SITE_NAME}",
        description=description,
        canonical_url=canonical,
        image_url=_profile_image_url(creator, cover=True) if creator else main_url(DEFAULT_IMAGE_PATH),
        og_type="article",
        json_ld=[
            {
                "@context": "https://schema.org",
                "@type": "CreativeWork",
                "name": play.title,
                "description": description,
                "url": canonical,
                "inLanguage": SITE_LANGUAGE,
                "dateCreated": _iso_datetime(play.created_at),
                "dateModified": _iso_datetime(play.updated_at),
                "creator": {
                    "@type": "Person",
                    "name": creator.username,
                    "url": author_url(creator.username, "/"),
                } if creator else None,
            }
        ],
    )


def _forum_thread_metadata(thread: models.ForumThread) -> PageMetadata:
    canonical = main_url(f"/discutii/{thread.slug}")
    author = thread.author
    description = _excerpt(
        thread.content,
        fallback=f"Discuție literară pe Călimara{f' pornită de @{author.username}' if author else ''}.",
    )
    return PageMetadata(
        title=f"{thread.title} | Discuții | {SITE_NAME}",
        description=description,
        canonical_url=canonical,
        image_url=_profile_image_url(author) if author else main_url(DEFAULT_IMAGE_PATH),
        og_type="article",
        json_ld=[
            {
                "@context": "https://schema.org",
                "@type": "DiscussionForumPosting",
                "headline": thread.title,
                "text": _excerpt(thread.content, fallback="", limit=600),
                "url": canonical,
                "inLanguage": SITE_LANGUAGE,
                "datePublished": _iso_datetime(thread.created_at),
                "dateModified": _iso_datetime(thread.updated_at),
                "author": {
                    "@type": "Person",
                    "name": author.username,
                    "url": author_url(author.username, "/"),
                } if author else None,
            }
        ],
    )


def build_page_metadata(db: Session, request: Request) -> PageMetadata:
    path = "/" + request.url.path.strip("/")
    if path == "//":
        path = "/"
    username = getattr(getattr(request, "state", None), "username", None)

    if username:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            return _noindex_metadata(path, title="Profil inexistent", not_found=True)
        if path == "/":
            return _profile_metadata(user)
        if path == "/toate-operele":
            return _profile_metadata(user, path="/toate-operele")
        if path in {"/urmaritori", "/urmariti", "/inventar"}:
            return _noindex_metadata(path, title="Pagină de profil")
        if path in SUBDOMAIN_PRIVATE_PATHS:
            return _noindex_metadata(path)
        slug = path.strip("/")
        post = (
            db.query(models.Post)
            .filter(
                models.Post.slug == slug,
                models.Post.user_id == user.id,
                models.Post.moderation_status == "approved",
            )
            .first()
        )
        if post:
            return _post_metadata(post, user)
        # A pending/rejected post still exists for its author; only a missing slug is a 404.
        exists = db.query(models.Post.id).filter(models.Post.slug == slug, models.Post.user_id == user.id).first()
        return _noindex_metadata(path, title="Text inexistent", not_found=exists is None)

    if path in STATIC_PUBLIC_PAGES:
        return _static_page_metadata(path)

    if path.startswith("/serii/"):
        slug = path.split("/", 2)[2]
        series = db.query(models.Series).options(joinedload(models.Series.owner)).filter(models.Series.slug == slug).first()
        if not series:
            return _noindex_metadata(path, title="Serie inexistentă", not_found=True)
        post_count = _approved_series_post_count(db, series.id)
        if post_count <= 0:
            return _noindex_metadata(path, title="Serie fără texte publice")
        return _series_metadata(series, post_count)

    if path.startswith("/teatru/") and path != "/teatru/nou":
        slug = path.split("/", 2)[2]
        play = db.query(models.TheatrePlay).options(joinedload(models.TheatrePlay.creator)).filter(models.TheatrePlay.slug == slug).first()
        if play:
            return _theatre_metadata(play)
        return _noindex_metadata(path, title="Piesă inexistentă", not_found=True)

    if path.startswith("/discutii/") and path != "/discutii/nou":
        slug = path.split("/", 2)[2]
        thread = (
            db.query(models.ForumThread)
            .options(joinedload(models.ForumThread.author))
            .filter(
                models.ForumThread.slug == slug,
                models.ForumThread.moderation_status == "approved",
            )
            .first()
        )
        if thread:
            return _forum_thread_metadata(thread)
        exists = db.query(models.ForumThread.id).filter(models.ForumThread.slug == slug).first()
        return _noindex_metadata(path, title="Discuție inexistentă", not_found=exists is None)

    if path == "/teatru/nou" or path == "/discutii/nou" or _is_known_private_path(path):
        return _noindex_metadata(path)

    return _noindex_metadata(path, title="Pagină negăsită", not_found=True)


def _is_known_private_path(path: str) -> bool:
    """Mirror of frontend/src/app/router.jsx for main-domain pages that are not indexed."""
    if path in MAIN_PRIVATE_EXACT_PATHS:
        return True
    return any(path.startswith(prefix) and len(path) > len(prefix) for prefix in MAIN_PRIVATE_SLUG_PREFIXES)


def _approved_series_post_count(db: Session, series_id: int) -> int:
    return (
        db.query(func.count(models.SeriesPost.id))
        .join(models.Post, models.Post.id == models.SeriesPost.post_id)
        .filter(
            models.SeriesPost.series_id == series_id,
            models.Post.moderation_status == "approved",
        )
        .scalar()
        or 0
    )


def build_sitemap_entries(db: Session, *, limit: int = SITEMAP_LIMIT) -> list[SitemapEntry]:
    entries: list[SitemapEntry] = [
        SitemapEntry(main_url("/"), priority="1.0", changefreq="daily"),
        SitemapEntry(main_url("/ce-este-calimara"), priority="0.7", changefreq="monthly"),
        SitemapEntry(main_url("/premium"), priority="0.6", changefreq="monthly"),
        SitemapEntry(main_url("/discutii"), priority="0.7", changefreq="daily"),
        SitemapEntry(main_url("/teatru"), priority="0.7", changefreq="daily"),
        SitemapEntry(main_url("/confidentialitate"), priority="0.3", changefreq="yearly"),
        SitemapEntry(main_url("/termeni"), priority="0.3", changefreq="yearly"),
    ]

    remaining = max(0, limit - len(entries))
    if remaining <= 0:
        return entries[:limit]

    profile_lastmod = (
        db.query(
            models.Post.user_id.label("user_id"),
            func.max(models.Post.updated_at).label("lastmod"),
        )
        .filter(models.Post.moderation_status == "approved")
        .group_by(models.Post.user_id)
        .subquery()
    )
    profile_rows = (
        db.query(models.User, profile_lastmod.c.lastmod)
        .join(profile_lastmod, profile_lastmod.c.user_id == models.User.id)
        .order_by(profile_lastmod.c.lastmod.desc())
        .limit(remaining)
        .all()
    )
    for user, lastmod in profile_rows:
        entries.append(SitemapEntry(author_url(user.username, "/"), lastmod=lastmod, priority="0.8", changefreq="weekly"))
        if len(entries) >= limit:
            return entries
        entries.append(SitemapEntry(author_url(user.username, "/toate-operele"), lastmod=lastmod, priority="0.6", changefreq="weekly"))
        if len(entries) >= limit:
            return entries

    post_rows = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(models.Post.moderation_status == "approved")
        .order_by(models.Post.updated_at.desc(), models.Post.id.desc())
        .limit(max(0, limit - len(entries)))
        .all()
    )
    for post in post_rows:
        if post.owner:
            entries.append(SitemapEntry(author_url(post.owner.username, f"/{post.slug}"), lastmod=post.updated_at, priority="0.9", changefreq="weekly"))
        if len(entries) >= limit:
            return entries

    series_rows = (
        db.query(models.Series, func.max(models.Post.updated_at).label("lastmod"))
        .join(models.SeriesPost, models.SeriesPost.series_id == models.Series.id)
        .join(models.Post, models.Post.id == models.SeriesPost.post_id)
        .filter(models.Post.moderation_status == "approved")
        .group_by(models.Series.id)
        .order_by(func.max(models.Post.updated_at).desc())
        .limit(max(0, limit - len(entries)))
        .all()
    )
    for series, lastmod in series_rows:
        entries.append(SitemapEntry(main_url(f"/serii/{series.slug}"), lastmod=lastmod, priority="0.7", changefreq="weekly"))
        if len(entries) >= limit:
            return entries

    theatre_rows = (
        db.query(models.TheatrePlay)
        .order_by(models.TheatrePlay.updated_at.desc(), models.TheatrePlay.id.desc())
        .limit(max(0, limit - len(entries)))
        .all()
    )
    for play in theatre_rows:
        entries.append(SitemapEntry(main_url(f"/teatru/{play.slug}"), lastmod=play.updated_at, priority="0.6", changefreq="weekly"))
        if len(entries) >= limit:
            return entries

    forum_rows = (
        db.query(models.ForumThread)
        .filter(models.ForumThread.moderation_status == "approved")
        .order_by(models.ForumThread.updated_at.desc(), models.ForumThread.id.desc())
        .limit(max(0, limit - len(entries)))
        .all()
    )
    for thread in forum_rows:
        entries.append(SitemapEntry(main_url(f"/discutii/{thread.slug}"), lastmod=thread.updated_at, priority="0.5", changefreq="weekly"))
        if len(entries) >= limit:
            return entries

    return entries


def build_sitemap_xml(db: Session) -> str:
    items = "\n".join(_sitemap_entry_xml(entry) for entry in build_sitemap_entries(db))
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n'


def _sitemap_entry_xml(entry: SitemapEntry) -> str:
    parts = [f"  <loc>{xml_escape(entry.loc)}</loc>"]
    if entry.lastmod:
        parts.append(f"  <lastmod>{xml_escape(_iso_date(entry.lastmod))}</lastmod>")
    if entry.changefreq:
        parts.append(f"  <changefreq>{xml_escape(entry.changefreq)}</changefreq>")
    if entry.priority:
        parts.append(f"  <priority>{xml_escape(entry.priority)}</priority>")
    return "  <url>\n" + "\n".join(parts) + "\n  </url>"


def build_robots_txt() -> str:
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/admin/",
        "Disallow: /api/moderare/",
        "Disallow: /api/notificari",
        "Disallow: /api/mesaje",
        "Disallow: /api/portabilitate",
        "Disallow: /api/deconectare",
        f"Sitemap: {main_url('/sitemap.xml')}",
        "",
    ]
    return "\n".join(lines)


def render_index_html(index_html: str, metadata: PageMetadata) -> str:
    cleaned = _strip_existing_seo(index_html)
    cleaned = _replace_title(cleaned, metadata.title)
    tags = "\n".join(_metadata_tags(metadata))
    if "</head>" in cleaned:
        return cleaned.replace("</head>", f"    {tags}\n  </head>", 1)
    return f"{cleaned}\n{tags}\n"


def _strip_existing_seo(index_html: str) -> str:
    without_scripts = re.sub(
        r"\s*<script\b(?=[^>]*\bdata-seo=)[^>]*>.*?</script>",
        "",
        index_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(
        r"\s*<(?:meta|link)\b(?=[^>]*\bdata-seo=)[^>]*>",
        "",
        without_scripts,
        flags=re.IGNORECASE,
    )


def _replace_title(index_html: str, title: str) -> str:
    title_tag = f"<title>{html.escape(title)}</title>"
    if re.search(r"<title\b[^>]*>.*?</title>", index_html, flags=re.IGNORECASE | re.DOTALL):
        return re.sub(
            r"<title\b[^>]*>.*?</title>",
            title_tag,
            index_html,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return index_html.replace("</head>", f"    {title_tag}\n  </head>", 1)


def _metadata_tags(metadata: PageMetadata) -> Iterable[str]:
    image = _absolute_url(metadata.image_url)
    canonical = metadata.canonical_url or main_url("/")
    yield _meta_name("description", metadata.description)
    yield _meta_name("robots", metadata.robots)
    yield f'<link rel="canonical" href="{html.escape(canonical, quote=True)}" data-seo="canonical" />'
    yield _meta_property("og:site_name", SITE_NAME)
    yield _meta_property("og:locale", "ro_RO")
    yield _meta_property("og:type", metadata.og_type)
    yield _meta_property("og:title", metadata.title)
    yield _meta_property("og:description", metadata.description)
    yield _meta_property("og:url", canonical)
    yield _meta_property("og:image", image)
    yield _meta_name("twitter:card", "summary_large_image")
    yield _meta_name("twitter:title", metadata.title)
    yield _meta_name("twitter:description", metadata.description)
    yield _meta_name("twitter:image", image)
    for index, payload in enumerate(_clean_json_ld(metadata.json_ld)):
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        yield f'<script type="application/ld+json" data-seo="jsonld-{index}">{raw}</script>'


def _meta_name(name: str, content: str) -> str:
    return f'<meta name="{html.escape(name, quote=True)}" content="{html.escape(str(content), quote=True)}" data-seo="{html.escape(name, quote=True)}" />'


def _meta_property(prop: str, content: str) -> str:
    return f'<meta property="{html.escape(prop, quote=True)}" content="{html.escape(str(content), quote=True)}" data-seo="{html.escape(prop, quote=True)}" />'


def _clean_json_ld(payloads: list[dict]) -> list[dict]:
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if item is not None}
        if isinstance(value, list):
            return [clean(item) for item in value if item is not None]
        return value

    return [clean(payload) for payload in payloads if payload]


def _iso_datetime(value) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    return str(value)


def _iso_date(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
