from ._shared import *
from .slugs import generate_slug

def _generate_series_slug(title: str) -> str:
    return generate_slug(title, fallback="serie")

def _ensure_unique_series_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while db.query(models.Series).filter(models.Series.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

def get_series(db: Session, series_id: int):
    return db.query(models.Series).options(
        joinedload(models.Series.owner)
    ).filter(models.Series.id == series_id).first()

def get_series_by_slug(db: Session, slug: str):
    return db.query(models.Series).options(
        joinedload(models.Series.owner)
    ).filter(models.Series.slug == slug).first()

def get_series_by_owner(db: Session, owner_id: int):
    return db.query(models.Series).options(
        joinedload(models.Series.owner)
    ).filter(
        models.Series.owner_id == owner_id
    ).order_by(models.Series.created_at.desc()).all()

def create_series(db: Session, owner_id: int, data: schemas.SeriesCreate) -> models.Series:
    base_slug = _generate_series_slug(data.title)
    slug = _ensure_unique_series_slug(db, base_slug)
    series = models.Series(
        owner_id=owner_id,
        title=data.title.strip(),
        slug=slug,
        description=(data.description or "").strip() or None,
    )
    db.add(series)
    db.commit()
    db.refresh(series)
    return series

def update_series(db: Session, series_id: int, data: schemas.SeriesUpdate) -> Optional[models.Series]:
    series = get_series(db, series_id)
    if not series:
        return None
    payload = data.model_dump(exclude_unset=True)
    if "title" in payload and payload["title"]:
        series.title = payload["title"].strip()
    if "description" in payload:
        value = payload["description"]
        series.description = value.strip() if value else None
    db.commit()
    db.refresh(series)
    return series

def delete_series(db: Session, series_id: int) -> bool:
    series = get_series(db, series_id)
    if not series:
        return False
    db.delete(series)
    db.commit()
    return True

def count_series_posts(db: Session, series_id: int, approved_only: bool = True) -> int:
    query = db.query(models.SeriesPost).join(models.Post).filter(
        models.SeriesPost.series_id == series_id,
    )
    if approved_only:
        query = query.filter(
            models.Post.moderation_status == "approved",
            not_human_rejected_condition("post", models.Post.id),
        )
    else:
        query = query.filter(
            models.Post.moderation_status != "rejected",
            not_human_rejected_condition("post", models.Post.id),
        )
    return query.count()

def get_series_entries(
    db: Session,
    series_id: int,
    approved_posts_only: bool = True,
):
    query = db.query(models.SeriesPost).options(
        joinedload(models.SeriesPost.post).joinedload(models.Post.owner)
    ).filter(models.SeriesPost.series_id == series_id)
    if approved_posts_only:
        query = query.join(models.Post).filter(
            models.Post.moderation_status == "approved",
            not_human_rejected_condition("post", models.Post.id),
        )
    else:
        query = query.join(models.Post).filter(
            models.Post.moderation_status != "rejected",
            not_human_rejected_condition("post", models.Post.id),
        )
    entries = query.order_by(
        models.SeriesPost.position.asc(),
        models.SeriesPost.created_at.asc(),
    ).all()
    return entries

def get_series_entry(db: Session, series_id: int, post_id: int) -> Optional[models.SeriesPost]:
    return db.query(models.SeriesPost).filter(
        models.SeriesPost.series_id == series_id,
        models.SeriesPost.post_id == post_id,
    ).first()

def get_series_entry_for_post(db: Session, post_id: int) -> Optional[models.SeriesPost]:
    return db.query(models.SeriesPost).options(
        joinedload(models.SeriesPost.series).joinedload(models.Series.owner),
        joinedload(models.SeriesPost.post).joinedload(models.Post.owner),
    ).filter(models.SeriesPost.post_id == post_id).first()

def _renumber_series_entries(db: Session, entries: List[models.SeriesPost]) -> None:
    ordered_entries = sorted(entries, key=lambda entry: (entry.position, entry.created_at or datetime.min, entry.id))
    for index, entry in enumerate(ordered_entries, start=1):
        entry.position = -index
    db.flush()
    for index, entry in enumerate(ordered_entries, start=1):
        entry.position = index

def add_post_to_series(
    db: Session,
    series: models.Series,
    post: models.Post,
) -> tuple[Optional[models.SeriesPost], Optional[str]]:
    if post.user_id != series.owner_id:
        return None, "wrong_author"

    existing = get_series_entry_for_post(db, post.id)
    if existing:
        if existing.series_id == series.id:
            return existing, "already_in_series"
        return existing, "post_in_other_series"

    max_position = db.query(func.max(models.SeriesPost.position)).filter(
        models.SeriesPost.series_id == series.id
    ).scalar() or 0
    entry = models.SeriesPost(
        series_id=series.id,
        post_id=post.id,
        position=max_position + 1,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None, "post_in_other_series"
    db.refresh(entry)
    return entry, None

def remove_series_entry(db: Session, series: models.Series, post_id: int) -> bool:
    entry = get_series_entry(db, series.id, post_id)
    if not entry:
        return False
    db.delete(entry)
    db.flush()
    remaining = get_series_entries(db, series.id, approved_posts_only=False)
    _renumber_series_entries(db, remaining)
    db.commit()
    return True

def reorder_series_posts(
    db: Session,
    series: models.Series,
    post_ids: List[int],
) -> tuple[Optional[List[models.SeriesPost]], Optional[str]]:
    entries = get_series_entries(db, series.id, approved_posts_only=False)
    existing_ids = [entry.post_id for entry in entries]
    if len(post_ids) != len(set(post_ids)):
        return None, "duplicate_posts"
    if set(post_ids) != set(existing_ids):
        return None, "mismatched_posts"

    by_post_id = {entry.post_id: entry for entry in entries}
    ordered_entries = [by_post_id[post_id] for post_id in post_ids]
    for index, entry in enumerate(ordered_entries, start=1):
        entry.position = -index
    db.flush()
    for index, entry in enumerate(ordered_entries, start=1):
        entry.position = index
    db.commit()
    return get_series_entries(db, series.id, approved_posts_only=False), None

def _series_context_post_payload(post: Optional[models.Post]) -> Optional[dict]:
    if not post:
        return None
    owner = post.owner
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "category": post.category,
        "moderation_status": post.moderation_status,
        "owner": {
            "id": owner.id,
            "username": owner.username,
            "avatar_seed": owner.avatar_seed or f"{owner.username}-shapes",
        } if owner else None,
    }

def get_series_context_for_post(db: Session, post: models.Post, include_unapproved: bool = False) -> Optional[dict]:
    entry = get_series_entry_for_post(db, post.id)
    if not entry or not entry.series:
        return None
    entries = get_series_entries(
        db,
        entry.series_id,
        approved_posts_only=not include_unapproved,
    )
    visible_post_ids = [series_entry.post_id for series_entry in entries]
    if post.id not in visible_post_ids:
        return None
    index = visible_post_ids.index(post.id)
    series = entry.series
    owner = series.owner
    return {
        "series": {
            "id": series.id,
            "owner_id": series.owner_id,
            "title": series.title,
            "slug": series.slug,
            "description": series.description,
            "owner": {
                "id": owner.id,
                "username": owner.username,
                "avatar_seed": owner.avatar_seed or f"{owner.username}-shapes",
            } if owner else None,
            "post_count": len(entries),
        },
        "position": index + 1,
        "total_posts": len(entries),
        "previous_post": _series_context_post_payload(entries[index - 1].post) if index > 0 else None,
        "next_post": _series_context_post_payload(entries[index + 1].post) if index + 1 < len(entries) else None,
    }

def get_random_series(db: Session) -> Optional[models.Series]:
    """Random series with at least one approved post (so the random link
    isn't a dead-end to an empty page)."""
    return (
        db.query(models.Series)
        .options(joinedload(models.Series.owner))
        .filter(
            db.query(models.SeriesPost.id)
            .join(models.Post, models.Post.id == models.SeriesPost.post_id)
            .filter(
                models.SeriesPost.series_id == models.Series.id,
                models.Post.moderation_status == "approved",
            )
            .exists()
        )
        .order_by(func.random())
        .limit(1)
        .first()
    )
