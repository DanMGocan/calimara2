import html
import logging
import os
import re
import socket
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from uuid import uuid4

import httpx
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from . import models, rich_text
from .utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX
from .week_util import utcnow_naive

logger = logging.getLogger(__name__)

EMAIL_TYPE_COMMENT = "comment"
EMAIL_TYPE_MENTION = "mention"
EMAIL_TYPE_ANALYTICS = "analytics"
EMAIL_TYPE_ADMIN = "admin"
EMAIL_STATUSES_TO_CLAIM = ("queued",)
UNSUBSCRIBE_PREFS = {
    EMAIL_TYPE_COMMENT: "email_comment_notifications",
    EMAIL_TYPE_MENTION: "email_mention_notifications",
    EMAIL_TYPE_ANALYTICS: "email_analytics_digest",
    EMAIL_TYPE_ADMIN: "email_admin_announcements",
}


def emails_enabled() -> bool:
    return os.getenv("EMAILS_ENABLED", "False").lower() in {"true", "1", "yes", "on"}


def sender_email() -> str:
    return os.getenv("BREVO_SENDER_EMAIL", "contact@calimara.ro").strip()


def sender_name() -> str:
    return os.getenv("BREVO_SENDER_NAME", "Călimara").strip()


def public_scheme() -> str:
    configured = os.getenv("PUBLIC_SCHEME", "").strip()
    if configured:
        return configured
    https_only = os.getenv("HTTPS_ONLY", "True").lower() in {"true", "1", "yes", "on"}
    return "https" if https_only else "http"


def main_url(path: str = "") -> str:
    normalized = path if path.startswith("/") else f"/{path}" if path else ""
    return f"{public_scheme()}://{MAIN_DOMAIN}{normalized}"


def author_url(username: str, path: str = "") -> str:
    suffix = SUBDOMAIN_SUFFIX if SUBDOMAIN_SUFFIX.startswith(".") else f".{SUBDOMAIN_SUFFIX}"
    normalized = path if path.startswith("/") else f"/{path}" if path else ""
    return f"{public_scheme()}://{username}{suffix}{normalized}"


def worker_id() -> str:
    return f"{socket.gethostname()}-{uuid4().hex[:8]}"


def _serializer() -> URLSafeSerializer:
    secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("EMAIL_UNSUBSCRIBE_SECRET")
    if not secret:
        raise RuntimeError("SESSION_SECRET_KEY is required for email unsubscribe tokens.")
    return URLSafeSerializer(secret, salt="calimara-email-unsubscribe-v1")


def unsubscribe_token(user_id: int, email_type: str) -> str:
    if email_type not in UNSUBSCRIBE_PREFS:
        raise ValueError("Invalid unsubscribe type")
    return _serializer().dumps({"user_id": user_id, "type": email_type})


def unsubscribe_url(user_id: int, email_type: str) -> str:
    return main_url(f"/api/email/dezabonare?token={unsubscribe_token(user_id, email_type)}&type={email_type}")


def apply_unsubscribe_token(db: Session, token: str, requested_type: Optional[str] = None) -> tuple[models.User, str]:
    try:
        payload = _serializer().loads(token)
    except BadSignature:
        raise ValueError("invalid_token")
    user_id = int(payload.get("user_id") or 0)
    email_type = str(payload.get("type") or "")
    if requested_type and requested_type != email_type:
        raise ValueError("invalid_token")
    pref = UNSUBSCRIBE_PREFS.get(email_type)
    if not user_id or not pref:
        raise ValueError("invalid_token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise ValueError("user_not_found")
    setattr(user, pref, False)
    db.commit()
    db.refresh(user)
    return user, email_type


def _strip_html_to_text(value: str) -> str:
    return rich_text.rich_text_to_plain_text(value)


def normalize_email_html(value: str) -> str:
    cleaned = rich_text.SCRIPT_STYLE_RE.sub("", str(value or "")).strip()
    return cleaned


def _email_page(title: str, body: str) -> str:
    escaped_title = html.escape(title)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escaped_title}</title>
  </head>
  <body style="margin:0;padding:0;background:#f7f3ea;color:#1f1d1b;font-family:Georgia,'Times New Roman',serif;">
    <div style="max-width:720px;margin:0 auto;padding:28px 18px;">
      <div style="font-family:Arial,sans-serif;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#7a7168;">călimara.ro</div>
      <h1 style="font-weight:500;font-size:28px;line-height:1.15;margin:12px 0 18px;">{escaped_title}</h1>
      <div style="font-size:16px;line-height:1.58;">{body}</div>
    </div>
  </body>
</html>"""


def _button(label: str, href: str) -> str:
    return (
        f'<p style="margin:22px 0 0;"><a href="{html.escape(href, quote=True)}" '
        'style="display:inline-block;padding:10px 14px;border:1px solid #1f1d1b;'
        'border-radius:8px;color:#1f1d1b;text-decoration:none;font-family:Arial,sans-serif;'
        f'font-size:14px;">{html.escape(label)}</a></p>'
    )


def _footer(user: models.User, email_type: str) -> str:
    if email_type not in UNSUBSCRIBE_PREFS:
        return ""
    url = unsubscribe_url(user.id, email_type)
    return (
        '<hr style="border:0;border-top:1px solid rgba(31,29,27,.18);margin:28px 0 14px;">'
        '<p style="font-family:Arial,sans-serif;font-size:12px;line-height:1.45;color:#7a7168;">'
        f'Poți opri aceste emailuri din profil sau direct aici: '
        f'<a href="{html.escape(url, quote=True)}" style="color:#1f1d1b;">dezabonare</a>.'
        "</p>"
    )


def _with_footer(user: models.User, email_type: str, body: str) -> str:
    return f"{body}{_footer(user, email_type)}"


def queue_email(
    db: Session,
    *,
    recipient_email: str,
    recipient_name: Optional[str],
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    email_type: str,
    recipient_user_id: Optional[int] = None,
    campaign_id: Optional[int] = None,
    extra_data: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
    commit: bool = True,
) -> Optional[models.EmailOutbox]:
    email = (recipient_email or "").strip()
    if not email:
        return None
    if dedupe_key:
        existing = db.query(models.EmailOutbox).filter(models.EmailOutbox.dedupe_key == dedupe_key).first()
        if existing:
            return existing
    cleaned_html = normalize_email_html(html_content)
    plain_text = (text_content or _strip_html_to_text(cleaned_html)).strip()
    row = models.EmailOutbox(
        campaign_id=campaign_id,
        recipient_user_id=recipient_user_id,
        recipient_email=email[:255],
        recipient_name=(recipient_name or "")[:255] or None,
        email_type=email_type,
        subject=subject[:255],
        html_content=cleaned_html,
        text_content=plain_text,
        extra_data=extra_data or {},
        dedupe_key=dedupe_key,
        status="queued",
        run_after=utcnow_naive(),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def _send_with_brevo(email: models.EmailOutbox) -> str:
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BREVO_API_KEY is not configured.")
    payload = {
        "sender": {"email": sender_email(), "name": sender_name()},
        "to": [{"email": email.recipient_email, "name": email.recipient_name or email.recipient_email}],
        "subject": email.subject,
        "htmlContent": email.html_content,
        "textContent": email.text_content,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Brevo send failed ({response.status_code}): {response.text[:1000]}")
    try:
        data = response.json()
    except ValueError:
        data = {}
    return str(data.get("messageId") or "")


def claim_due_emails(db: Session, *, limit: int = 20, worker: Optional[str] = None) -> list[models.EmailOutbox]:
    now = utcnow_naive()
    query = (
        db.query(models.EmailOutbox)
        .filter(
            models.EmailOutbox.status.in_(EMAIL_STATUSES_TO_CLAIM),
            models.EmailOutbox.run_after <= now,
            models.EmailOutbox.attempts < models.EmailOutbox.max_attempts,
        )
        .order_by(models.EmailOutbox.run_after.asc(), models.EmailOutbox.id.asc())
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    rows = query.limit(max(1, limit)).all()
    for row in rows:
        row.status = "sending"
        row.locked_at = now
        row.locked_by = worker or worker_id()
        row.attempts = int(row.attempts or 0) + 1
        row.error_message = None
    if rows:
        db.commit()
        for row in rows:
            db.refresh(row)
    return rows


def _retry_delay_seconds(email: models.EmailOutbox) -> int:
    attempts = int(email.attempts or 1)
    return min(1800, 30 * (2 ** max(0, attempts - 1)))


def complete_email(db: Session, email: models.EmailOutbox, message_id: str) -> models.EmailOutbox:
    email.status = "sent"
    email.provider_message_id = message_id or None
    email.sent_at = utcnow_naive()
    email.locked_at = None
    email.locked_by = None
    email.error_message = None
    db.commit()
    db.refresh(email)
    return email


def fail_email(db: Session, email: models.EmailOutbox, error_message: str, *, retry: bool = True) -> models.EmailOutbox:
    message = (error_message or "Email send failed")[:2000]
    if retry and int(email.attempts or 0) < int(email.max_attempts or 1):
        email.status = "queued"
        email.run_after = utcnow_naive() + timedelta(seconds=_retry_delay_seconds(email))
    else:
        email.status = "failed"
    email.locked_at = None
    email.locked_by = None
    email.error_message = message
    db.commit()
    db.refresh(email)
    return email


def process_email_outbox(db: Session, *, limit: int = 20, worker: Optional[str] = None) -> int:
    rows = claim_due_emails(db, limit=limit, worker=worker)
    for row in rows:
        if not emails_enabled():
            row.status = "skipped"
            row.locked_at = None
            row.locked_by = None
            row.error_message = "EMAILS_ENABLED is false"
            db.commit()
            continue
        try:
            message_id = _send_with_brevo(row)
            complete_email(db, row, message_id)
        except Exception as exc:
            logger.exception("Email outbox row %s failed", row.id)
            row_id = row.id
            try:
                db.rollback()
            except Exception:
                logger.exception("Rollback failed after email send error")
            row = db.query(models.EmailOutbox).filter(models.EmailOutbox.id == row_id).first()
            if row:
                fail_email(db, row, str(exc), retry=True)
    return len(rows)


def _comment_author_name(comment: models.Comment) -> str:
    if comment.commenter:
        return comment.commenter.username
    return comment.author_name or "Un cititor"


def queue_comment_approved_email(db: Session, comment: models.Comment) -> Optional[models.EmailOutbox]:
    if getattr(comment, "is_robot", False):
        return None
    post = comment.post or db.query(models.Post).filter(models.Post.id == comment.post_id).first()
    if not post:
        return None
    owner = post.owner or db.query(models.User).filter(models.User.id == post.user_id).first()
    if not owner or not owner.email_comment_notifications or owner.is_suspended:
        return None
    if comment.user_id and comment.user_id == owner.id:
        return None
    link = author_url(owner.username, f"/{post.slug}#comment-{comment.id}")
    author = _comment_author_name(comment)
    excerpt = html.escape(_strip_html_to_text(comment.content)[:500])
    body = (
        f"<p>{html.escape(author)} a comentat la „{html.escape(post.title)}”.</p>"
        f'<blockquote style="border-left:3px solid #d2c7b8;margin:14px 0;padding:8px 0 8px 14px;color:#4d4740;">{excerpt}</blockquote>'
        f"{_button('Vezi comentariul', link)}"
    )
    html_content = _email_page(
        "Comentariu nou",
        _with_footer(owner, EMAIL_TYPE_COMMENT, body),
    )
    text = (
        f"{author} a comentat la „{post.title}”.\n\n"
        f"{_strip_html_to_text(comment.content)[:500]}\n\n{link}\n\n"
        f"Dezabonare: {unsubscribe_url(owner.id, EMAIL_TYPE_COMMENT)}"
    )
    return queue_email(
        db,
        recipient_user_id=owner.id,
        recipient_email=owner.email,
        recipient_name=owner.username,
        subject=f"Comentariu nou la „{post.title}”",
        html_content=html_content,
        text_content=text,
        email_type=EMAIL_TYPE_COMMENT,
        extra_data={"comment_id": comment.id, "post_id": post.id},
        dedupe_key=f"comment-owner:{comment.id}:{owner.id}",
    )


def queue_mention_email(
    db: Session,
    *,
    target: models.User,
    actor: models.User,
    source_type: str,
    source_id: int,
    source_title: Optional[str],
    link: Optional[str],
) -> Optional[models.EmailOutbox]:
    if not target.email_mention_notifications or target.is_suspended:
        return None
    absolute_link = link or main_url("/")
    if absolute_link.startswith("//"):
        absolute_link = f"{public_scheme()}:{absolute_link}"
    elif absolute_link.startswith("/"):
        absolute_link = main_url(absolute_link)
    title = f"{actor.username} te-a menționat"
    body = (
        f"<p>{html.escape(actor.username)} te-a menționat pe călimara.ro.</p>"
        f"<p>{html.escape(source_title or 'Ai fost menționat într-o conversație.')}</p>"
        f"{_button('Vezi mențiunea', absolute_link)}"
    )
    html_content = _email_page(title, _with_footer(target, EMAIL_TYPE_MENTION, body))
    text = (
        f"{actor.username} te-a menționat pe călimara.ro.\n"
        f"{source_title or 'Ai fost menționat într-o conversație.'}\n\n{absolute_link}\n\n"
        f"Dezabonare: {unsubscribe_url(target.id, EMAIL_TYPE_MENTION)}"
    )
    return queue_email(
        db,
        recipient_user_id=target.id,
        recipient_email=target.email,
        recipient_name=target.username,
        subject=title,
        html_content=html_content,
        text_content=text,
        email_type=EMAIL_TYPE_MENTION,
        extra_data={"source_type": source_type, "source_id": source_id, "actor_id": actor.id},
        dedupe_key=f"mention:{source_type}:{source_id}:{target.id}",
    )


def _range_start(value: date) -> datetime:
    return datetime.combine(value, datetime.min.time())


def _range_end(value: date) -> datetime:
    return datetime.combine(value + timedelta(days=1), datetime.min.time())


def _metric_map(rows) -> dict[int, int]:
    return {int(key): int(value or 0) for key, value in rows if key is not None}


def _real_view_filters():
    return and_(models.PageView.is_bot == False, models.PageView.is_duplicate == False)


def _post_view_counts(db: Session, post_ids: list[int], start: Optional[date] = None, end: Optional[date] = None) -> dict[int, int]:
    if not post_ids:
        return {}
    filters = [
        models.PageView.content_type == "post",
        models.PageView.content_id.in_(post_ids),
        _real_view_filters(),
    ]
    if start:
        filters.append(models.PageView.created_at >= _range_start(start))
    if end:
        filters.append(models.PageView.created_at < _range_end(end))
    rows = (
        db.query(models.PageView.content_id, func.count(models.PageView.id))
        .filter(*filters)
        .group_by(models.PageView.content_id)
        .all()
    )
    return _metric_map(rows)


def _post_listen_seconds(db: Session, post_ids: list[int], start: date, end: date) -> dict[int, int]:
    if not post_ids:
        return {}
    rows = (
        db.query(models.AudioListenEvent.post_id, func.coalesce(func.sum(models.AudioListenEvent.seconds), 0))
        .filter(
            models.AudioListenEvent.post_id.in_(post_ids),
            models.AudioListenEvent.created_at >= _range_start(start),
            models.AudioListenEvent.created_at < _range_end(end),
        )
        .group_by(models.AudioListenEvent.post_id)
        .all()
    )
    return _metric_map(rows)


def _post_counts(db: Session, model, post_ids: list[int], approved_only: bool = False) -> dict[int, int]:
    if not post_ids:
        return {}
    filters = [model.post_id.in_(post_ids)]
    if approved_only:
        filters.append(model.approved == True)
    rows = db.query(model.post_id, func.count(model.id)).filter(*filters).group_by(model.post_id).all()
    return _metric_map(rows)


def _format_seconds(seconds: int) -> str:
    seconds = int(seconds or 0)
    if seconds < 60:
        return f"{seconds}s"
    minutes, remaining = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _analytics_rows(db: Session, user: models.User, start: date, end: date) -> list[dict]:
    posts = (
        db.query(models.Post)
        .filter(models.Post.user_id == user.id, models.Post.moderation_status == "approved")
        .order_by(models.Post.created_at.desc(), models.Post.id.desc())
        .all()
    )
    post_ids = [post.id for post in posts]
    period_days = (end - start).days + 1
    previous_start = start - timedelta(days=period_days)
    previous_end = start - timedelta(days=1)
    lifetime_views = _post_view_counts(db, post_ids)
    period_views = _post_view_counts(db, post_ids, start, end)
    previous_views = _post_view_counts(db, post_ids, previous_start, previous_end)
    listens = _post_listen_seconds(db, post_ids, start, end)
    likes = _post_counts(db, models.Like, post_ids)
    comments = _post_counts(db, models.Comment, post_ids, approved_only=True)
    return [
        {
            "post": post,
            "lifetime_views": int(lifetime_views.get(post.id, post.view_count or 0) or 0),
            "period_views": int(period_views.get(post.id, 0) or 0),
            "previous_views": int(previous_views.get(post.id, 0) or 0),
            "seconds_listened": int(listens.get(post.id, 0) or 0),
            "likes": int(likes.get(post.id, 0) or 0),
            "comments": int(comments.get(post.id, 0) or 0),
        }
        for post in posts
    ]


def queue_analytics_digest(
    db: Session,
    user: models.User,
    *,
    start: date,
    end: date,
    cadence: str,
) -> Optional[models.EmailOutbox]:
    if not user.email_analytics_digest or user.is_suspended:
        return None
    rows = _analytics_rows(db, user, start, end)
    if not rows:
        return None
    total_period_views = sum(row["period_views"] for row in rows)
    total_previous_views = sum(row["previous_views"] for row in rows)
    total_seconds = sum(row["seconds_listened"] for row in rows)
    period_label = start.isoformat() if start == end else f"{start.isoformat()} - {end.isoformat()}"
    title = "Analitice avansate"
    table_rows = []
    for row in rows:
        post = row["post"]
        delta = row["period_views"] - row["previous_views"]
        sign = "+" if delta >= 0 else ""
        href = author_url(user.username, f"/{post.slug}")
        table_rows.append(
            "<tr>"
            f'<td style="padding:8px;border-bottom:1px solid #e3d8c9;"><a href="{html.escape(href, quote=True)}" style="color:#1f1d1b;">{html.escape(post.title)}</a></td>'
            f'<td style="padding:8px;border-bottom:1px solid #e3d8c9;text-align:right;">{row["lifetime_views"]}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e3d8c9;text-align:right;">{row["period_views"]}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e3d8c9;text-align:right;">{sign}{delta}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e3d8c9;text-align:right;">{html.escape(_format_seconds(row["seconds_listened"]))}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e3d8c9;text-align:right;">{row["likes"]}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e3d8c9;text-align:right;">{row["comments"]}</td>'
            "</tr>"
        )
    body = (
        f"<p>Raportul tău de Analitice avansate pentru {html.escape(period_label)}.</p>"
        f"<p><strong>{total_period_views}</strong> vizualizări reale, "
        f"<strong>{total_period_views - total_previous_views:+d}</strong> față de perioada precedentă, "
        f"<strong>{html.escape(_format_seconds(total_seconds))}</strong> ascultate.</p>"
        '<table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">'
        '<thead><tr>'
        '<th style="text-align:left;padding:8px;border-bottom:1px solid #b9aa99;">Text</th>'
        '<th style="text-align:right;padding:8px;border-bottom:1px solid #b9aa99;">Total views</th>'
        '<th style="text-align:right;padding:8px;border-bottom:1px solid #b9aa99;">Views</th>'
        '<th style="text-align:right;padding:8px;border-bottom:1px solid #b9aa99;">Dif.</th>'
        '<th style="text-align:right;padding:8px;border-bottom:1px solid #b9aa99;">Ascultat</th>'
        '<th style="text-align:right;padding:8px;border-bottom:1px solid #b9aa99;">Like</th>'
        '<th style="text-align:right;padding:8px;border-bottom:1px solid #b9aa99;">Comentarii</th>'
        "</tr></thead><tbody>"
        f"{''.join(table_rows)}</tbody></table>"
        f"{_button('Deschide panoul', author_url(user.username, '/panou'))}"
    )
    html_content = _email_page(title, _with_footer(user, EMAIL_TYPE_ANALYTICS, body))
    text_lines = [
        f"Analitice avansate pentru {period_label}",
        f"Vizualizări: {total_period_views} ({total_period_views - total_previous_views:+d})",
        f"Secunde ascultate: {_format_seconds(total_seconds)}",
        "",
    ]
    for row in rows:
        text_lines.append(
            f"{row['post'].title}: total {row['lifetime_views']} views, "
            f"{row['period_views']} în perioadă ({row['period_views'] - row['previous_views']:+d}), "
            f"{_format_seconds(row['seconds_listened'])} ascultate"
        )
    text_lines.extend(["", author_url(user.username, "/panou"), f"Dezabonare: {unsubscribe_url(user.id, EMAIL_TYPE_ANALYTICS)}"])
    return queue_email(
        db,
        recipient_user_id=user.id,
        recipient_email=user.email,
        recipient_name=user.username,
        subject=f"Analitice avansate: {period_label}",
        html_content=html_content,
        text_content="\n".join(text_lines),
        email_type=EMAIL_TYPE_ANALYTICS,
        extra_data={"cadence": cadence, "start": start.isoformat(), "end": end.isoformat()},
        dedupe_key=f"analytics:{user.id}:{cadence}:{start.isoformat()}:{end.isoformat()}",
    )


def _is_daily_analytics_user(user: models.User) -> bool:
    return bool(user.is_premium and user.premium_tier in {"cronicar", "rapsod"})


def queue_due_analytics_digests(db: Session, today: Optional[date] = None) -> int:
    current = today or datetime.now(timezone.utc).date()
    yesterday = current - timedelta(days=1)
    users = (
        db.query(models.User)
        .filter(models.User.email_analytics_digest == True, models.User.is_suspended == False)
        .order_by(models.User.id.asc())
        .all()
    )
    queued = 0
    for user in users:
        if _is_daily_analytics_user(user):
            if queue_analytics_digest(db, user, start=yesterday, end=yesterday, cadence="daily"):
                queued += 1
        elif current.weekday() == 0:
            start = current - timedelta(days=7)
            end = current - timedelta(days=1)
            if queue_analytics_digest(db, user, start=start, end=end, cadence="weekly"):
                queued += 1
    return queued


def queue_admin_campaign(
    db: Session,
    *,
    actor: models.User,
    subject: str,
    html_content: str,
    recipients: Iterable[models.User],
    filters: Optional[dict] = None,
    selected_user_ids: Optional[list[int]] = None,
    matched_count: int = 0,
) -> models.EmailCampaign:
    cleaned_html = normalize_email_html(html_content)
    text_content = _strip_html_to_text(cleaned_html)
    campaign = models.EmailCampaign(
        actor_user_id=actor.id,
        subject=subject[:255],
        html_content=cleaned_html,
        text_content=text_content,
        filters=filters or {},
        selected_user_ids=selected_user_ids or [],
        matched_count=matched_count,
        status="queued",
        queued_at=utcnow_naive(),
    )
    db.add(campaign)
    db.flush()
    queued = 0
    recipient_count = 0
    for user in recipients:
        if not user.email_admin_announcements or user.is_suspended or not user.email:
            continue
        recipient_count += 1
        html_body = _with_footer(user, EMAIL_TYPE_ADMIN, cleaned_html)
        text = f"{text_content}\n\nDezabonare: {unsubscribe_url(user.id, EMAIL_TYPE_ADMIN)}"
        row = queue_email(
            db,
            recipient_user_id=user.id,
            recipient_email=user.email,
            recipient_name=user.username,
            subject=subject,
            html_content=html_body,
            text_content=text,
            email_type=EMAIL_TYPE_ADMIN,
            campaign_id=campaign.id,
            extra_data={"campaign_id": campaign.id, "actor_id": actor.id},
            dedupe_key=f"admin-campaign:{campaign.id}:user:{user.id}",
            commit=False,
        )
        if row:
            queued += 1
    campaign.recipient_count = recipient_count
    campaign.queued_count = queued
    db.commit()
    db.refresh(campaign)
    return campaign
