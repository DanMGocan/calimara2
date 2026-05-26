import logging
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import String, and_, case, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from .. import admin, crud, email_service, invitations, models, object_storage, platform_access, schemas, statistics
from ..database import get_db
from ..utils import author_public_url, post_public_url
from ..week_util import utcnow_naive

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

CONTENT_TYPES = {"post", "comment", "audio", "forum_thread", "forum_reply", "theatre_entry", "stafeta_segment"}
CONTENT_STATUSES = {"approved", "pending", "flagged", "rejected"}
PREMIUM_TIERS = {"free", "trubadur", "cronicar", "rapsod"}
STORAGE_APP_PREFIXES = ("posts/", "users/", "clubs/")
STORAGE_STATUS_FILTERS = {"all", "referenced", "unreferenced", "deletable", "protected"}
QA_REPORT_MESSAGE_PREFIX = "Raport QA"
QA_REPORT_CONTEXT_FIELD = "report_stamp"


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Format dată invalid: {value}. Folosiți YYYY-MM-DD.")


def _date_filters(column, from_date: Optional[date], to_date: Optional[date]) -> list:
    filters = []
    if from_date:
        filters.append(column >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        filters.append(column < datetime.combine(to_date + timedelta(days=1), datetime.min.time()))
    return filters


def _audit(
    db: Session,
    request: Optional[Request],
    actor: models.User,
    *,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[models.AdminAuditLog]:
    return admin.write_admin_audit_log(
        db,
        actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        request=request,
        extra_data=metadata,
    )


def _admin_count(db: Session) -> int:
    return db.query(models.User).filter(models.User.is_admin == True).count()


def _ensure_not_self(actor: models.User, target: models.User, action: str) -> None:
    if actor.id == target.id:
        raise HTTPException(status_code=400, detail=f"Nu poți executa această acțiune asupra propriului cont: {action}.")


def _ensure_can_remove_admin(db: Session, target: models.User) -> None:
    if target.is_admin and _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Nu poți modifica ultimul administrator.")


def _delete_user_owned_content(db: Session, user_id: int) -> dict:
    """Remove user-authored content that would otherwise be anonymized."""
    counts = {}

    def delete_rows(label: str, query) -> None:
        counts[label] = query.delete(synchronize_session=False)

    counts["theatre_scenes_opened"] = (
        db.query(models.TheatreScene)
        .filter(models.TheatreScene.opened_by == user_id)
        .update({models.TheatreScene.opened_by: None}, synchronize_session=False)
    )
    delete_rows("comments", db.query(models.Comment).filter(models.Comment.user_id == user_id))
    delete_rows("likes", db.query(models.Like).filter(models.Like.user_id == user_id))
    delete_rows("audio_listen_events", db.query(models.AudioListenEvent).filter(models.AudioListenEvent.listener_user_id == user_id))
    delete_rows("forum_replies", db.query(models.ForumReply).filter(models.ForumReply.author_id == user_id))
    delete_rows("forum_threads", db.query(models.ForumThread).filter(models.ForumThread.author_id == user_id))
    delete_rows("club_board_messages", db.query(models.ClubBoardMessage).filter(models.ClubBoardMessage.author_id == user_id))
    delete_rows("theatre_entries", db.query(models.TheatreEntry).filter(models.TheatreEntry.author_id == user_id))
    delete_rows("stafeta_segments", db.query(models.StafetaSegment).filter(models.StafetaSegment.author_id == user_id))
    delete_rows("post_drafts", db.query(models.PostDraft).filter(models.PostDraft.user_id == user_id))
    delete_rows("posts", db.query(models.Post).filter(models.Post.user_id == user_id))

    return counts


def _as_iso(value):
    return value.isoformat() if value else None


def _storage_prefix_type(key: str) -> str:
    for prefix in STORAGE_APP_PREFIXES:
        if key.startswith(prefix):
            return prefix.rstrip("/")
    return "outside"


def _add_storage_reference(references: dict[str, list[dict]], key: Optional[str], payload: dict) -> None:
    if not key:
        return
    references.setdefault(key, []).append(payload)


def _main_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return path if path.startswith("/") else f"/{path}"


def _forum_thread_url(thread: Optional[models.ForumThread], anchor: Optional[str] = None) -> Optional[str]:
    if not thread or not thread.slug:
        return None
    path = f"/discutii/{thread.slug}"
    if anchor:
        path = f"{path}#{str(anchor).lstrip('#')}"
    return path


def _theatre_play_url(play: Optional[models.TheatrePlay]) -> Optional[str]:
    return f"/teatru/{play.slug}" if play and play.slug else None


def _stafeta_work_url(work: Optional[models.StafetaWork]) -> Optional[str]:
    return f"/stafeta/{work.slug}" if work and work.slug else None


def _storage_reference_map(db: Session) -> dict[str, list[dict]]:
    references: dict[str, list[dict]] = {}

    audio_rows = (
        db.query(models.PostAudio)
        .options(joinedload(models.PostAudio.post).joinedload(models.Post.owner))
        .filter(
            models.PostAudio.storage_backend == "s3",
            models.PostAudio.storage_key.isnot(None),
        )
        .all()
    )
    for audio in audio_rows:
        post = audio.post
        title = post.title if post else "Audio"
        author = post.owner.username if post and post.owner else None
        label = f"Audio #{audio.id} · {title}"
        if author:
            label = f"{label} · @{author}"
        _add_storage_reference(
            references,
            audio.storage_key,
            {
                "type": "audio",
                "id": audio.id,
                "label": label,
                "target_url": post_public_url(post.owner, post.slug) if post and post.owner else None,
            },
        )

    users = (
        db.query(models.User)
        .filter(
            or_(
                and_(models.User.profile_photo_storage_backend == "s3", models.User.profile_photo_storage_key.isnot(None)),
                and_(models.User.cover_photo_storage_backend == "s3", models.User.cover_photo_storage_key.isnot(None)),
            )
        )
        .all()
    )
    for user in users:
        _add_storage_reference(
            references,
            user.profile_photo_storage_key,
            {
                "type": "user_profile_photo",
                "id": user.id,
                "label": f"Profil utilizator · @{user.username}",
                "target_url": author_public_url(user),
            },
        )
        _add_storage_reference(
            references,
            user.cover_photo_storage_key,
            {
                "type": "user_cover_photo",
                "id": user.id,
                "label": f"Copertă utilizator · @{user.username}",
                "target_url": author_public_url(user),
            },
        )

    clubs = (
        db.query(models.Club)
        .filter(
            or_(
                and_(models.Club.profile_photo_storage_backend == "s3", models.Club.profile_photo_storage_key.isnot(None)),
                and_(models.Club.cover_photo_storage_backend == "s3", models.Club.cover_photo_storage_key.isnot(None)),
            )
        )
        .all()
    )
    for club in clubs:
        _add_storage_reference(
            references,
            club.profile_photo_storage_key,
            {
                "type": "club_profile_photo",
                "id": club.id,
                "label": f"Profil club · {club.title}",
                "target_url": _main_path(f"/cluburi/{club.slug}") if club.slug else None,
            },
        )
        _add_storage_reference(
            references,
            club.cover_photo_storage_key,
            {
                "type": "club_cover_photo",
                "id": club.id,
                "label": f"Copertă club · {club.title}",
                "target_url": _main_path(f"/cluburi/{club.slug}") if club.slug else None,
            },
        )

    return references


def _serialize_storage_time(value) -> Optional[str]:
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _storage_object_payload(raw: dict, references: dict[str, list[dict]]) -> dict:
    key = str(raw.get("Key") or "")
    refs = references.get(key, [])
    prefix_type = _storage_prefix_type(key)
    known_prefix = prefix_type != "outside"
    can_delete = known_prefix and not refs
    protected_reason = None
    if refs:
        protected_reason = "Obiectul este folosit de înregistrări din baza de date."
    elif not known_prefix:
        protected_reason = "Obiectul este în afara prefixelor Călimara și este doar vizibil."
    return {
        "key": key,
        "size": raw.get("Size") or 0,
        "last_modified": _serialize_storage_time(raw.get("LastModified")),
        "etag": str(raw.get("ETag") or "").strip('"'),
        "storage_class": raw.get("StorageClass"),
        "prefix_type": prefix_type,
        "known_prefix": known_prefix,
        "references": refs,
        "can_delete": can_delete,
        "protected_reason": protected_reason,
    }


def _matches_storage_status(payload: dict, status_filter: str) -> bool:
    if status_filter == "all":
        return True
    has_references = bool(payload["references"])
    if status_filter == "referenced":
        return has_references
    if status_filter == "unreferenced":
        return not has_references
    if status_filter == "deletable":
        return bool(payload["can_delete"])
    if status_filter == "protected":
        return not payload["can_delete"]
    return False


def _storage_error(detail: str, exc: Exception) -> HTTPException:
    logger.warning("Object storage admin operation failed: %s", detail, exc_info=True)
    return HTTPException(status_code=503, detail=detail)


def _storage_metadata_payload(object_metadata: dict) -> dict:
    return {
        "size": object_metadata.get("ContentLength"),
        "content_type": object_metadata.get("ContentType"),
        "etag": str(object_metadata.get("ETag") or "").strip('"'),
        "last_modified": _serialize_storage_time(object_metadata.get("LastModified")),
    }


def _clear_media_reference(item, prefix: str) -> None:
    setattr(item, f"{prefix}_storage_backend", None)
    setattr(item, f"{prefix}_storage_key", None)
    setattr(item, f"{prefix}_content_type", None)
    setattr(item, f"{prefix}_updated_at", None)


def _cleanup_storage_references(db: Session, key: str, reason: str) -> dict:
    counts = {
        "audio": 0,
        "user_profile_photo": 0,
        "user_cover_photo": 0,
        "club_profile_photo": 0,
        "club_cover_photo": 0,
    }
    now = utcnow_naive()
    cancelled_reason = f"Fișier curățat din panoul admin: {reason}"

    audio_rows = (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.storage_backend == "s3",
            models.PostAudio.storage_key == key,
        )
        .all()
    )
    for audio in audio_rows:
        audio.status = "cancelled"
        audio.storage_backend = None
        audio.storage_key = None
        audio.content_type = None
        audio.byte_size = None
        audio.moderation_status = "cancelled"
        audio.moderation_reason = cancelled_reason
        audio.updated_at = now
        counts["audio"] += 1

    users = (
        db.query(models.User)
        .filter(
            or_(
                and_(models.User.profile_photo_storage_backend == "s3", models.User.profile_photo_storage_key == key),
                and_(models.User.cover_photo_storage_backend == "s3", models.User.cover_photo_storage_key == key),
            )
        )
        .all()
    )
    for user in users:
        if user.profile_photo_storage_backend == "s3" and user.profile_photo_storage_key == key:
            _clear_media_reference(user, "profile_photo")
            counts["user_profile_photo"] += 1
        if user.cover_photo_storage_backend == "s3" and user.cover_photo_storage_key == key:
            _clear_media_reference(user, "cover_photo")
            counts["user_cover_photo"] += 1

    clubs = (
        db.query(models.Club)
        .filter(
            or_(
                and_(models.Club.profile_photo_storage_backend == "s3", models.Club.profile_photo_storage_key == key),
                and_(models.Club.cover_photo_storage_backend == "s3", models.Club.cover_photo_storage_key == key),
            )
        )
        .all()
    )
    for club in clubs:
        if club.profile_photo_storage_backend == "s3" and club.profile_photo_storage_key == key:
            _clear_media_reference(club, "profile_photo")
            counts["club_profile_photo"] += 1
        if club.cover_photo_storage_backend == "s3" and club.cover_photo_storage_key == key:
            _clear_media_reference(club, "cover_photo")
            counts["club_cover_photo"] += 1

    total = sum(counts.values())
    return {
        "counts": counts,
        "total": total,
    }


def _user_payload(db: Session, user: models.User, include_counts: bool = False) -> dict:
    payload = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "is_moderator": user.is_moderator,
        "is_suspended": user.is_suspended,
        "suspension_reason": user.suspension_reason,
        "suspended_at": _as_iso(user.suspended_at),
        "suspended_by": user.suspended_by,
        "premium_tier": user.premium_tier,
        "premium_period_start": _as_iso(user.premium_period_start),
        "premium_until": _as_iso(user.premium_until),
        "is_premium": user.is_premium,
        "stripe_customer_id": user.stripe_customer_id,
        "stripe_subscription_id": user.stripe_subscription_id,
        "gologani_balance": user.gologani_balance,
        "seconds_listened": user.seconds_listened or 0,
        "last_login_at": _as_iso(user.last_login_at),
        "email_comment_notifications": user.email_comment_notifications,
        "email_mention_notifications": user.email_mention_notifications,
        "email_analytics_digest": user.email_analytics_digest,
        "email_admin_announcements": user.email_admin_announcements,
        "created_at": _as_iso(user.created_at),
        "updated_at": _as_iso(user.updated_at),
    }
    if include_counts:
        payload["counts"] = {
            "posts": db.query(models.Post).filter(models.Post.user_id == user.id).count(),
            "comments": db.query(models.Comment).filter(models.Comment.user_id == user.id).count(),
            "forum_threads": db.query(models.ForumThread).filter(models.ForumThread.author_id == user.id).count(),
            "forum_replies": db.query(models.ForumReply).filter(models.ForumReply.author_id == user.id).count(),
            "super_likes_given": db.query(models.SuperLike).filter(models.SuperLike.user_id == user.id).count(),
            "inventory_items": db.query(models.UserInventoryItem).filter(models.UserInventoryItem.user_id == user.id).count(),
        }
    return payload


def _audit_payload(log: models.AdminAuditLog, db: Optional[Session] = None) -> dict:
    return {
        "id": log.id,
        "actor_user_id": log.actor_user_id,
        "actor_username": log.actor_username,
        "actor_url": author_public_url(log.actor_username) if log.actor_username else None,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "target_url": _admin_target_url(db, log.target_type, log.target_id) if db else None,
        "reason": log.reason,
        "ip_address": log.ip_address,
        "metadata": log.extra_data or {},
        "created_at": _as_iso(log.created_at),
    }


def _coerce_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _site_feedback_reply_targets_for_conversation(db: Session, conversation_id: int) -> list[tuple[datetime, int, int]]:
    logs = (
        db.query(models.AdminAuditLog)
        .filter(
            models.AdminAuditLog.action == "site_feedback_reply",
            models.AdminAuditLog.target_type == "site_feedback",
            models.AdminAuditLog.target_id != None,
        )
        .all()
    )
    message_to_feedback: dict[int, int] = {}
    for log in logs:
        metadata = log.extra_data or {}
        if _coerce_int(metadata.get("conversation_id")) != conversation_id:
            continue
        message_id = _coerce_int(metadata.get("message_id"))
        if message_id is not None and log.target_id is not None:
            message_to_feedback[message_id] = log.target_id

    if not message_to_feedback:
        return []

    reply_messages = (
        db.query(models.Message.id, models.Message.created_at)
        .filter(
            models.Message.conversation_id == conversation_id,
            models.Message.id.in_(message_to_feedback.keys()),
        )
        .order_by(models.Message.created_at.asc(), models.Message.id.asc())
        .all()
    )
    return [
        (created_at or datetime.min, message_id, message_to_feedback[message_id])
        for message_id, created_at in reply_messages
        if message_id in message_to_feedback
    ]


def _site_feedback_target_for_user_reply(
    message: models.Message,
    reply_targets: list[tuple[datetime, int, int]],
) -> Optional[int]:
    message_key = (message.created_at or datetime.min, message.id or 0)
    matched_target_id: Optional[int] = None
    for reply_created_at, reply_message_id, feedback_id in reply_targets:
        if (reply_created_at, reply_message_id) < message_key:
            matched_target_id = feedback_id
        else:
            break
    return matched_target_id


def _site_feedback_unread_reply_messages(db: Session, item: models.SiteFeedback) -> list[models.Message]:
    if not item.support_conversation_id or not item.user_id:
        return []

    messages = (
        db.query(models.Message)
        .filter(
            models.Message.conversation_id == item.support_conversation_id,
            models.Message.sender_id == item.user_id,
            models.Message.is_read == False,
        )
        .order_by(models.Message.created_at.desc(), models.Message.id.desc())
        .all()
    )
    reply_targets = _site_feedback_reply_targets_for_conversation(db, item.support_conversation_id)
    if not reply_targets:
        return messages
    return [
        message
        for message in messages
        if _site_feedback_target_for_user_reply(message, reply_targets) == item.id
    ]


def _mark_site_feedback_replies_as_read(db: Session, item: models.SiteFeedback) -> int:
    unread_messages = _site_feedback_unread_reply_messages(db, item)
    if not unread_messages:
        return 0
    unread_message_ids = [message.id for message in unread_messages]
    return db.query(models.Message).filter(
        models.Message.id.in_(unread_message_ids),
        models.Message.is_read == False,
    ).update({"is_read": True}, synchronize_session=False)


def _site_feedback_unread_reply_summary(db: Session, item: models.SiteFeedback) -> dict:
    summary = {
        "unread_reply_count": 0,
        "latest_unread_reply_at": None,
        "latest_unread_reply_preview": None,
    }
    unread_messages = _site_feedback_unread_reply_messages(db, item)
    summary["unread_reply_count"] = len(unread_messages)
    if not unread_messages:
        return summary

    latest_reply = unread_messages[0]
    if latest_reply:
        summary["latest_unread_reply_at"] = _as_iso(latest_reply.created_at)
        summary["latest_unread_reply_preview"] = latest_reply.content
    return summary


def _site_feedback_payload(item: models.SiteFeedback, db: Optional[Session] = None) -> dict:
    payload = {
        "id": item.id,
        "kind": item.kind,
        "user_id": item.user_id,
        "username_snapshot": item.username_snapshot,
        "email_snapshot": item.email_snapshot,
        "message": item.message,
        "page_url": item.page_url,
        "user_agent": item.user_agent,
        "client_context": item.client_context or {},
        "status": item.status,
        "admin_note": item.admin_note,
        "resolved_by": item.resolved_by,
        "resolver_username": item.resolver.username if item.resolver else None,
        "resolved_at": _as_iso(item.resolved_at),
        "support_conversation_id": item.support_conversation_id,
        "support_started_at": _as_iso(item.support_started_at),
        "created_at": _as_iso(item.created_at),
        "updated_at": _as_iso(item.updated_at),
    }
    if db is not None:
        payload.update(_site_feedback_unread_reply_summary(db, item))
    return payload


def _site_feedback_thread_message_payload(message: models.Message) -> dict:
    sender = message.sender
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "sender_username": sender.username if sender else None,
        "sender_is_system": bool(getattr(sender, "is_system", False)),
        "sender_label": "Călimara" if getattr(sender, "is_system", False) else (sender.username if sender else "Utilizator"),
        "content": message.content,
        "created_at": _as_iso(message.created_at),
    }


def _site_feedback_thread_payload(db: Session, item: models.SiteFeedback) -> dict:
    messages = []
    if item.support_conversation_id:
        messages = (
            db.query(models.Message)
            .options(joinedload(models.Message.sender))
            .filter(models.Message.conversation_id == item.support_conversation_id)
            .order_by(models.Message.created_at.asc(), models.Message.id.asc())
            .all()
        )
    return {
        "feedback": _site_feedback_payload(item, db),
        "conversation_id": item.support_conversation_id,
        "messages": [_site_feedback_thread_message_payload(message) for message in messages],
        "unread_reply_count": _admin_site_feedback_unread_reply_count(db),
    }


def _qa_report_feedback_filter():
    context_text = models.SiteFeedback.client_context.cast(String)
    return or_(
        models.SiteFeedback.message.ilike(f"{QA_REPORT_MESSAGE_PREFIX}%"),
        context_text.ilike(f"%{QA_REPORT_CONTEXT_FIELD}%"),
    )


def _admin_site_feedback_unread_reply_count(db: Session) -> int:
    return int(
        db.query(func.count(func.distinct(models.Message.id)))
        .join(
            models.SiteFeedback,
            models.SiteFeedback.support_conversation_id == models.Message.conversation_id,
        )
        .filter(
            ~_qa_report_feedback_filter(),
            models.SiteFeedback.support_conversation_id != None,
            models.SiteFeedback.user_id != None,
            models.Message.sender_id == models.SiteFeedback.user_id,
            models.Message.is_read == False,
        )
        .scalar()
        or 0
    )


def _admin_site_feedback_unread_reply_ids(db: Session) -> set[int]:
    unread_messages = (
        db.query(models.Message)
        .join(
            models.SiteFeedback,
            models.SiteFeedback.support_conversation_id == models.Message.conversation_id,
        )
        .filter(
            ~_qa_report_feedback_filter(),
            models.SiteFeedback.support_conversation_id != None,
            models.SiteFeedback.user_id != None,
            models.Message.sender_id == models.SiteFeedback.user_id,
            models.Message.is_read == False,
        )
        .order_by(models.Message.created_at.asc(), models.Message.id.asc())
        .all()
    )
    targets_by_conversation: dict[int, list[tuple[datetime, int, int]]] = {}
    feedback_ids: set[int] = set()
    for message in {message.id: message for message in unread_messages}.values():
        targets = targets_by_conversation.setdefault(
            message.conversation_id,
            _site_feedback_reply_targets_for_conversation(db, message.conversation_id),
        )
        target_id = _site_feedback_target_for_user_reply(message, targets)
        if target_id is not None:
            feedback_ids.add(target_id)
    return feedback_ids


def _qa_report_feedback_payload(item: models.SiteFeedback) -> dict:
    payload = _site_feedback_payload(item)
    message_lines = [line.strip() for line in str(item.message or "").splitlines() if line.strip()]
    payload["title"] = message_lines[0] if message_lines else QA_REPORT_MESSAGE_PREFIX
    payload["body"] = "\n".join(message_lines[1:]) if len(message_lines) > 1 else item.message
    payload["report_stamp"] = payload["client_context"].get(QA_REPORT_CONTEXT_FIELD)
    payload["report_part"] = payload["client_context"].get("part")
    return payload


def _platform_allowed_email_payload(item: models.PlatformAllowedEmail) -> dict:
    return {
        "id": item.id,
        "email": item.email,
        "note": item.note,
        "created_by": item.created_by,
        "created_at": _as_iso(item.created_at),
        "updated_at": _as_iso(item.updated_at),
    }


def _platform_invitation_payload(item: models.PlatformInvitation) -> dict:
    return {
        "id": item.id,
        "email": item.email,
        "status": invitations.invitation_display_status(item),
        "stored_status": item.status,
        "premium_tier": item.premium_tier,
        "premium_days": item.premium_days,
        "note": item.note,
        "created_by": item.created_by,
        "accepted_user_id": item.accepted_user_id,
        "expires_at": _as_iso(item.expires_at),
        "accepted_at": _as_iso(item.accepted_at),
        "revoked_at": _as_iso(item.revoked_at),
        "resent_at": _as_iso(item.resent_at),
        "created_at": _as_iso(item.created_at),
        "updated_at": _as_iso(item.updated_at),
    }


def _platform_access_payload(db: Session) -> dict:
    emails = platform_access.list_allowed_emails(db)
    invite_rows = invitations.list_invitations(db)
    return {
        "open": platform_access.is_platform_open(db),
        "allowed_count": len(emails),
        "emails": [_platform_allowed_email_payload(item) for item in emails],
        "invitation_count": len(invite_rows),
        "invitations": [_platform_invitation_payload(item) for item in invite_rows],
    }


def _queue_platform_invitation(
    db: Session,
    *,
    invitation: models.PlatformInvitation,
    token: str,
    temporary_password: str,
    actor: models.User,
) -> Optional[models.EmailOutbox]:
    invite_url = email_service.main_url(f"/invitatie/{token}")
    row = email_service.queue_platform_invitation_email(
        db,
        recipient_email=invitation.email,
        invitation_url=invite_url,
        temporary_password=temporary_password,
        premium_tier=invitation.premium_tier,
        premium_days=invitation.premium_days,
        actor=actor,
        invitation_id=invitation.id,
    )
    email_service.send_queued_email_now(db, row, worker=f"admin-invitation:{actor.id}")
    return row


def _admin_daily_metrics_available(db: Session) -> bool:
    if admin.db_table_exists(db, models.AdminDailyMetric.__tablename__):
        return True
    admin.warn_missing_table_once(
        models.AdminDailyMetric.__tablename__,
        "admin daily metrics are returned empty and rollups are computed without persistence",
    )
    return False


def _admin_audit_logs_available(db: Session) -> bool:
    if admin.db_table_exists(db, models.AdminAuditLog.__tablename__):
        return True
    admin.warn_missing_table_once(
        models.AdminAuditLog.__tablename__,
        "admin audit history is returned empty and new audit entries are skipped",
    )
    return False


def _job_payload(job: models.AIJob, db: Optional[Session] = None) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "target_type": job.target_type,
        "target_id": job.target_id,
        "target_url": _admin_target_url(db, job.target_type, job.target_id) if db else None,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "run_after": _as_iso(job.run_after),
        "locked_at": _as_iso(job.locked_at),
        "locked_by": job.locked_by,
        "error_message": job.error_message,
        "created_at": _as_iso(job.created_at),
        "updated_at": _as_iso(job.updated_at),
    }


def _content_payload(item, content_type: str) -> dict:
    if content_type == "post":
        return {
            "id": item.id,
            "type": "post",
            "title": item.title,
            "slug": item.slug,
            "content": item.content,
            "author": item.owner.username if item.owner else None,
            "author_id": item.user_id,
            "author_url": author_public_url(item.owner) if item.owner else None,
            "target_url": post_public_url(item.owner, item.slug) if item.owner else None,
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "category": item.category,
            "views": item.view_count,
            "seconds_listened": item.seconds_listened or 0,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    if content_type == "comment":
        return {
            "id": item.id,
            "type": "comment",
            "title": item.post.title if item.post else "Comentariu",
            "content": item.content,
            "author": item.commenter.username if item.commenter else (item.author_name or "Anonim"),
            "author_id": item.user_id,
            "author_url": author_public_url(item.commenter) if item.commenter else None,
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "post_id": item.post_id,
            "post_slug": item.post.slug if item.post else None,
            "post_author": item.post.owner.username if item.post and item.post.owner else None,
            "target_url": post_public_url(item.post.owner, item.post.slug, f"comment-{item.id}") if item.post and item.post.owner else None,
            "created_at": _as_iso(item.created_at),
            "updated_at": None,
        }
    if content_type == "audio":
        return {
            "id": item.id,
            "type": "audio",
            "title": item.post.title if item.post else "Audio",
            "content": item.transcript or item.moderation_reason or "",
            "author": item.post.owner.username if item.post and item.post.owner else None,
            "author_id": item.post.user_id if item.post else None,
            "author_url": author_public_url(item.post.owner) if item.post and item.post.owner else None,
            "status": item.status,
            "reason": item.moderation_reason,
            "toxicity_score": None,
            "post_id": item.post_id,
            "post_slug": item.post.slug if item.post else None,
            "post_author": item.post.owner.username if item.post and item.post.owner else None,
            "target_url": post_public_url(item.post.owner, item.post.slug) if item.post and item.post.owner else None,
            "source": item.source,
            "duration_seconds": item.duration_seconds,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    if content_type == "forum_thread":
        return {
            "id": item.id,
            "type": "forum_thread",
            "title": item.title,
            "slug": item.slug,
            "content": item.content,
            "author": item.author.username if item.author else None,
            "author_id": item.author_id,
            "author_url": author_public_url(item.author) if item.author else None,
            "target_url": _forum_thread_url(item),
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "section": item.section,
            "views": item.view_count,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    if content_type == "theatre_entry":
        return {
            "id": item.id,
            "type": "theatre_entry",
            "title": item.play.title if item.play else "Teatru colaborativ",
            "content": item.content,
            "author": item.author.username if item.author else None,
            "author_id": item.author_id,
            "author_url": author_public_url(item.author) if item.author else None,
            "target_url": _theatre_play_url(item.play),
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "play_id": item.play_id,
            "play_slug": item.play.slug if item.play else None,
            "scene_id": item.scene_id,
            "entry_type": item.entry_type,
            "character": item.character.name if item.character else None,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    if content_type == "stafeta_segment":
        return {
            "id": item.id,
            "type": "stafeta_segment",
            "title": item.work.title if item.work else "Ștafeta",
            "content": item.content,
            "author": item.author.username if item.author else None,
            "author_id": item.author_id,
            "author_url": author_public_url(item.author) if item.author else None,
            "target_url": _stafeta_work_url(item.work),
            "status": item.moderation_status,
            "reason": item.moderation_reason,
            "toxicity_score": item.toxicity_score,
            "work_id": item.work_id,
            "work_slug": item.work.slug if item.work else None,
            "assignment_id": item.assignment_id,
            "created_at": _as_iso(item.created_at),
            "updated_at": _as_iso(item.updated_at),
        }
    return {
        "id": item.id,
        "type": "forum_reply",
        "title": item.thread.title if item.thread else "Răspuns pe forum",
        "content": item.content,
        "author": item.author.username if item.author else None,
        "author_id": item.author_id,
        "author_url": author_public_url(item.author) if item.author else None,
        "target_url": _forum_thread_url(item.thread, f"reply-{item.id}"),
        "status": item.moderation_status,
        "reason": item.moderation_reason,
        "toxicity_score": item.toxicity_score,
        "thread_id": item.thread_id,
        "thread_slug": item.thread.slug if item.thread else None,
        "created_at": _as_iso(item.created_at),
        "updated_at": _as_iso(item.updated_at),
    }


def _content_object(db: Session, content_type: str, content_id: int):
    if content_type == "post":
        return db.query(models.Post).options(joinedload(models.Post.owner)).filter(models.Post.id == content_id).first()
    if content_type == "comment":
        return db.query(models.Comment).options(
            joinedload(models.Comment.commenter),
            joinedload(models.Comment.post).joinedload(models.Post.owner),
        ).filter(models.Comment.id == content_id).first()
    if content_type == "audio":
        return db.query(models.PostAudio).options(
            joinedload(models.PostAudio.post).joinedload(models.Post.owner)
        ).filter(models.PostAudio.id == content_id).first()
    if content_type == "forum_thread":
        return db.query(models.ForumThread).options(joinedload(models.ForumThread.author)).filter(models.ForumThread.id == content_id).first()
    if content_type == "forum_reply":
        return db.query(models.ForumReply).options(
            joinedload(models.ForumReply.author),
            joinedload(models.ForumReply.thread),
        ).filter(models.ForumReply.id == content_id).first()
    if content_type == "theatre_entry":
        return db.query(models.TheatreEntry).options(
            joinedload(models.TheatreEntry.author),
            joinedload(models.TheatreEntry.play),
            joinedload(models.TheatreEntry.scene),
            joinedload(models.TheatreEntry.character),
        ).filter(models.TheatreEntry.id == content_id).first()
    if content_type == "stafeta_segment":
        return db.query(models.StafetaSegment).options(
            joinedload(models.StafetaSegment.author),
            joinedload(models.StafetaSegment.work),
        ).filter(models.StafetaSegment.id == content_id).first()
    return None


def _admin_target_url(db: Optional[Session], target_type: Optional[str], target_id: Optional[int]) -> Optional[str]:
    if not db or not target_type or not target_id:
        return None
    if target_type == "user":
        user = crud.get_user_by_id(db, target_id)
        return author_public_url(user) if user else None
    if target_type in CONTENT_TYPES:
        item = _content_object(db, target_type, target_id)
        if not item:
            return None
        return _content_payload(item, target_type).get("target_url")
    return None


def _count_by_status(db: Session, model, column) -> dict:
    rows = db.query(column, func.count()).group_by(column).all()
    return {str(status or "unknown"): count for status, count in rows}


def _premium_filter():
    return and_(models.User.premium_until != None, models.User.premium_until > utcnow_naive())


def _apply_admin_user_filters(
    db: Session,
    query,
    *,
    q: str = "",
    role: str = "all",
    status_filter: str = "all",
    premium: str = "all",
    joined_from: Optional[date] = None,
    joined_to: Optional[date] = None,
    last_login_from: Optional[date] = None,
    last_login_to: Optional[date] = None,
    min_posts: Optional[int] = None,
    max_posts: Optional[int] = None,
    selected_user_ids: Optional[list[int]] = None,
):
    query = query.filter(models.User.is_system == False)
    if selected_user_ids:
        return query.filter(models.User.id.in_(selected_user_ids))

    term = q.strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(models.User.username.ilike(like), models.User.email.ilike(like)))
    if role == "admin":
        query = query.filter(models.User.is_admin == True)
    elif role == "moderator":
        query = query.filter(models.User.is_moderator == True, models.User.is_admin == False)
    elif role == "member":
        query = query.filter(models.User.is_admin == False, models.User.is_moderator == False)
    if status_filter == "suspended":
        query = query.filter(models.User.is_suspended == True)
    elif status_filter == "active":
        query = query.filter(models.User.is_suspended == False)
    if premium in PREMIUM_TIERS and premium != "all":
        if premium == "free":
            query = query.filter(or_(models.User.premium_until == None, models.User.premium_until <= utcnow_naive()))
        else:
            query = query.filter(_premium_filter(), models.User.premium_tier == premium)
    query = query.filter(*_date_filters(models.User.created_at, joined_from, joined_to))
    query = query.filter(*_date_filters(models.User.last_login_at, last_login_from, last_login_to))
    if min_posts is not None or max_posts is not None:
        post_counts = (
            db.query(models.Post.user_id.label("user_id"), func.count(models.Post.id).label("post_count"))
            .group_by(models.Post.user_id)
            .subquery()
        )
        count_value = func.coalesce(post_counts.c.post_count, 0)
        query = query.outerjoin(post_counts, post_counts.c.user_id == models.User.id)
        if min_posts is not None:
            query = query.filter(count_value >= min_posts)
        if max_posts is not None:
            query = query.filter(count_value <= max_posts)
    return query


def _audience_filters_dict(audience: schemas.AdminEmailAudience) -> dict:
    return {
        "q": audience.q,
        "role": audience.role,
        "status": audience.status,
        "premium": audience.premium,
        "joined_from": audience.joined_from,
        "joined_to": audience.joined_to,
        "last_login_from": audience.last_login_from,
        "last_login_to": audience.last_login_to,
        "min_posts": audience.min_posts,
        "max_posts": audience.max_posts,
    }


def _admin_email_recipients(db: Session, audience: schemas.AdminEmailAudience) -> tuple[list[models.User], int]:
    joined_from = _parse_date(audience.joined_from)
    joined_to = _parse_date(audience.joined_to)
    last_login_from = _parse_date(audience.last_login_from)
    last_login_to = _parse_date(audience.last_login_to)
    selected_ids = [int(user_id) for user_id in audience.selected_user_ids if int(user_id) > 0]
    query = _apply_admin_user_filters(
        db,
        db.query(models.User),
        q=audience.q,
        role=audience.role,
        status_filter=audience.status,
        premium=audience.premium,
        joined_from=joined_from,
        joined_to=joined_to,
        last_login_from=last_login_from,
        last_login_to=last_login_to,
        min_posts=audience.min_posts,
        max_posts=audience.max_posts,
        selected_user_ids=selected_ids or None,
    )
    matched_count = query.count()
    recipients = (
        query.filter(
            models.User.email_admin_announcements == True,
            models.User.email != None,
            models.User.is_suspended == False,
        )
        .order_by(models.User.created_at.desc(), models.User.id.desc())
        .all()
    )
    return recipients, matched_count


def _metric_counts_for_day(db: Session, target_date: date) -> dict:
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    day_filter_user = [models.User.created_at >= start, models.User.created_at < end]
    day_filter_post = [models.Post.created_at >= start, models.Post.created_at < end]
    day_filter_comment = [models.Comment.created_at >= start, models.Comment.created_at < end]
    day_filter_views = [models.PageView.created_at >= start, models.PageView.created_at < end]
    day_filter_listens = [models.AudioListenEvent.created_at >= start, models.AudioListenEvent.created_at < end]
    day_filter_jobs = [models.AIJob.created_at >= start, models.AIJob.created_at < end]

    issued = db.query(func.coalesce(func.sum(models.GologaniTransaction.amount), 0)).filter(
        models.GologaniTransaction.amount > 0,
        models.GologaniTransaction.created_at >= start,
        models.GologaniTransaction.created_at < end,
    ).scalar()
    spent = db.query(func.coalesce(func.sum(models.GologaniTransaction.amount), 0)).filter(
        models.GologaniTransaction.amount < 0,
        models.GologaniTransaction.created_at >= start,
        models.GologaniTransaction.created_at < end,
    ).scalar()

    return {
        "new_users": db.query(models.User).filter(*day_filter_user).count(),
        "new_posts": db.query(models.Post).filter(*day_filter_post).count(),
        "new_comments": db.query(models.Comment).filter(*day_filter_comment).count(),
        "page_views": db.query(models.PageView).filter(*day_filter_views).count(),
        "seconds_listened": int(db.query(func.coalesce(func.sum(models.AudioListenEvent.seconds), 0)).filter(*day_filter_listens).scalar() or 0),
        "unique_views": db.query(models.PageView).filter(
            *day_filter_views,
            models.PageView.is_bot == False,
            models.PageView.is_duplicate == False,
        ).count(),
        "bot_views": db.query(models.PageView).filter(*day_filter_views, models.PageView.is_bot == True).count(),
        "likes": db.query(models.Like).filter(models.Like.created_at >= start, models.Like.created_at < end).count(),
        "super_likes": db.query(models.SuperLike).filter(models.SuperLike.created_at >= start, models.SuperLike.created_at < end).count(),
        "shop_purchases": db.query(models.UserInventoryItem).filter(models.UserInventoryItem.purchased_at >= start, models.UserInventoryItem.purchased_at < end).count(),
        "gologani_issued": int(issued or 0),
        "gologani_spent": abs(int(spent or 0)),
        "ai_jobs_created": db.query(models.AIJob).filter(*day_filter_jobs).count(),
        "ai_jobs_failed": db.query(models.AIJob).filter(*day_filter_jobs, models.AIJob.status == "failed").count(),
    }


def aggregate_admin_daily_metrics(db: Session, target_date: date):
    metrics = _metric_counts_for_day(db, target_date)
    metrics.update({
        "total_users": db.query(models.User).count(),
        "active_premium_users": db.query(models.User).filter(_premium_filter()).count(),
        "total_posts": db.query(models.Post).count(),
        "approved_posts": db.query(models.Post).filter(models.Post.moderation_status == "approved").count(),
        "pending_moderation": crud.get_moderation_stats(db)["total_pending"],
        "flagged_moderation": crud.get_moderation_stats(db)["total_flagged"],
        "total_comments": db.query(models.Comment).count(),
        "total_seconds_listened": int(db.query(func.coalesce(func.sum(models.User.seconds_listened), 0)).scalar() or 0),
        "forum_threads": db.query(models.ForumThread).count(),
        "forum_replies": db.query(models.ForumReply).count(),
        "shop_items": db.query(models.ShopItem).count(),
        "ai_jobs_pending": db.query(models.AIJob).filter(models.AIJob.status == "pending").count(),
        "ai_jobs_failed_total": db.query(models.AIJob).filter(models.AIJob.status == "failed").count(),
    })
    if not _admin_daily_metrics_available(db):
        return SimpleNamespace(id=None, stat_date=target_date, metrics=metrics)
    row = db.query(models.AdminDailyMetric).filter(models.AdminDailyMetric.stat_date == target_date).first()
    if row:
        row.metrics = metrics
    else:
        row = models.AdminDailyMetric(stat_date=target_date, metrics=metrics)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/overview")
def admin_overview(
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    start = _parse_date(from_date)
    end = _parse_date(to_date)
    now = utcnow_naive()
    date_f_user = _date_filters(models.User.created_at, start, end)
    date_f_post = _date_filters(models.Post.created_at, start, end)
    date_f_comment = _date_filters(models.Comment.created_at, start, end)
    overview = statistics.get_overview_stats(db, start, end)
    moderation_stats = crud.get_moderation_stats(db)
    extended_moderation = crud.get_moderation_stats_extended(db)

    premium_by_tier = {
        tier: db.query(models.User).filter(_premium_filter(), models.User.premium_tier == tier).count()
        for tier in PREMIUM_TIERS
        if tier != "free"
    }
    jobs_by_status = _count_by_status(db, models.AIJob, models.AIJob.status)
    audio_by_status = _count_by_status(db, models.PostAudio, models.PostAudio.status)
    content_by_status = {
        "posts": _count_by_status(db, models.Post, models.Post.moderation_status),
        "comments": _count_by_status(db, models.Comment, models.Comment.moderation_status),
        "forum_threads": _count_by_status(db, models.ForumThread, models.ForumThread.moderation_status),
        "forum_replies": _count_by_status(db, models.ForumReply, models.ForumReply.moderation_status),
    }

    daily_metrics = []
    if _admin_daily_metrics_available(db):
        metric_query = db.query(models.AdminDailyMetric)
        if start:
            metric_query = metric_query.filter(models.AdminDailyMetric.stat_date >= start)
        if end:
            metric_query = metric_query.filter(models.AdminDailyMetric.stat_date <= end)
        daily_metrics = [
            {"date": row.stat_date.isoformat(), "metrics": row.metrics or {}}
            for row in metric_query.order_by(models.AdminDailyMetric.stat_date.desc()).limit(30).all()
        ]

    return {
        "cards": {
            "total_users": db.query(models.User).count(),
            "new_users": db.query(models.User).filter(*date_f_user).count(),
            "active_premium_users": db.query(models.User).filter(models.User.premium_until != None, models.User.premium_until > now).count(),
            "suspended_users": db.query(models.User).filter(models.User.is_suspended == True).count(),
            "total_posts": db.query(models.Post).count(),
            "new_posts": db.query(models.Post).filter(*date_f_post).count(),
            "total_comments": db.query(models.Comment).count(),
            "new_comments": db.query(models.Comment).filter(*date_f_comment).count(),
            "seconds_listened": int(db.query(func.coalesce(func.sum(models.AudioListenEvent.seconds), 0)).scalar() or 0),
            "pending_moderation": moderation_stats["total_pending"],
            "flagged_moderation": moderation_stats["total_flagged"],
            "failed_jobs": jobs_by_status.get("failed", 0),
            "shop_items": db.query(models.ShopItem).count(),
        },
        "traffic": overview,
        "moderation": {"basic": moderation_stats, "extended": extended_moderation, "content_by_status": content_by_status},
        "premium": {"by_tier": premium_by_tier},
        "jobs": {"by_status": jobs_by_status},
        "audio": {"by_status": audio_by_status},
        "economy": {
            "shop_items_active": db.query(models.ShopItem).filter(models.ShopItem.is_active == True).count(),
            "inventory_items": db.query(models.UserInventoryItem).count(),
            "gologani_balance_total": int(db.query(func.coalesce(func.sum(models.User.gologani_balance), 0)).scalar() or 0),
        },
        "daily_metrics": daily_metrics,
    }


@router.post("/metrics/rollup")
def rollup_admin_metrics(
    request: Request,
    target_date: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    parsed = _parse_date(target_date) or (date.today() - timedelta(days=1))
    row = aggregate_admin_daily_metrics(db, parsed)
    _audit(db, request, current_user, action="admin_metrics_rollup", target_type="admin_daily_metric", target_id=getattr(row, "id", None), metadata={"date": parsed.isoformat()})
    return {"date": row.stat_date.isoformat(), "metrics": row.metrics or {}, "persisted": getattr(row, "id", None) is not None}


@router.get("/users")
def list_admin_users(
    q: str = "",
    role: str = "all",
    status_filter: str = Query("all", alias="status"),
    premium: str = "all",
    joined_from: Optional[str] = Query(None),
    joined_to: Optional[str] = Query(None),
    last_login_from: Optional[str] = Query(None),
    last_login_to: Optional[str] = Query(None),
    min_posts: Optional[int] = Query(None, ge=0),
    max_posts: Optional[int] = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if min_posts is not None and max_posts is not None and min_posts > max_posts:
        raise HTTPException(status_code=400, detail="Numărul minim de postări nu poate depăși maximul.")
    query = _apply_admin_user_filters(
        db,
        db.query(models.User),
        q=q,
        role=role,
        status_filter=status_filter,
        premium=premium,
        joined_from=_parse_date(joined_from),
        joined_to=_parse_date(joined_to),
        last_login_from=_parse_date(last_login_from),
        last_login_to=_parse_date(last_login_to),
        min_posts=min_posts,
        max_posts=max_posts,
    )
    total = query.count()
    users = query.order_by(models.User.created_at.desc(), models.User.id.desc()).offset(offset).limit(limit).all()
    return {"users": [_user_payload(db, user, include_counts=True) for user in users], "total": total}


@router.post("/email/preview")
def preview_admin_email(
    data: schemas.AdminEmailPreviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    recipients, matched_count = _admin_email_recipients(db, data.audience)
    sample = recipients[:10]
    return {
        "matched_count": matched_count,
        "recipient_count": len(recipients),
        "sample": [_user_payload(db, user, include_counts=True) for user in sample],
    }


@router.post("/email/campaigns")
def create_admin_email_campaign(
    data: schemas.AdminEmailCampaignCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    recipients, matched_count = _admin_email_recipients(db, data.audience)
    if not recipients:
        raise HTTPException(status_code=400, detail="Nu există destinatari eligibili pentru această campanie.")
    campaign = email_service.queue_admin_campaign(
        db,
        actor=current_user,
        subject=data.subject.strip(),
        html_content=data.html_content,
        recipients=recipients,
        filters=_audience_filters_dict(data.audience),
        selected_user_ids=data.audience.selected_user_ids,
        matched_count=matched_count,
    )
    _audit(
        db,
        request,
        current_user,
        action="admin_email_campaign_queue",
        target_type="email_campaign",
        target_id=campaign.id,
        metadata={
            "subject": campaign.subject,
            "matched_count": matched_count,
            "recipient_count": campaign.recipient_count,
            "queued_count": campaign.queued_count,
            "filters": campaign.filters or {},
        },
    )
    return {
        "id": campaign.id,
        "matched_count": campaign.matched_count,
        "recipient_count": campaign.recipient_count,
        "queued_count": campaign.queued_count,
        "status": campaign.status,
    }


@router.get("/email/campaigns")
def list_admin_email_campaigns(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    campaigns = db.query(models.EmailCampaign).order_by(models.EmailCampaign.created_at.desc(), models.EmailCampaign.id.desc()).limit(limit).all()
    payload = []
    for campaign in campaigns:
        sent_count = db.query(models.EmailOutbox).filter(
            models.EmailOutbox.campaign_id == campaign.id,
            models.EmailOutbox.status == "sent",
        ).count()
        failed_count = db.query(models.EmailOutbox).filter(
            models.EmailOutbox.campaign_id == campaign.id,
            models.EmailOutbox.status == "failed",
        ).count()
        queued_count = db.query(models.EmailOutbox).filter(
            models.EmailOutbox.campaign_id == campaign.id,
            models.EmailOutbox.status.in_(("queued", "sending")),
        ).count()
        payload.append({
            "id": campaign.id,
            "subject": campaign.subject,
            "actor_user_id": campaign.actor_user_id,
            "matched_count": campaign.matched_count,
            "recipient_count": campaign.recipient_count,
            "queued_count": campaign.queued_count,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "pending_count": queued_count,
            "status": campaign.status,
            "created_at": _as_iso(campaign.created_at),
        })
    return {"campaigns": payload}


@router.post("/email/outbox/process")
def process_admin_email_outbox(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    processed = email_service.process_email_outbox(db, limit=limit, worker=f"admin:{current_user.id}")
    pending_count = db.query(models.EmailOutbox).filter(models.EmailOutbox.status.in_(("queued", "sending"))).count()
    sent_count = db.query(models.EmailOutbox).filter(models.EmailOutbox.status == "sent").count()
    failed_count = db.query(models.EmailOutbox).filter(models.EmailOutbox.status == "failed").count()
    skipped_count = db.query(models.EmailOutbox).filter(models.EmailOutbox.status == "skipped").count()
    _audit(
        db,
        request,
        current_user,
        action="admin_email_outbox_process",
        target_type="email_outbox",
        metadata={
            "limit": limit,
            "processed": processed,
            "pending_count": pending_count,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
        },
    )
    return {
        "processed": processed,
        "pending_count": pending_count,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
    }


@router.post("/email/test-notification")
def send_admin_notification_test_email(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    row = email_service.queue_test_notification_email(db, actor=current_user)
    if not row:
        raise HTTPException(status_code=500, detail="Nu am putut crea emailul de test.")
    sent = email_service.send_queued_email_now(db, row, worker=f"admin-test-notification:{current_user.id}")
    db.refresh(row)
    _audit(
        db,
        request,
        current_user,
        action="admin_email_test_notification",
        target_type="email_outbox",
        target_id=row.id,
        metadata={
            "recipient_email": row.recipient_email,
            "subject": row.subject,
            "status": row.status,
            "sent": sent,
            "emails_enabled": email_service.emails_enabled(),
        },
    )
    return {
        "id": row.id,
        "recipient_email": row.recipient_email,
        "subject": row.subject,
        "status": row.status,
        "sent": sent,
        "emails_enabled": email_service.emails_enabled(),
    }


@router.get("/users/{user_id}")
def get_admin_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    recent_posts = db.query(models.Post).filter(models.Post.user_id == user.id).order_by(models.Post.created_at.desc()).limit(10).all()
    transactions = db.query(models.GologaniTransaction).filter(models.GologaniTransaction.user_id == user.id).order_by(models.GologaniTransaction.created_at.desc()).limit(20).all()
    audits = []
    if _admin_audit_logs_available(db):
        audits = db.query(models.AdminAuditLog).filter(models.AdminAuditLog.target_type == "user", models.AdminAuditLog.target_id == user.id).order_by(models.AdminAuditLog.created_at.desc()).limit(20).all()
    return {
        "user": _user_payload(db, user, include_counts=True),
        "recent_posts": [_content_payload(post, "post") for post in recent_posts],
        "transactions": [
            {
                "id": tx.id,
                "amount": tx.amount,
                "balance_after": tx.balance_after,
                "event_type": tx.event_type,
                "description": tx.description,
                "created_at": _as_iso(tx.created_at),
            }
            for tx in transactions
        ],
        "audit": [_audit_payload(log, db) for log in audits],
    }


@router.put("/users/{user_id}/roles")
def update_admin_user_roles(
    user_id: int,
    data: schemas.AdminRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    if user.is_admin and not data.is_admin:
        _ensure_can_remove_admin(db, user)
    if current_user.id == user.id and not data.is_admin:
        raise HTTPException(status_code=400, detail="Nu îți poți elimina propriul rol de administrator.")
    before = {"is_admin": user.is_admin, "is_moderator": user.is_moderator}
    user.is_admin = data.is_admin
    user.is_moderator = data.is_moderator or data.is_admin
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_roles_update", target_type="user", target_id=user.id, reason=data.reason, metadata={"before": before, "after": {"is_admin": user.is_admin, "is_moderator": user.is_moderator}})
    return _user_payload(db, user, include_counts=True)


@router.post("/users/{user_id}/suspend")
def suspend_admin_user(
    user_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    _ensure_not_self(current_user, user, "suspendare")
    _ensure_can_remove_admin(db, user)
    user.is_suspended = True
    user.suspension_reason = data.reason
    user.suspended_at = utcnow_naive()
    user.suspended_by = current_user.id
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_suspend", target_type="user", target_id=user.id, reason=data.reason)
    return _user_payload(db, user, include_counts=True)


@router.post("/users/{user_id}/reactivate")
def reactivate_admin_user(
    user_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    user.is_suspended = False
    user.suspension_reason = None
    user.suspended_at = None
    user.suspended_by = None
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_reactivate", target_type="user", target_id=user.id, reason=data.reason)
    return _user_payload(db, user, include_counts=True)


@router.put("/users/{user_id}/premium")
def update_admin_user_premium(
    user_id: int,
    data: schemas.AdminPremiumUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    before = {
        "premium_tier": user.premium_tier,
        "premium_until": _as_iso(user.premium_until),
        "stripe_subscription_id": user.stripe_subscription_id,
    }
    if data.premium_tier == "free":
        user.premium_tier = "free"
        user.premium_period_start = None
        user.premium_until = None
        user.stripe_subscription_id = None
    else:
        user.premium_tier = data.premium_tier
        user.premium_period_start = data.premium_period_start or user.premium_period_start or utcnow_naive()
        user.premium_until = data.premium_until or (utcnow_naive() + timedelta(days=30))
        if data.stripe_subscription_id is not None:
            user.stripe_subscription_id = data.stripe_subscription_id
    db.commit()
    db.refresh(user)
    _audit(db, request, current_user, action="user_premium_update", target_type="user", target_id=user.id, reason=data.reason, metadata={"before": before, "after": {"premium_tier": user.premium_tier, "premium_until": _as_iso(user.premium_until), "stripe_subscription_id": user.stripe_subscription_id}})
    return _user_payload(db, user, include_counts=True)


@router.post("/users/{user_id}/gologani-adjustments")
def adjust_admin_user_gologani(
    user_id: int,
    data: schemas.AdminGologaniAdjustment,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    tx = crud.grant_gologani(
        db,
        user_id=user.id,
        amount=data.amount,
        event_type="admin_adjustment",
        idempotency_key=f"admin-adjustment:{current_user.id}:{user.id}:{uuid4()}",
        source_type="admin",
        source_id=current_user.id,
        description=data.reason,
        extra_data={"admin_username": current_user.username},
    )
    db.refresh(user)
    _audit(db, request, current_user, action="user_gologani_adjust", target_type="user", target_id=user.id, reason=data.reason, metadata={"amount": data.amount, "transaction_id": tx.id if tx else None})
    return {"user": _user_payload(db, user, include_counts=True), "transaction_id": tx.id if tx else None}


@router.delete("/users/{user_id}")
def delete_admin_user(
    user_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    _ensure_not_self(current_user, user, "ștergere")
    _ensure_can_remove_admin(db, user)
    metadata = {"username": user.username, "email": user.email}
    db.expunge(user)
    try:
        deleted_content = _delete_user_owned_content(db, user_id)
        deleted_count = (
            db.query(models.User)
            .filter(models.User.id == user_id)
            .delete(synchronize_session=False)
        )
        if not deleted_count:
            db.rollback()
            raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
        db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not delete admin user %s", user_id)
        raise HTTPException(status_code=500, detail="Nu am putut șterge utilizatorul.") from exc
    _audit(db, request, current_user, action="user_delete", target_type="user", target_id=user_id, reason=data.reason, metadata={**metadata, "deleted_content": deleted_content})
    return {"success": True}


@router.get("/storage/objects")
def list_admin_storage_objects(
    prefix: str = "",
    q: str = "",
    status_filter: str = Query("all", alias="status"),
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if status_filter not in STORAGE_STATUS_FILTERS:
        raise HTTPException(status_code=400, detail="Filtru de stocare invalid")
    prefix = prefix.strip()
    term = q.strip().lower()
    references = _storage_reference_map(db)
    try:
        page = object_storage.list_objects(prefix=prefix, continuation_token=cursor, max_keys=limit)
    except RuntimeError as exc:
        raise _storage_error("Stocarea de obiecte nu este configurată.", exc)
    except Exception as exc:
        raise _storage_error("Nu am putut citi obiectele din bucket.", exc)

    objects = []
    for raw in page["objects"]:
        payload = _storage_object_payload(raw, references)
        if term and term not in payload["key"].lower():
            continue
        if not _matches_storage_status(payload, status_filter):
            continue
        objects.append(payload)

    return {
        "objects": objects,
        "next_cursor": page.get("next_cursor"),
        "is_truncated": page.get("is_truncated", False),
        "summary": {
            "raw_count": len(page["objects"]),
            "listed_count": len(objects),
            "referenced_count": sum(1 for item in objects if item["references"]),
            "deletable_count": sum(1 for item in objects if item["can_delete"]),
        },
    }


@router.post("/storage/objects/presign")
def presign_admin_storage_object(
    data: schemas.AdminStorageObjectRequest,
    current_user: models.User = Depends(admin.require_admin),
):
    try:
        return {
            "key": data.key,
            "url": object_storage.presigned_get_url(data.key),
            "expires_in": object_storage.signed_url_ttl_seconds(),
        }
    except RuntimeError as exc:
        raise _storage_error("Stocarea de obiecte nu este configurată.", exc)
    except Exception as exc:
        raise _storage_error("Nu am putut genera linkul obiectului.", exc)


@router.delete("/storage/objects")
def delete_admin_storage_object(
    data: schemas.AdminStorageObjectDelete,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    key = data.key
    references = _storage_reference_map(db).get(key, [])
    prefix_type = _storage_prefix_type(key)
    if references:
        raise HTTPException(status_code=409, detail="Obiectul este încă folosit în baza de date.")
    if prefix_type == "outside":
        raise HTTPException(status_code=400, detail="Obiectele din afara prefixelor Călimara sunt doar vizibile.")

    object_metadata = {}
    try:
        object_metadata = object_storage.head_object_metadata(key)
    except Exception:
        logger.info("Could not read object metadata before delete: %s", key, exc_info=True)

    try:
        object_storage.delete_object(key)
    except RuntimeError as exc:
        raise _storage_error("Stocarea de obiecte nu este configurată.", exc)
    except Exception as exc:
        raise _storage_error("Nu am putut șterge obiectul din bucket.", exc)

    _audit(
        db,
        request,
        current_user,
        action="storage_object_delete",
        target_type="storage_object",
        reason=data.reason,
        metadata={
            "key": key,
            "prefix_type": prefix_type,
            "size": object_metadata.get("ContentLength"),
            "content_type": object_metadata.get("ContentType"),
            "etag": str(object_metadata.get("ETag") or "").strip('"'),
            "last_modified": _serialize_storage_time(object_metadata.get("LastModified")),
        },
    )
    return {"success": True, "key": key}


@router.post("/storage/objects/cleanup")
def cleanup_admin_storage_object(
    data: schemas.AdminStorageObjectCleanup,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    key = data.key
    prefix_type = _storage_prefix_type(key)
    references = _storage_reference_map(db).get(key, [])
    object_metadata = {}
    try:
        object_metadata = object_storage.head_object_metadata(key)
    except Exception:
        logger.info("Could not read object metadata before cleanup: %s", key, exc_info=True)

    cleanup = _cleanup_storage_references(db, key, data.reason)
    try:
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Could not clear object references before cleanup: %s", key, exc_info=True)
        raise HTTPException(status_code=500, detail="Nu am putut curăța referințele obiectului.") from exc

    try:
        object_storage.delete_object(key)
    except RuntimeError as exc:
        db.rollback()
        raise _storage_error("Stocarea de obiecte nu este configurată.", exc)
    except Exception as exc:
        db.rollback()
        raise _storage_error("Nu am putut șterge obiectul din bucket.", exc)

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Object was deleted but reference cleanup could not be committed: %s", key)
        raise HTTPException(
            status_code=500,
            detail="Obiectul a fost șters din bucket, dar nu am putut salva curățarea referințelor.",
        ) from exc

    metadata = {
        "key": key,
        "prefix_type": prefix_type,
        **_storage_metadata_payload(object_metadata),
        "references": references,
        "cleanup": cleanup,
    }
    _audit(
        db,
        request,
        current_user,
        action="storage_object_cleanup",
        target_type="storage_object",
        reason=data.reason,
        metadata=metadata,
    )
    return {
        "success": True,
        "key": key,
        "references_removed": cleanup["total"],
        "references": references,
        "cleanup": cleanup,
        "object": _storage_metadata_payload(object_metadata),
    }


@router.get("/content")
def list_admin_content(
    content_type: str = "all",
    status_filter: str = Query("all", alias="status"),
    q: str = "",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if content_type != "all" and content_type not in CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Tip de conținut invalid")
    if status_filter != "all" and status_filter not in CONTENT_STATUSES and status_filter not in {"ready", "failed", "processing", "cancelled"}:
        raise HTTPException(status_code=400, detail="Status invalid")
    term = q.strip()
    items = []

    def add_rows(rows, kind):
        items.extend(_content_payload(row, kind) for row in rows)

    if content_type in {"all", "post"}:
        query = db.query(models.Post).options(joinedload(models.Post.owner))
        if status_filter != "all":
            query = query.filter(models.Post.moderation_status == status_filter)
        if term:
            like = f"%{term}%"
            query = query.filter(or_(models.Post.title.ilike(like), models.Post.content.ilike(like)))
        add_rows(query.order_by(models.Post.created_at.desc()).limit(limit).offset(offset if content_type == "post" else 0).all(), "post")
    if content_type in {"all", "comment"}:
        query = db.query(models.Comment).options(
            joinedload(models.Comment.commenter),
            joinedload(models.Comment.post).joinedload(models.Post.owner),
        )
        if status_filter != "all":
            query = query.filter(models.Comment.moderation_status == status_filter)
        if term:
            query = query.filter(models.Comment.content.ilike(f"%{term}%"))
        add_rows(query.order_by(models.Comment.created_at.desc()).limit(limit).offset(offset if content_type == "comment" else 0).all(), "comment")
    if content_type in {"all", "audio"}:
        query = db.query(models.PostAudio).options(joinedload(models.PostAudio.post).joinedload(models.Post.owner))
        if status_filter != "all":
            query = query.filter(models.PostAudio.status == status_filter)
        if term:
            query = query.filter(models.PostAudio.transcript.ilike(f"%{term}%"))
        add_rows(query.order_by(models.PostAudio.created_at.desc()).limit(limit).offset(offset if content_type == "audio" else 0).all(), "audio")
    if content_type in {"all", "forum_thread"}:
        query = db.query(models.ForumThread).options(joinedload(models.ForumThread.author))
        if status_filter != "all":
            query = query.filter(models.ForumThread.moderation_status == status_filter)
        if term:
            like = f"%{term}%"
            query = query.filter(or_(models.ForumThread.title.ilike(like), models.ForumThread.content.ilike(like)))
        add_rows(query.order_by(models.ForumThread.created_at.desc()).limit(limit).offset(offset if content_type == "forum_thread" else 0).all(), "forum_thread")
    if content_type in {"all", "forum_reply"}:
        query = db.query(models.ForumReply).options(joinedload(models.ForumReply.author), joinedload(models.ForumReply.thread))
        if status_filter != "all":
            query = query.filter(models.ForumReply.moderation_status == status_filter)
        if term:
            query = query.filter(models.ForumReply.content.ilike(f"%{term}%"))
        add_rows(query.order_by(models.ForumReply.created_at.desc()).limit(limit).offset(offset if content_type == "forum_reply" else 0).all(), "forum_reply")
    if content_type in {"all", "theatre_entry"}:
        query = db.query(models.TheatreEntry).options(
            joinedload(models.TheatreEntry.author),
            joinedload(models.TheatreEntry.play),
            joinedload(models.TheatreEntry.scene),
            joinedload(models.TheatreEntry.character),
        )
        if status_filter != "all":
            query = query.filter(models.TheatreEntry.moderation_status == status_filter)
        if term:
            query = query.filter(models.TheatreEntry.content.ilike(f"%{term}%"))
        add_rows(query.order_by(models.TheatreEntry.created_at.desc()).limit(limit).offset(offset if content_type == "theatre_entry" else 0).all(), "theatre_entry")
    if content_type in {"all", "stafeta_segment"}:
        query = db.query(models.StafetaSegment).options(
            joinedload(models.StafetaSegment.author),
            joinedload(models.StafetaSegment.work),
        )
        if status_filter != "all":
            query = query.filter(models.StafetaSegment.moderation_status == status_filter)
        if term:
            query = query.filter(models.StafetaSegment.content.ilike(f"%{term}%"))
        add_rows(query.order_by(models.StafetaSegment.created_at.desc()).limit(limit).offset(offset if content_type == "stafeta_segment" else 0).all(), "stafeta_segment")

    items.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    if content_type == "all":
        items = items[offset:offset + limit]
    return {"content": items, "total": len(items)}


@router.get("/content/{content_type}/{content_id}")
def get_admin_content_detail(
    content_type: schemas.AdminContentType,
    content_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = _content_object(db, content_type, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    return _content_payload(item, content_type)


@router.put("/content/{content_type}/{content_id}")
def update_admin_content(
    content_type: schemas.AdminContentType,
    content_id: int,
    data: schemas.AdminContentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = _content_object(db, content_type, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    changed = {}
    for field in ("title", "content", "category", "section"):
        value = getattr(data, field)
        if value is not None and hasattr(item, field):
            changed[field] = {"before": getattr(item, field), "after": value}
            setattr(item, field, value)
    if data.moderation_status in {"approved", "rejected"}:
        db.commit()
        item = crud.approve_content(db, content_type, content_id, current_user.id, data.reason) if data.moderation_status == "approved" else crud.reject_content(db, content_type, content_id, current_user.id, data.reason)
    else:
        if data.moderation_status:
            if content_type == "audio":
                item.status = data.moderation_status
            elif hasattr(item, "moderation_status"):
                item.moderation_status = data.moderation_status
            if hasattr(item, "moderation_reason"):
                item.moderation_reason = data.reason
        db.commit()
        db.refresh(item)
    _audit(db, request, current_user, action="content_update", target_type=content_type, target_id=content_id, reason=data.reason, metadata={"changed": changed, "moderation_status": data.moderation_status})
    refreshed = _content_object(db, content_type, content_id)
    return _content_payload(refreshed, content_type)


@router.post("/content/{content_type}/{content_id}/moderate")
def moderate_admin_content(
    content_type: schemas.AdminContentType,
    content_id: int,
    data: schemas.ModerationActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if data.action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    result = crud.approve_content(db, content_type, content_id, current_user.id, data.reason) if data.action == "approve" else crud.reject_content(db, content_type, content_id, current_user.id, data.reason)
    if not result:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    _audit(db, request, current_user, action=f"content_{data.action}", target_type=content_type, target_id=content_id, reason=data.reason)
    return _content_payload(_content_object(db, content_type, content_id), content_type)


@router.delete("/content/{content_type}/{content_id}")
def delete_admin_content(
    content_type: schemas.AdminContentType,
    content_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = _content_object(db, content_type, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conținutul nu a fost găsit")
    snapshot = _content_payload(item, content_type)
    db.delete(item)
    db.commit()
    _audit(db, request, current_user, action="content_delete", target_type=content_type, target_id=content_id, reason=data.reason, metadata={"snapshot": {k: snapshot.get(k) for k in ("title", "author", "status")}})
    return {"success": True}


@router.get("/jobs")
def list_admin_jobs(
    status_filter: str = Query("all", alias="status"),
    job_type: str = "all",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    query = db.query(models.AIJob)
    if status_filter != "all":
        query = query.filter(models.AIJob.status == status_filter)
    if job_type != "all":
        query = query.filter(models.AIJob.job_type == job_type)
    total = query.count()
    jobs = query.order_by(models.AIJob.created_at.desc(), models.AIJob.id.desc()).offset(offset).limit(limit).all()
    return {"jobs": [_job_payload(job, db) for job in jobs], "total": total}


@router.post("/jobs/{job_id}/retry")
def retry_admin_job(
    job_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    job = db.query(models.AIJob).filter(models.AIJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Jobul nu a fost găsit")
    job.status = "pending"
    job.attempts = 0
    job.locked_at = None
    job.locked_by = None
    job.error_message = None
    job.run_after = utcnow_naive()
    db.commit()
    db.refresh(job)
    _audit(db, request, current_user, action="ai_job_retry", target_type="ai_job", target_id=job.id, reason=data.reason)
    return _job_payload(job, db)


@router.post("/jobs/{job_id}/cancel")
def cancel_admin_job(
    job_id: int,
    data: schemas.AdminReasonRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    job = db.query(models.AIJob).filter(models.AIJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Jobul nu a fost găsit")
    job.status = "cancelled"
    job.locked_at = None
    job.locked_by = None
    job.error_message = data.reason
    db.commit()
    db.refresh(job)
    _audit(db, request, current_user, action="ai_job_cancel", target_type="ai_job", target_id=job.id, reason=data.reason)
    return _job_payload(job, db)


@router.get("/platform-access")
def get_platform_access(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    return _platform_access_payload(db)


@router.put("/platform-access")
def update_platform_access(
    data: schemas.AdminPlatformAccessUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    before = platform_access.is_platform_open(db)
    setting = platform_access.set_platform_open(db, is_open=data.open, actor=current_user)
    _audit(
        db,
        request,
        current_user,
        action="platform_access_update",
        target_type="platform_access_settings",
        target_id=setting.id,
        metadata={"before": {"open": before}, "after": {"open": setting.is_open}},
    )
    return _platform_access_payload(db)


@router.post("/platform-access/emails")
def add_platform_allowed_email(
    data: schemas.AdminPlatformAllowedEmailCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    try:
        item = platform_access.add_allowed_email(db, email=str(data.email), note=data.note, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _audit(
        db,
        request,
        current_user,
        action="platform_allowed_email_create",
        target_type="platform_allowed_email",
        target_id=item.id,
        metadata={"email": item.email, "note": item.note},
    )
    return _platform_access_payload(db)


@router.get("/invitatii")
def list_platform_invitations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    return {"invitations": [_platform_invitation_payload(item) for item in invitations.list_invitations(db)]}


@router.post("/invitatii")
def create_platform_invitations(
    data: schemas.AdminInvitationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    results = []
    invited_ids = []
    created_count = 0
    updated_count = 0
    skipped_count = 0
    seen_emails = set()
    for raw_email in data.emails:
        email = invitations.normalize_invitation_email(str(raw_email))
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        existing_user = crud.get_user_by_email(db, email)
        if existing_user:
            skipped_count += 1
            results.append({"email": email, "status": "skipped", "reason": "existing_user"})
            continue
        try:
            invitation, token, temporary_password, action = invitations.upsert_invitation(
                db,
                email=email,
                premium_tier=data.premium_tier,
                premium_days=data.premium_days,
                note=data.note,
                actor=current_user,
            )
        except ValueError as exc:
            skipped_count += 1
            results.append({"email": email, "status": "skipped", "reason": str(exc)})
            continue
        _queue_platform_invitation(
            db,
            invitation=invitation,
            token=token,
            temporary_password=temporary_password,
            actor=current_user,
        )
        invited_ids.append(invitation.id)
        if action == "created":
            created_count += 1
        else:
            updated_count += 1
        results.append({"email": email, "status": action, "invitation_id": invitation.id})

    if not results:
        raise HTTPException(status_code=400, detail="Nu există invitații noi de trimis.")
    _audit(
        db,
        request,
        current_user,
        action="platform_invitations_create",
        target_type="platform_invitation",
        metadata={
            "invitation_ids": invited_ids,
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "premium_tier": data.premium_tier,
            "premium_days": data.premium_days,
        },
    )
    return {
        **_platform_access_payload(db),
        "results": results,
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
    }


@router.post("/invitatii/{invitation_id}/retrimite")
def resend_platform_invitation(
    invitation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    invitation = invitations.get_invitation(db, invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitația nu a fost găsită.")
    try:
        invitation, token, temporary_password = invitations.rotate_invitation(db, invitation)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _queue_platform_invitation(
        db,
        invitation=invitation,
        token=token,
        temporary_password=temporary_password,
        actor=current_user,
    )
    _audit(
        db,
        request,
        current_user,
        action="platform_invitation_resend",
        target_type="platform_invitation",
        target_id=invitation.id,
        metadata={"email": invitation.email},
    )
    return _platform_access_payload(db)


@router.post("/invitatii/{invitation_id}/revoca")
def revoke_platform_invitation(
    invitation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    invitation = invitations.get_invitation(db, invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitația nu a fost găsită.")
    try:
        invitations.revoke_invitation(db, invitation)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _audit(
        db,
        request,
        current_user,
        action="platform_invitation_revoke",
        target_type="platform_invitation",
        target_id=invitation.id,
        metadata={"email": invitation.email},
    )
    return _platform_access_payload(db)


@router.delete("/platform-access/emails/{email_id}")
def delete_platform_allowed_email(
    email_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = db.query(models.PlatformAllowedEmail).filter(models.PlatformAllowedEmail.id == email_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Emailul nu este în lista de acces.")
    snapshot = {"email": item.email, "note": item.note}
    db.delete(item)
    db.commit()
    _audit(
        db,
        request,
        current_user,
        action="platform_allowed_email_delete",
        target_type="platform_allowed_email",
        target_id=email_id,
        metadata=snapshot,
    )
    return _platform_access_payload(db)


@router.get("/site-feedback")
def list_site_feedback(
    kind: str = Query("all"),
    status_filter: str = Query("open", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    qa_report_filter = _qa_report_feedback_filter()
    query = (
        db.query(models.SiteFeedback)
        .options(joinedload(models.SiteFeedback.resolver))
        .filter(~qa_report_filter)
    )
    if kind != "all":
        if kind not in {"feedback", "bug"}:
            raise HTTPException(status_code=400, detail="Tip de sesizare invalid.")
        query = query.filter(models.SiteFeedback.kind == kind)
    if status_filter != "all":
        if status_filter not in {"open", "closed"}:
            raise HTTPException(status_code=400, detail="Status de sesizare invalid.")
        if status_filter == "open":
            unread_reply_ids = _admin_site_feedback_unread_reply_ids(db)
            query = query.filter(
                or_(
                    models.SiteFeedback.status == "open",
                    models.SiteFeedback.id.in_(unread_reply_ids),
                )
            )
        else:
            query = query.filter(models.SiteFeedback.status == status_filter)
    total = query.count()
    unread_reply_ids = _admin_site_feedback_unread_reply_ids(db)
    submissions = (
        query.order_by(
            case((models.SiteFeedback.id.in_(unread_reply_ids), 0), else_=1),
            models.SiteFeedback.created_at.desc(),
            models.SiteFeedback.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "submissions": [_site_feedback_payload(item, db) for item in submissions],
        "total": total,
        "open_count": db.query(models.SiteFeedback).filter(~qa_report_filter, models.SiteFeedback.status == "open").count(),
        "closed_count": db.query(models.SiteFeedback).filter(~qa_report_filter, models.SiteFeedback.status == "closed").count(),
        "unread_reply_count": _admin_site_feedback_unread_reply_count(db),
    }


@router.get("/site-feedback/{feedback_id}/thread")
def get_site_feedback_thread(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = (
        db.query(models.SiteFeedback)
        .options(joinedload(models.SiteFeedback.resolver))
        .filter(models.SiteFeedback.id == feedback_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Sesizarea nu a fost găsită.")
    if _mark_site_feedback_replies_as_read(db, item):
        db.commit()
        db.refresh(item)
    return _site_feedback_thread_payload(db, item)


@router.post("/site-feedback/{feedback_id}/reply")
def reply_to_site_feedback(
    feedback_id: int,
    data: schemas.SiteFeedbackReplyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = (
        db.query(models.SiteFeedback)
        .options(joinedload(models.SiteFeedback.resolver))
        .filter(models.SiteFeedback.id == feedback_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Sesizarea nu a fost găsită.")

    try:
        _mark_site_feedback_replies_as_read(db, item)
        message = crud.reply_to_site_feedback(db, item, admin_user=current_user, content=data.content)
        db.commit()
        db.refresh(item)
        db.refresh(message)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not send support reply for site feedback %s", feedback_id)
        raise HTTPException(status_code=500, detail="Nu am putut trimite răspunsul.")

    _audit(
        db,
        request,
        current_user,
        action="site_feedback_reply",
        target_type="site_feedback",
        target_id=item.id,
        reason="Răspuns trimis prin mesaj direct",
        metadata={
            "conversation_id": item.support_conversation_id,
            "message_id": message.id,
            "recipient_user_id": item.user_id,
        },
    )
    db.refresh(item)
    return _site_feedback_thread_payload(db, item)


@router.get("/referinta/raport-qa")
def list_admin_reference_qa_report(
    status_filter: str = Query("all", alias="status"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if status_filter != "all":
        if status_filter not in {"open", "closed"}:
            raise HTTPException(status_code=400, detail="Status de raport invalid.")
    qa_report_filter = _qa_report_feedback_filter()
    query = (
        db.query(models.SiteFeedback)
        .options(joinedload(models.SiteFeedback.resolver))
        .filter(qa_report_filter)
    )
    if status_filter != "all":
        query = query.filter(models.SiteFeedback.status == status_filter)
    total = query.count()
    entries = (
        query.order_by(models.SiteFeedback.created_at.desc(), models.SiteFeedback.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "entries": [_qa_report_feedback_payload(item) for item in entries],
        "total": total,
        "open_count": db.query(models.SiteFeedback).filter(qa_report_filter, models.SiteFeedback.status == "open").count(),
        "closed_count": db.query(models.SiteFeedback).filter(qa_report_filter, models.SiteFeedback.status == "closed").count(),
    }


@router.put("/site-feedback/{feedback_id}")
def update_site_feedback(
    feedback_id: int,
    data: schemas.SiteFeedbackUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    item = (
        db.query(models.SiteFeedback)
        .options(joinedload(models.SiteFeedback.resolver))
        .filter(models.SiteFeedback.id == feedback_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Sesizarea nu a fost găsită.")

    before = {"status": item.status, "admin_note": item.admin_note}
    item.status = data.status
    if "admin_note" in data.model_fields_set:
        item.admin_note = data.admin_note
    if data.status == "closed":
        item.resolved_by = current_user.id
        item.resolved_at = utcnow_naive()
    else:
        item.resolved_by = None
        item.resolved_at = None

    db.commit()
    db.refresh(item)
    _audit(
        db,
        request,
        current_user,
        action="site_feedback_update",
        target_type="site_feedback",
        target_id=item.id,
        reason=item.admin_note,
        metadata={"before": before, "after": {"status": item.status, "admin_note": item.admin_note}},
    )
    db.refresh(item)
    return _site_feedback_payload(item, db)


@router.get("/audit-log")
def list_admin_audit_log(
    actor: str = "",
    action: str = "",
    target_type: str = "",
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if not _admin_audit_logs_available(db):
        return {"logs": [], "total": 0, "unavailable": True}
    query = db.query(models.AdminAuditLog)
    if actor:
        query = query.filter(models.AdminAuditLog.actor_username.ilike(f"%{actor.strip()}%"))
    if action:
        query = query.filter(models.AdminAuditLog.action == action)
    if target_type:
        query = query.filter(models.AdminAuditLog.target_type == target_type)
    total = query.count()
    logs = query.order_by(models.AdminAuditLog.created_at.desc(), models.AdminAuditLog.id.desc()).offset(offset).limit(limit).all()
    return {"logs": [_audit_payload(log, db) for log in logs], "total": total}
