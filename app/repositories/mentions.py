import html

from ._shared import *
from .notifications import create_notification
from .. import email_service
from ..utils import SUBDOMAIN_SUFFIX

MENTION_RE = re.compile(r"(?<![A-Za-z0-9])@([A-Za-z0-9]{1,255})")
HTML_TAG_RE = re.compile(r"(<[^>]+>)")


def extract_mentioned_usernames(content: str | None) -> List[str]:
    """Return unique @username mentions in first-seen order."""
    plain_text = rich_text.rich_text_to_plain_text(content)
    usernames: List[str] = []
    seen: set[str] = set()
    for match in MENTION_RE.finditer(plain_text):
        username = match.group(1)
        key = username.lower()
        if key in seen:
            continue
        seen.add(key)
        usernames.append(username)
    return usernames


def _mentioned_users(
    db: Session,
    content: str | None,
    actor_id: Optional[int],
) -> List[models.User]:
    usernames = extract_mentioned_usernames(content)
    if not usernames or not actor_id:
        return []

    order_by_username = {username.lower(): index for index, username in enumerate(usernames)}
    users = (
        db.query(models.User)
        .filter(
            func.lower(models.User.username).in_(list(order_by_username.keys())),
            models.User.id != actor_id,
            models.User.is_suspended == False,
        )
        .all()
    )
    return sorted(users, key=lambda user: order_by_username.get(user.username.lower(), len(order_by_username)))


def _users_for_mention_links(db: Session, content: str | None) -> Dict[str, models.User]:
    usernames = extract_mentioned_usernames(content)
    if not usernames:
        return {}

    return {
        user.username.lower(): user
        for user in (
            db.query(models.User)
            .filter(
                func.lower(models.User.username).in_([username.lower() for username in usernames]),
                models.User.is_suspended == False,
            )
            .all()
        )
    }


def _blog_href(username: str) -> str:
    suffix = SUBDOMAIN_SUFFIX if SUBDOMAIN_SUFFIX.startswith(".") else f".{SUBDOMAIN_SUFFIX}"
    return f"//{username}{suffix}"


def _link_mentions_in_text_chunk(chunk: str, users_by_username: Dict[str, models.User]) -> str:
    def replace(match: re.Match) -> str:
        typed_username = match.group(1)
        user = users_by_username.get(typed_username.lower())
        if not user:
            return match.group(0)
        label = html.escape(f"@{user.username}")
        href = html.escape(_blog_href(user.username), quote=True)
        return f'<a class="mention-link" href="{href}">{label}</a>'

    return MENTION_RE.sub(replace, chunk)


def _plain_text_to_linkable_html(value: str) -> str:
    paragraphs = []
    for block in re.split(r"\n{2,}", value):
        lines = [html.escape(line) for line in block.splitlines()]
        paragraphs.append(f"<p>{'<br>'.join(lines)}</p>")
    return "".join(paragraphs)


def link_mentions_in_rich_text(db: Session, content: str | None) -> str:
    """Sanitize content, then link existing @username mentions to user blogs."""
    sanitized = rich_text.sanitize_rich_text(content)
    if not sanitized:
        return ""

    users_by_username = _users_for_mention_links(db, sanitized)
    if not users_by_username:
        return sanitized

    linkable = sanitized if rich_text.HTML_RE.search(sanitized) else _plain_text_to_linkable_html(sanitized)
    parts = HTML_TAG_RE.split(linkable)
    return "".join(
        part if HTML_TAG_RE.fullmatch(part) else _link_mentions_in_text_chunk(part, users_by_username)
        for part in parts
    )


def _create_mention_notifications(
    db: Session,
    *,
    actor: Optional[models.User],
    content: str | None,
    source_type: str,
    source_id: int,
    link: Optional[str],
    source_title: Optional[str] = None,
) -> None:
    if not actor:
        return

    for user in _mentioned_users(db, content, actor.id):
        create_notification(
            db=db,
            user_id=user.id,
            notif_type="mention",
            title=f"{actor.username} te-a menționat",
            message=source_title or "Ai fost menționat într-o conversație.",
            link=link,
            extra_data={
                "source_type": source_type,
                "source_id": source_id,
                "actor_id": actor.id,
                "actor_username": actor.username,
            },
        )
        email_service.queue_mention_email(
            db=db,
            target=user,
            actor=actor,
            source_type=source_type,
            source_id=source_id,
            source_title=source_title,
            link=link,
        )


def notify_mentions_for_forum_thread(db: Session, thread: models.ForumThread) -> None:
    actor = thread.author or db.query(models.User).filter(models.User.id == thread.author_id).first()
    _create_mention_notifications(
        db,
        actor=actor,
        content=thread.content,
        source_type="forum_thread",
        source_id=thread.id,
        link=f"/discutii/{thread.slug}",
        source_title=f"În discuția „{thread.title}\".",
    )


def notify_mentions_for_forum_reply(db: Session, reply: models.ForumReply) -> None:
    thread = reply.thread or db.query(models.ForumThread).filter(models.ForumThread.id == reply.thread_id).first()
    actor = reply.author or db.query(models.User).filter(models.User.id == reply.author_id).first()
    _create_mention_notifications(
        db,
        actor=actor,
        content=reply.content,
        source_type="forum_reply",
        source_id=reply.id,
        link=f"/discutii/{thread.slug}#reply-{reply.id}" if thread else None,
        source_title=f"În răspunsul la „{thread.title}\"." if thread else "Într-un răspuns de pe forum.",
    )


def notify_mentions_for_comment(db: Session, comment: models.Comment) -> None:
    post = comment.post or db.query(models.Post).filter(models.Post.id == comment.post_id).first()
    actor = comment.commenter or (
        db.query(models.User).filter(models.User.id == comment.user_id).first() if comment.user_id else None
    )
    if not post:
        return

    owner = post.owner or db.query(models.User).filter(models.User.id == post.user_id).first()
    suffix = SUBDOMAIN_SUFFIX if SUBDOMAIN_SUFFIX.startswith(".") else f".{SUBDOMAIN_SUFFIX}"
    link = f"//{owner.username}{suffix}/{post.slug}#comment-{comment.id}" if owner else f"/{post.slug}#comment-{comment.id}"
    _create_mention_notifications(
        db,
        actor=actor,
        content=comment.content,
        source_type="comment",
        source_id=comment.id,
        link=link,
        source_title=f"Într-un comentariu la „{post.title}\".",
    )
