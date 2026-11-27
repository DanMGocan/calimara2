import calendar
from datetime import timezone
from zoneinfo import ZoneInfo

from ._shared import *

AUDIO_TTS_MONTHLY_QUOTAS = {
    "free": 1_000,
    "trubadur": 25_000,
    "cronicar": 50_000,
    "rapsod": 100_000,
}

AUDIO_LISTEN_MODES = {"poezie", "proza_scurta", "toate"}
AUDIO_LISTEN_CONTEXTS = {"player", "post"}
FREE_PLAYER_LISTEN_SECONDS_PER_DAY = 20 * 60
PLAYER_QUOTA_TIMEZONE = ZoneInfo("Europe/Bucharest")
TTS_AUDIO_JOB_TYPE = "tts_audio_generation"
ACTIVE_TTS_JOB_STATUSES = ("pending", "processing")

# ===================================
# USER CRUD FUNCTIONS
# ===================================

def get_best_audio_for_post(db: Session, post_id: int) -> Optional[models.PostAudio]:
    author_audio = (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "author",
            models.PostAudio.status == "ready",
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )
    if author_audio:
        return author_audio
    return (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "tts",
            models.PostAudio.status == "ready",
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )

def get_latest_audio_for_post(db: Session, post_id: int) -> Optional[models.PostAudio]:
    return (
        db.query(models.PostAudio)
        .filter(models.PostAudio.post_id == post_id, models.PostAudio.deleted_at.is_(None))
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )

def get_latest_author_audio_for_post(db: Session, post_id: int) -> Optional[models.PostAudio]:
    return (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "author",
            models.PostAudio.status != "cancelled",
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )

def create_post_audio(
    db: Session,
    post_id: int,
    source: str,
    status: str = "pending",
    **fields,
) -> models.PostAudio:
    audio = models.PostAudio(post_id=post_id, source=source, status=status, **fields)
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return audio

def cancel_non_ready_author_audio_for_post(
    db: Session, post_id: int, exclude_audio_id: Optional[int] = None
) -> int:
    query = db.query(models.PostAudio).filter(
        models.PostAudio.post_id == post_id,
        models.PostAudio.source == "author",
        models.PostAudio.status.in_(["pending", "processing", "flagged", "failed"]),
    )
    if exclude_audio_id is not None:
        query = query.filter(models.PostAudio.id != exclude_audio_id)
    updated = query.update(
        {
            "status": "cancelled",
            "moderation_status": "cancelled",
            "moderation_reason": "Înregistrarea a fost înlocuită de autor",
            "updated_at": func.now(),
        },
        synchronize_session=False,
    )
    if updated:
        db.commit()
    return updated

def update_post_audio(db: Session, audio_id: int, **fields) -> Optional[models.PostAudio]:
    audio = db.query(models.PostAudio).filter(models.PostAudio.id == audio_id).first()
    if not audio:
        return None
    for key, value in fields.items():
        setattr(audio, key, value)
    db.commit()
    db.refresh(audio)
    return audio

def get_pending_tts_audio_jobs(db: Session, limit: int = 10) -> List[models.PostAudio]:
    return (
        db.query(models.PostAudio)
        .join(models.Post)
        .filter(
            models.PostAudio.source == "tts",
            models.PostAudio.status == "pending",
            models.PostAudio.requester_user_id.isnot(None),
            models.Post.moderation_status == "approved",
        )
        .order_by(models.PostAudio.created_at.asc(), models.PostAudio.id.asc())
        .limit(limit)
        .all()
    )

def get_active_or_ready_tts_for_post(db: Session, post_id: int) -> Optional[models.PostAudio]:
    active_retry_job_exists = exists().where(
        and_(
            models.AIJob.job_type == TTS_AUDIO_JOB_TYPE,
            models.AIJob.target_type == "audio",
            models.AIJob.target_id == models.PostAudio.id,
            models.AIJob.status.in_(ACTIVE_TTS_JOB_STATUSES),
        )
    )
    return (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "tts",
            or_(
                models.PostAudio.status == "ready",
                and_(
                    models.PostAudio.status.in_(["pending", "processing"]),
                    models.PostAudio.requester_user_id.isnot(None),
                ),
                and_(
                    models.PostAudio.status == "failed",
                    models.PostAudio.requester_user_id.isnot(None),
                    active_retry_job_exists,
                ),
            ),
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )

def has_active_tts_audio_job(db: Session, audio_id: int) -> bool:
    return db.query(models.AIJob.id).filter(
        models.AIJob.job_type == TTS_AUDIO_JOB_TYPE,
        models.AIJob.target_type == "audio",
        models.AIJob.target_id == audio_id,
        models.AIJob.status.in_(ACTIVE_TTS_JOB_STATUSES),
    ).first() is not None

def cancel_legacy_pending_tts_for_post(db: Session, post_id: int) -> int:
    updated = (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post_id,
            models.PostAudio.source == "tts",
            models.PostAudio.requester_user_id.is_(None),
            models.PostAudio.status.in_(["pending", "processing"]),
        )
        .update(
            {
                "status": "cancelled",
                "moderation_status": "cancelled",
                "moderation_reason": "Automatic TTS generation was disabled",
            },
            synchronize_session=False,
        )
    )
    if updated:
        db.commit()
    return updated

def enqueue_tts_audio_for_post(db: Session, post: models.Post) -> Optional[models.PostAudio]:
    if post.moderation_status != "approved":
        return None
    existing = (
        db.query(models.PostAudio)
        .filter(
            models.PostAudio.post_id == post.id,
            models.PostAudio.source == "tts",
            models.PostAudio.status.in_(["pending", "processing", "ready"]),
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )
    if existing:
        return existing
    return create_post_audio(db, post_id=post.id, source="tts", status="pending")

def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def audio_tts_quota_limit_for_user(user: models.User) -> int:
    if not user:
        return 0
    tier = user.premium_tier if user.is_premium else "free"
    return AUDIO_TTS_MONTHLY_QUOTAS.get(tier or "free", AUDIO_TTS_MONTHLY_QUOTAS["free"])

def audio_tts_quota_period_for_user(user: models.User) -> tuple[Optional[datetime], Optional[datetime]]:
    if not user:
        return None, None
    now = utcnow_naive()
    if user.is_premium and user.premium_until:
        period_end = _naive(user.premium_until)
        period_start = _naive(user.premium_period_start) if user.premium_period_start else period_end - timedelta(days=30)
        return period_start, period_end

    anchor = _naive(user.created_at) if user.created_at else now
    if now < anchor:
        return anchor, _add_months(anchor, 1)
    elapsed_months = (now.year - anchor.year) * 12 + (now.month - anchor.month)
    period_start = _add_months(anchor, elapsed_months)
    if period_start > now:
        elapsed_months -= 1
        period_start = _add_months(anchor, elapsed_months)
    return period_start, _add_months(anchor, elapsed_months + 1)

def get_user_audio_tts_character_usage(
    db: Session,
    user_id: int,
    period_start: datetime,
    period_end: datetime,
) -> int:
    used = (
        db.query(func.coalesce(func.sum(models.PostAudio.tts_character_count), 0))
        .filter(
            models.PostAudio.source == "tts",
            models.PostAudio.requester_user_id == user_id,
            models.PostAudio.quota_period_start == period_start,
            models.PostAudio.quota_period_end == period_end,
            or_(
                models.PostAudio.status.in_(["pending", "processing", "ready"]),
                # Audio the author deleted still used up quota that month.
                models.PostAudio.deleted_at.isnot(None),
            ),
        )
        .scalar()
    )
    return int(used or 0)

def create_tts_audio_request(
    db: Session,
    *,
    post_id: int,
    requester_user_id: int,
    tts_character_count: int,
    quota_period_start: datetime,
    quota_period_end: datetime,
) -> models.PostAudio:
    return create_post_audio(
        db,
        post_id=post_id,
        requester_user_id=requester_user_id,
        source="tts",
        status="pending",
        tts_character_count=tts_character_count,
        quota_period_start=quota_period_start,
        quota_period_end=quota_period_end,
    )

def get_random_ready_audio(
    db: Session, category: Optional[str] = None
) -> Optional[models.PostAudio]:
    query = (
        db.query(models.PostAudio)
        .join(models.Post)
        .filter(
            models.PostAudio.status == "ready",
            models.Post.moderation_status == "approved",
        )
    )
    if category:
        query = query.filter(models.Post.category == category)
    return query.order_by(func.random()).first()


def get_random_ready_audio_for_listen_mode(
    db: Session, mode: str
) -> Optional[models.PostAudio]:
    if mode not in AUDIO_LISTEN_MODES:
        return None
    category = None if mode == "toate" else mode
    return get_random_ready_audio(db, category=category)


def get_ready_audio_post_count_for_author(db: Session, author_id: int) -> int:
    return (
        db.query(models.Post.id)
        .join(models.PostAudio, models.PostAudio.post_id == models.Post.id)
        .filter(
            models.Post.user_id == author_id,
            models.Post.moderation_status == "approved",
            models.PostAudio.status == "ready",
        )
        .distinct()
        .count()
    )


def get_random_ready_audio_for_author_listen_mode(
    db: Session,
    author_id: int,
    mode: str,
) -> Optional[models.PostAudio]:
    if mode not in AUDIO_LISTEN_MODES:
        return None
    ready_audio_exists = (
        db.query(models.PostAudio.id)
        .filter(
            models.PostAudio.post_id == models.Post.id,
            models.PostAudio.status == "ready",
        )
        .exists()
    )
    query = (
        db.query(models.Post.id)
        .filter(
            models.Post.user_id == author_id,
            models.Post.moderation_status == "approved",
            ready_audio_exists,
        )
    )
    if mode != "toate":
        query = query.filter(models.Post.category == mode)
    row = query.order_by(func.random()).limit(1).first()
    return get_best_audio_for_post(db, row[0]) if row else None


def list_audio_playlists(
    db: Session,
    owner_id: int,
    post_id: Optional[int] = None,
) -> List[models.AudioPlaylist]:
    query = (
        db.query(models.AudioPlaylist)
        .options(joinedload(models.AudioPlaylist.items))
        .filter(models.AudioPlaylist.owner_id == owner_id)
    )
    if post_id is not None:
        query = query.filter(
            db.query(models.AudioPlaylistItem.id)
            .filter(
                models.AudioPlaylistItem.playlist_id == models.AudioPlaylist.id,
                models.AudioPlaylistItem.post_id == post_id,
            )
            .exists()
        )
    return query.order_by(models.AudioPlaylist.created_at.desc(), models.AudioPlaylist.id.desc()).all()


def get_audio_playlist(db: Session, playlist_id: int) -> Optional[models.AudioPlaylist]:
    return (
        db.query(models.AudioPlaylist)
        .options(
            joinedload(models.AudioPlaylist.owner),
            joinedload(models.AudioPlaylist.items).joinedload(models.AudioPlaylistItem.post).joinedload(models.Post.owner),
        )
        .filter(models.AudioPlaylist.id == playlist_id)
        .first()
    )


def get_audio_playlist_for_owner(
    db: Session,
    playlist_id: int,
    owner_id: int,
) -> Optional[models.AudioPlaylist]:
    playlist = get_audio_playlist(db, playlist_id)
    if not playlist or playlist.owner_id != owner_id:
        return None
    return playlist


def create_audio_playlist(db: Session, owner_id: int, title: str) -> models.AudioPlaylist:
    playlist = models.AudioPlaylist(owner_id=owner_id, title=title.strip())
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return playlist


def update_audio_playlist(
    db: Session,
    playlist: models.AudioPlaylist,
    *,
    title: str,
) -> models.AudioPlaylist:
    playlist.title = title.strip()
    db.commit()
    db.refresh(playlist)
    return playlist


def delete_audio_playlist(db: Session, playlist: models.AudioPlaylist) -> None:
    db.delete(playlist)
    db.commit()


def get_audio_playlist_items(
    db: Session,
    playlist_id: int,
) -> List[models.AudioPlaylistItem]:
    return (
        db.query(models.AudioPlaylistItem)
        .options(joinedload(models.AudioPlaylistItem.post).joinedload(models.Post.owner))
        .filter(models.AudioPlaylistItem.playlist_id == playlist_id)
        .order_by(models.AudioPlaylistItem.position.asc(), models.AudioPlaylistItem.created_at.asc(), models.AudioPlaylistItem.id.asc())
        .all()
    )


def get_audio_playlist_item(
    db: Session,
    playlist_id: int,
    post_id: int,
) -> Optional[models.AudioPlaylistItem]:
    return (
        db.query(models.AudioPlaylistItem)
        .options(joinedload(models.AudioPlaylistItem.post).joinedload(models.Post.owner))
        .filter(
            models.AudioPlaylistItem.playlist_id == playlist_id,
            models.AudioPlaylistItem.post_id == post_id,
        )
        .first()
    )


def add_post_to_audio_playlist(
    db: Session,
    playlist: models.AudioPlaylist,
    post: models.Post,
) -> tuple[Optional[models.AudioPlaylistItem], Optional[str]]:
    if post.moderation_status != "approved":
        return None, "post_unavailable"
    if not get_best_audio_for_post(db, post.id):
        return None, "audio_missing"
    existing = get_audio_playlist_item(db, playlist.id, post.id)
    if existing:
        return existing, "already_added"
    max_position = db.query(func.max(models.AudioPlaylistItem.position)).filter(
        models.AudioPlaylistItem.playlist_id == playlist.id
    ).scalar() or 0
    item = models.AudioPlaylistItem(
        playlist_id=playlist.id,
        post_id=post.id,
        position=max_position + 1,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return get_audio_playlist_item(db, playlist.id, post.id), "already_added"
    db.refresh(item)
    return item, None


def _renumber_audio_playlist_items(db: Session, items: List[models.AudioPlaylistItem]) -> None:
    ordered = sorted(items, key=lambda item: (item.position, item.created_at or datetime.min, item.id))
    for index, item in enumerate(ordered, start=1):
        item.position = -index
    db.flush()
    for index, item in enumerate(ordered, start=1):
        item.position = index


def remove_post_from_audio_playlist(
    db: Session,
    playlist: models.AudioPlaylist,
    post_id: int,
) -> bool:
    item = get_audio_playlist_item(db, playlist.id, post_id)
    if not item:
        return False
    db.delete(item)
    db.flush()
    _renumber_audio_playlist_items(db, get_audio_playlist_items(db, playlist.id))
    db.commit()
    return True


def get_audio_listen_event_by_event_id(
    db: Session, event_id: str
) -> Optional[models.AudioListenEvent]:
    return (
        db.query(models.AudioListenEvent)
        .filter(models.AudioListenEvent.event_id == event_id)
        .first()
    )


def get_ready_audio_for_listen_recording(
    db: Session, audio_id: int
) -> Optional[models.PostAudio]:
    return (
        db.query(models.PostAudio)
        .options(joinedload(models.PostAudio.post))
        .filter(models.PostAudio.id == audio_id)
        .first()
    )


def record_audio_listen_event(
    db: Session,
    *,
    event_id: str,
    audio: models.PostAudio,
    listener_user_id: Optional[int],
    seconds: int,
    mode: str,
    context: str = "post",
) -> tuple[models.AudioListenEvent, bool]:
    existing = get_audio_listen_event_by_event_id(db, event_id)
    if existing:
        return existing, False

    post = audio.post
    event = models.AudioListenEvent(
        event_id=event_id,
        audio_id=audio.id,
        post_id=post.id,
        content_owner_id=post.user_id,
        listener_user_id=listener_user_id,
        seconds=seconds,
        mode=mode,
        context=context,
    )
    db.add(event)
    db.query(models.Post).filter(models.Post.id == post.id).update(
        {models.Post.seconds_listened: func.coalesce(models.Post.seconds_listened, 0) + seconds},
        synchronize_session=False,
    )
    db.query(models.User).filter(models.User.id == post.user_id).update(
        {models.User.seconds_listened: func.coalesce(models.User.seconds_listened, 0) + seconds},
        synchronize_session=False,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = get_audio_listen_event_by_event_id(db, event_id)
        if existing:
            return existing, False
        raise
    db.refresh(event)
    return event, True


def _player_quota_day_start_in_db_clock(db: Session) -> datetime:
    """Start of today (Romanian midnight), expressed in the database's clock.

    audio_listen_events.created_at is stamped by the database's now(), whose
    timezone is a server setting (Europe/Berlin in production, UTC in SQLite
    tests). Measure that clock's offset from UTC and shift Romanian midnight
    into it, so the quota resets at local midnight whatever the DB timezone is.
    """
    db_now = db.query(func.now()).scalar()
    if isinstance(db_now, str):
        db_now = datetime.fromisoformat(db_now)
    if getattr(db_now, "tzinfo", None) is not None:
        db_now = db_now.replace(tzinfo=None)
    quarter_hours = round((db_now - utcnow_naive()) / timedelta(minutes=15))
    db_offset = timedelta(minutes=15 * quarter_hours)
    local_now = datetime.now(PLAYER_QUOTA_TIMEZONE)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight_utc = local_midnight.astimezone(timezone.utc).replace(tzinfo=None)
    return midnight_utc + db_offset


def get_player_listen_seconds_today(db: Session, user_id: int) -> int:
    """Seconds this user played today (Romanian calendar day) in the continuous player."""
    start_of_day = _player_quota_day_start_in_db_clock(db)
    total = (
        db.query(func.coalesce(func.sum(models.AudioListenEvent.seconds), 0))
        .filter(
            models.AudioListenEvent.listener_user_id == user_id,
            models.AudioListenEvent.context == "player",
            models.AudioListenEvent.created_at >= start_of_day,
        )
        .scalar()
    )
    return int(total or 0)
