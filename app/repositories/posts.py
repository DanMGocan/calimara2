from ._shared import *
from .slugs import generate_slug

def ensure_unique_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while db.query(models.Post).filter(models.Post.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

def get_post(db: Session, post_id: int):
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_post_by_slug(db: Session, slug: str):
    return db.query(models.Post).filter(models.Post.slug == slug).first()

def get_posts(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Post).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_posts_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Post).filter(models.Post.user_id == user_id).order_by(models.Post.created_at.desc()).offset(skip).limit(limit).all()

def get_post_draft(db: Session, draft_id: int, user_id: Optional[int] = None):
    query = db.query(models.PostDraft).filter(models.PostDraft.id == draft_id)
    if user_id is not None:
        query = query.filter(models.PostDraft.user_id == user_id)
    return query.first()

def count_post_drafts_by_user(db: Session, user_id: int):
    return db.query(func.count(models.PostDraft.id)).filter(models.PostDraft.user_id == user_id).scalar() or 0

def get_post_drafts_by_user(db: Session, user_id: int, limit: int = 50, offset: int = 0):
    return (
        db.query(models.PostDraft)
        .filter(models.PostDraft.user_id == user_id)
        .order_by(models.PostDraft.updated_at.desc(), models.PostDraft.id.desc())
        .offset(max(0, offset))
        .limit(limit)
        .all()
    )

def create_post_draft(db: Session, draft: schemas.PostDraftSave, user_id: int):
    db_draft = models.PostDraft(
        user_id=user_id,
        title=draft.title,
        content=draft.content,
        explanatory_note=draft.explanatory_note,
        category=draft.category,
    )
    db.add(db_draft)
    db.commit()
    db.refresh(db_draft)
    return db_draft

def update_post_draft(db: Session, draft_id: int, draft_update: schemas.PostDraftSave, user_id: int):
    db_draft = get_post_draft(db, draft_id, user_id)
    if not db_draft:
        return None
    db_draft.title = draft_update.title
    db_draft.content = draft_update.content
    db_draft.explanatory_note = draft_update.explanatory_note
    db_draft.category = draft_update.category
    db.commit()
    db.refresh(db_draft)
    return db_draft

def delete_post_draft(db: Session, draft_id: int, user_id: int):
    db_draft = get_post_draft(db, draft_id, user_id)
    if not db_draft:
        return None
    db.delete(db_draft)
    db.commit()
    return db_draft

def create_user_post(db: Session, post: schemas.PostCreate, user_id: int, category: Optional[str] = None):
    base_slug = generate_slug(post.title)
    slug = ensure_unique_slug(db, base_slug)
    post_data = post.model_dump(exclude={"ai_critic", "draft_id", "category"})
    
    db_post = models.Post(
        **post_data,
        user_id=user_id,
        slug=slug,
        category=category or post.category,
        ai_critic_requested=post.ai_critic,
        moderation_status="pending"
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)

    return db_post

def update_post(db: Session, post_id: int, post_update: schemas.PostUpdate, category: Optional[str] = None):
    db_post = get_post(db, post_id)
    if not db_post:
        return None
    
    update_data = post_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_post, key, value)
    
    if category:
        db_post.category = category
        
    db_post.moderation_status = "pending"
    db_post.theme_analysis_status = "pending"
    db_post.themes = []
    db_post.feelings = []
    db_post.ai_critic_requested = False
    db.query(models.PostAudio).filter(models.PostAudio.post_id == post_id).update(
        {
            "status": "rejected",
            "moderation_status": "rejected",
            "moderation_reason": "Postarea a fost editată după crearea acestui audio",
        }
    )
    db.commit()
    db.refresh(db_post)
    return db_post

def delete_post(db: Session, post_id: int):
    db_post = get_post(db, post_id)
    if db_post:
        db.delete(db_post)
        db.commit()
    return db_post

def update_post_theme_analysis(db: Session, post_id: int, themes: list, feelings: list, status: str):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post:
        post.themes = themes
        post.feelings = feelings
        post.theme_analysis_status = status
        db.commit()

def get_platform_stats(db: Session):
    try:
        total_posts = db.query(func.count(models.Post.id)).filter(
            models.Post.moderation_status == "approved"
        ).scalar() or 0
        total_authors = db.query(func.count(func.distinct(models.Post.user_id))).filter(
            models.Post.moderation_status == "approved",
            models.Post.user_id.isnot(None),
        ).scalar() or 0
    except Exception:
        logger.exception("Failed to load platform stats")
        db.rollback()
        return {"total_posts": 0, "total_authors": 0}
    return {"total_posts": total_posts, "total_authors": total_authors}

def get_random_posts(db: Session, limit: int = 10):
    return db.query(models.Post).filter(models.Post.moderation_status == "approved").order_by(func.random()).limit(limit).all()

def get_random_posts_by_category(db: Session, category: str, limit: int = 10):
    return db.query(models.Post).filter(
        models.Post.category == category,
        models.Post.moderation_status == "approved"
    ).order_by(func.random()).limit(limit).all()

def _view_weighted_order_key():
    # Efraimidis–Spirakis weighted random: LN(RANDOM()) is always negative,
    # so multiplying by the positive weight POWER(view_count + 1, alpha)
    # and sorting DESC picks the row with the smallest |LN(R)| / weight —
    # i.e. sampling probability ∝ 1 / (view_count + 1)^alpha.
    alpha = float(os.getenv("LANDING_VIEW_DECAY_ALPHA", "0.5"))
    if alpha == 0:
        return None
    return func.ln(func.random()) * func.power(models.Post.view_count + 1, alpha)

def get_weighted_random_posts(db: Session, limit: int = 10):
    if os.getenv("LANDING_WEIGHTED_RANDOM_ENABLED", "True").lower() != "true":
        return get_random_posts(db, limit=limit)
    order_key = _view_weighted_order_key()
    if order_key is None:
        return get_random_posts(db, limit=limit)
    return db.query(models.Post).filter(
        models.Post.moderation_status == "approved"
    ).order_by(desc(order_key)).limit(limit).all()

def get_weighted_random_posts_by_category(db: Session, category: str, limit: int = 10):
    if os.getenv("LANDING_WEIGHTED_RANDOM_ENABLED", "True").lower() != "true":
        return get_random_posts_by_category(db, category, limit=limit)
    order_key = _view_weighted_order_key()
    if order_key is None:
        return get_random_posts_by_category(db, category, limit=limit)
    return db.query(models.Post).filter(
        models.Post.category == category,
        models.Post.moderation_status == "approved"
    ).order_by(desc(order_key)).limit(limit).all()

def count_posts_for_user(db: Session, user_id: int, include_unapproved: bool = False):
    query = db.query(func.count(models.Post.id)).filter(models.Post.user_id == user_id)
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")
    return query.scalar() or 0

def count_posts_by_month_year(
    db: Session,
    user_id: int,
    month: int,
    year: int,
    include_unapproved: bool = False,
):
    query = db.query(func.count(models.Post.id)).filter(
        models.Post.user_id == user_id,
        extract('month', models.Post.created_at) == month,
        extract('year', models.Post.created_at) == year
    )
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")
    return query.scalar() or 0

def get_latest_posts_for_user(db: Session, user_id: int, limit: int = 5, include_unapproved: bool = False, offset: int = 0):
    query = db.query(models.Post).filter(models.Post.user_id == user_id)
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")
    return query.order_by(models.Post.created_at.desc()).offset(max(0, offset)).limit(limit).all()

def get_posts_by_month_year(
    db: Session,
    user_id: int,
    month: int,
    year: int,
    limit: int = 50,
    include_unapproved: bool = False,
    offset: int = 0,
):
    query = db.query(models.Post).filter(
        models.Post.user_id == user_id,
        extract('month', models.Post.created_at) == month,
        extract('year', models.Post.created_at) == year
    )
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")
    return query.order_by(models.Post.created_at.desc()).offset(max(0, offset)).limit(limit).all()

def get_available_months_for_user(db: Session, user_id: int, include_unapproved: bool = False):
    query = db.query(
        extract('month', models.Post.created_at).label('month'),
        extract('year', models.Post.created_at).label('year'),
        func.count(models.Post.id).label('post_count')
    ).filter(
        models.Post.user_id == user_id,
    )
    if not include_unapproved:
        query = query.filter(models.Post.moderation_status == "approved")

    results = query.group_by('year', 'month').order_by(desc('year'), desc('month')).all()
    
    return [{"month": int(r.month), "year": int(r.year), "post_count": r.post_count} for r in results]

def get_distinct_categories_used(db: Session, user_id: Optional[int] = None):
    query = db.query(models.Post.category).filter(models.Post.moderation_status == "approved")
    if user_id:
        query = query.filter(models.Post.user_id == user_id)
    results = query.distinct().all()
    return [r[0] for r in results if r[0]]

def get_user_post_counts_by_category(db: Session, user_id: int):
    rows = db.query(
        models.Post.category,
        func.count(models.Post.id),
    ).filter(
        models.Post.user_id == user_id,
        models.Post.moderation_status == "approved",
    ).group_by(models.Post.category).all()
    return {category: count for category, count in rows if category}

def _get_distinct_post_terms(db: Session, field_name: str) -> List[str]:
    posts = db.query(models.Post).filter(
        models.Post.moderation_status == "approved",
        models.Post.theme_analysis_status == "completed",
    ).all()
    terms = set()
    for post in posts:
        values = getattr(post, field_name, None) or []
        for value in values:
            if isinstance(value, str) and value.strip():
                terms.add(value.strip().lower())
    return sorted(terms)

def get_distinct_themes(db: Session):
    return _get_distinct_post_terms(db, "themes")

def get_distinct_feelings(db: Session):
    return _get_distinct_post_terms(db, "feelings")

# ===================================
# COMMENT CRUD FUNCTIONS
# ===================================
