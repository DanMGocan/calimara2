from ._shared import *

AUDIO_TTS_MONTHLY_QUOTAS = {
    "cronicar": 100_000,
    "rapsod": 250_000,
}

AUDIO_LISTEN_MODES = {"poezie", "proza_scurta", "toate"}

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
        .filter(models.PostAudio.post_id == post_id)
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
            ),
        )
        .order_by(models.PostAudio.updated_at.desc(), models.PostAudio.id.desc())
        .first()
    )

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

def audio_tts_quota_limit_for_user(user: models.User) -> int:
    if not user or not user.is_premium:
        return 0
    return AUDIO_TTS_MONTHLY_QUOTAS.get(user.premium_tier, 0)

def audio_tts_quota_period_for_user(user: models.User) -> tuple[Optional[datetime], Optional[datetime]]:
    if not user or not user.is_premium or not user.premium_until:
        return None, None
    period_end = user.premium_until
    period_start = user.premium_period_start or (period_end - timedelta(days=30))
    return period_start, period_end

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
            models.PostAudio.status.in_(["pending", "processing", "ready"]),
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
    listener_user_id: int,
    seconds: int,
    mode: str,
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
