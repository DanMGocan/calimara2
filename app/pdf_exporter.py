import html
import re
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import quote

import bleach
from weasyprint import HTML

from .utils import MAIN_DOMAIN


SITE_NAME = "călimara.ro"
PDF_MEDIA_TYPE = "application/pdf"

ALLOWED_CONTENT_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "blockquote",
    "ul",
    "ol",
    "li",
]

SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1>")
HTML_RE = re.compile(r"<[a-zA-Z][^>]*>")
WHITESPACE_RE = re.compile(r"\s+")
IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def pdf_response_headers(filename: str) -> dict[str, str]:
    safe = safe_pdf_filename(filename)
    return {
        "Content-Disposition": f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(safe)}",
        "Cache-Control": "private, max-age=60",
    }


def safe_pdf_filename(value: str) -> str:
    stem = value.rsplit(".", 1)[0] if value.endswith(".pdf") else value
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", stem).strip(".-_")
    return f"{stem or 'calimara-export'}.pdf"


def post_page_url(request: Any, username: str, slug: str) -> str:
    scheme, host_name, port = _request_host_parts(request)
    if host_name.startswith(f"{username}."):
        host = _join_host_port(host_name, port)
    elif host_name in {"localhost"} or IPV4_RE.match(host_name):
        host = _join_host_port(host_name, port)
    else:
        host = _join_host_port(f"{username}.{_root_host(host_name)}", port)
    return f"{scheme}://{host}/{quote(slug)}"


def collection_page_url(request: Any, slug: str) -> str:
    scheme, host_name, port = _request_host_parts(request)
    if host_name not in {"localhost"} and not IPV4_RE.match(host_name):
        host_name = _root_host(host_name)
    return f"{scheme}://{_join_host_port(host_name, port)}/colectii/{quote(slug)}"


def render_post_pdf(
    *,
    post: Any,
    author: Any,
    page_url: str,
    category_label: str = "",
) -> bytes:
    title = getattr(post, "title", "")
    author_name = getattr(author, "username", "anonim")
    created_at = getattr(post, "created_at", None)
    html_document = build_post_pdf_html(
        title=title,
        author=author_name,
        content=getattr(post, "content", ""),
        page_url=page_url,
        category_label=category_label,
        created_at=created_at,
    )
    return render_html_to_pdf(html_document)


def render_collection_pdf(
    *,
    collection: Any,
    owner: Any,
    entries: Iterable[Any],
    page_url: str,
    category_label_for_post,
) -> bytes:
    posts = []
    for entry in entries:
        post = getattr(entry, "post", None)
        if not post:
            continue
        author = getattr(post, "owner", None)
        posts.append(
            {
                "title": getattr(post, "title", ""),
                "author": getattr(author, "username", "anonim"),
                "content": getattr(post, "content", ""),
                "category_label": category_label_for_post(getattr(post, "category", None)),
                "created_at": getattr(post, "created_at", None),
            }
        )

    html_document = build_collection_pdf_html(
        title=getattr(collection, "title", ""),
        owner=getattr(owner, "username", "anonim"),
        description=getattr(collection, "description", "") or "",
        posts=posts,
        page_url=page_url,
    )
    return render_html_to_pdf(html_document)


def build_post_pdf_html(
    *,
    title: str,
    author: str,
    content: str,
    page_url: str,
    category_label: str = "",
    created_at: datetime | None = None,
) -> str:
    meta = _meta_line(category_label, created_at)
    return _document(
        page_url=page_url,
        body=f"""
        <main class="document">
          {_document_header(page_url)}
          <section class="hero">
            <div class="kicker">{_escape(category_label or "text")}</div>
            <h1>{_escape(title)}</h1>
            <p class="byline">de {_escape(author)}</p>
            {f'<p class="meta">{_escape(meta)}</p>' if meta else ''}
          </section>
          <article class="prose">
            {_content_html(content)}
          </article>
        </main>
        """,
    )


def build_collection_pdf_html(
    *,
    title: str,
    owner: str,
    description: str,
    posts: list[dict[str, Any]],
    page_url: str,
) -> str:
    if posts:
        post_sections = "\n".join(_collection_post_html(post) for post in posts)
    else:
        post_sections = '<p class="empty">Colecția nu are încă texte publice acceptate.</p>'

    return _document(
        page_url=page_url,
        body=f"""
        <main class="document collection-document">
          {_document_header(page_url)}
          <section class="hero">
            <div class="kicker">colecție</div>
            <h1>{_escape(title)}</h1>
            <p class="byline">de {_escape(owner)}</p>
            {f'<p class="description">{_escape(description)}</p>' if description else ''}
          </section>
          <section class="collection-items">
            {post_sections}
          </section>
        </main>
        """,
    )


def render_html_to_pdf(html_document: str) -> bytes:
    return HTML(string=html_document).write_pdf()


def _collection_post_html(post: dict[str, Any]) -> str:
    meta = _meta_line(post.get("category_label", ""), post.get("created_at"))
    return f"""
    <article class="collection-item">
      <header class="item-header">
        <div class="kicker">{_escape(post.get("category_label") or "text")}</div>
        <h2>{_escape(post.get("title") or "")}</h2>
        <p class="byline">de {_escape(post.get("author") or "anonim")}</p>
        {f'<p class="meta">{_escape(meta)}</p>' if meta else ''}
      </header>
      <div class="prose">
        {_content_html(post.get("content") or "")}
      </div>
    </article>
    """


def _document_header(page_url: str) -> str:
    return f"""
    <header class="export-header">
      <div class="site-name">{_escape(SITE_NAME)}</div>
      <div class="site-url">{_escape(page_url)}</div>
    </header>
    """


def _document(*, page_url: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ro">
<head>
  <meta charset="utf-8">
  <title>{_escape(SITE_NAME)} PDF export</title>
  <style>
    @page {{
      size: A4;
      margin: 20mm 19mm 22mm;
    }}

    html {{
      color: #261d18;
      font-family: "DejaVu Serif", Georgia, serif;
      font-size: 12.2pt;
      line-height: 1.58;
    }}

    body {{
      margin: 0;
      background: #fffdf8;
    }}

    body::before {{
      content: "";
      position: fixed;
      top: -8mm;
      right: -7mm;
      bottom: -9mm;
      left: -7mm;
      border: 1.2pt solid #c7aa71;
      outline: 0.5pt solid rgba(38, 29, 24, 0.24);
      outline-offset: 3mm;
    }}

    .document {{
      position: relative;
      z-index: 1;
    }}

    .export-header {{
      display: table;
      width: 100%;
      padding-bottom: 8mm;
      border-bottom: 0.7pt solid rgba(38, 29, 24, 0.25);
      font-family: "DejaVu Sans", Arial, sans-serif;
    }}

    .site-name,
    .site-url {{
      display: table-cell;
      vertical-align: top;
      font-size: 8.5pt;
      letter-spacing: 0.03em;
      color: #6d5b4a;
    }}

    .site-name {{
      width: 34%;
      font-weight: 700;
      text-transform: uppercase;
    }}

    .site-url {{
      text-align: right;
      word-break: break-all;
    }}

    .hero {{
      padding: 14mm 0 11mm;
      text-align: center;
    }}

    .kicker,
    .meta {{
      font-family: "DejaVu Sans", Arial, sans-serif;
      font-size: 8.2pt;
      color: #836b54;
    }}

    .kicker {{
      margin-bottom: 4mm;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 0;
      font-size: 31pt;
      font-weight: 400;
      line-height: 1.08;
      color: #231916;
    }}

    h2 {{
      margin: 0;
      font-size: 22pt;
      font-weight: 400;
      line-height: 1.12;
      color: #231916;
    }}

    .byline {{
      margin: 5mm 0 0;
      font-size: 13pt;
      font-style: italic;
      color: #604d42;
    }}

    .meta {{
      margin: 3mm 0 0;
    }}

    .description {{
      max-width: 135mm;
      margin: 7mm auto 0;
      font-family: "DejaVu Sans", Arial, sans-serif;
      font-size: 10.5pt;
      line-height: 1.55;
      color: #5f534d;
    }}

    .prose {{
      max-width: 142mm;
      margin: 0 auto;
      font-size: 12.5pt;
      line-height: 1.72;
    }}

    .prose p {{
      margin: 0 0 4.2mm;
    }}

    .prose blockquote {{
      margin: 6mm 0;
      padding-left: 6mm;
      border-left: 1.4pt solid #c7aa71;
      color: #51433b;
      font-style: italic;
    }}

    .prose ul,
    .prose ol {{
      margin: 0 0 5mm 8mm;
      padding: 0;
    }}

    .collection-item {{
      break-before: page;
    }}

    .collection-item:first-child {{
      break-before: auto;
    }}

    .item-header {{
      padding: 0 0 8mm;
      text-align: center;
    }}

    .empty {{
      max-width: 130mm;
      margin: 0 auto;
      text-align: center;
      color: #6d5b4a;
      font-style: italic;
    }}
  </style>
</head>
<body data-source="{_escape(page_url)}">
  {body}
</body>
</html>"""


def _content_html(value: str) -> str:
    raw = SCRIPT_STYLE_RE.sub("", value or "")
    if HTML_RE.search(raw):
        cleaned = bleach.clean(raw, tags=ALLOWED_CONTENT_TAGS, attributes={}, strip=True)
        return cleaned.strip() or '<p class="empty">Fără text.</p>'

    normalized = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return '<p class="empty">Fără text.</p>'

    blocks = re.split(r"\n\s*\n", normalized)
    paragraphs = []
    for block in blocks:
        lines = [_escape(line.strip()) for line in block.split("\n")]
        text = "<br>".join(line for line in lines if line)
        if text:
            paragraphs.append(f"<p>{text}</p>")
    return "\n".join(paragraphs) or '<p class="empty">Fără text.</p>'


def _meta_line(category_label: str, created_at: datetime | None) -> str:
    parts = []
    if category_label:
        parts.append(category_label)
    if created_at:
        parts.append(created_at.strftime("%d.%m.%Y"))
    return " · ".join(parts)


def _request_host_parts(request: Any) -> tuple[str, str, str]:
    scheme = getattr(getattr(request, "url", None), "scheme", "https") or "https"
    host = ""
    if hasattr(request, "headers"):
        host = request.headers.get("host", "")
    host = host or MAIN_DOMAIN

    host_name, separator, port = host.partition(":")
    return scheme, host_name.lower(), port if separator else ""


def _root_host(host_name: str) -> str:
    if host_name.startswith("www."):
        host_name = host_name[4:]
    parts = [part for part in host_name.split(".") if part]
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return host_name


def _join_host_port(host_name: str, port: str) -> str:
    return f"{host_name}:{port}" if port else host_name


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)
