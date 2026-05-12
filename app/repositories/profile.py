from ._shared import *

PROMOTED_OWN_POST_LIMIT = 2
PROMOTED_AUTHOR_LIMIT = 3
PROMOTED_OTHER_POST_LIMIT = 3
OWN_POST_POSITION_START = 1
OWN_POST_POSITION_END = 2
OTHER_POST_POSITION_START = 3
OTHER_POST_POSITION_END = 5


def promotion_limits():
    return {
        "own_posts": PROMOTED_OWN_POST_LIMIT,
        "authors": PROMOTED_AUTHOR_LIMIT,
        "other_posts": PROMOTED_OTHER_POST_LIMIT,
    }


def get_featured_posts_for_user(db: Session, user_id: int):
    return (
        db.query(models.FeaturedPost)
        .options(joinedload(models.FeaturedPost.post).joinedload(models.Post.owner))
        .filter(models.FeaturedPost.user_id == user_id)
        .order_by(models.FeaturedPost.position)
        .all()
    )

def get_best_friends_for_user(db: Session, user_id: int):
    return (
        db.query(models.BestFriend)
        .options(joinedload(models.BestFriend.friend))
        .filter(models.BestFriend.user_id == user_id)
        .order_by(models.BestFriend.position)
        .all()
    )


def _approved_promoted_entries(entries):
    return [
        entry
        for entry in entries
        if entry.post and entry.post.moderation_status == "approved"
    ]


def get_promoted_own_post_entries_for_user(db: Session, user_id: int):
    entries = get_featured_posts_for_user(db, user_id)
    return [
        entry
        for entry in _approved_promoted_entries(entries)
        if entry.post.user_id == user_id and OWN_POST_POSITION_START <= entry.position <= OWN_POST_POSITION_END
    ]


def get_promoted_other_post_entries_for_user(db: Session, user_id: int):
    entries = get_featured_posts_for_user(db, user_id)
    return [
        entry
        for entry in _approved_promoted_entries(entries)
        if entry.post.user_id != user_id and OTHER_POST_POSITION_START <= entry.position <= OTHER_POST_POSITION_END
    ]


def get_promoted_authors_for_user(db: Session, user_id: int):
    return [
        entry
        for entry in get_best_friends_for_user(db, user_id)
        if entry.friend and not entry.friend.is_suspended
    ][:PROMOTED_AUTHOR_LIMIT]


def get_promoted_post_ids_for_user(db: Session, user_id: int):
    return {
        row[0]
        for row in db.query(models.FeaturedPost.post_id)
        .filter(models.FeaturedPost.user_id == user_id)
        .all()
    }


def get_promoted_author_ids_for_user(db: Session, user_id: int):
    return {
        row[0]
        for row in db.query(models.BestFriend.friend_user_id)
        .filter(models.BestFriend.user_id == user_id)
        .all()
    }


def is_post_promoted_by_user(db: Session, user_id: int, post_id: int) -> bool:
    return (
        db.query(models.FeaturedPost.id)
        .filter(
            models.FeaturedPost.user_id == user_id,
            models.FeaturedPost.post_id == post_id,
        )
        .first()
        is not None
    )


def is_author_promoted_by_user(db: Session, user_id: int, author_id: int) -> bool:
    return (
        db.query(models.BestFriend.id)
        .filter(
            models.BestFriend.user_id == user_id,
            models.BestFriend.friend_user_id == author_id,
        )
        .first()
        is not None
    )


def replace_promoted_own_posts(db: Session, user_id: int, post_ids: list[int]) -> None:
    db.query(models.FeaturedPost).filter(
        models.FeaturedPost.user_id == user_id,
        models.FeaturedPost.position.between(OWN_POST_POSITION_START, OWN_POST_POSITION_END),
    ).delete(synchronize_session=False)

    for offset, post_id in enumerate(post_ids):
        db.add(
            models.FeaturedPost(
                user_id=user_id,
                post_id=post_id,
                position=OWN_POST_POSITION_START + offset,
            )
        )


def replace_promoted_other_posts(db: Session, user_id: int, post_ids: list[int]) -> None:
    db.query(models.FeaturedPost).filter(
        models.FeaturedPost.user_id == user_id,
        models.FeaturedPost.position.between(OTHER_POST_POSITION_START, OTHER_POST_POSITION_END),
    ).delete(synchronize_session=False)

    for offset, post_id in enumerate(post_ids):
        db.add(
            models.FeaturedPost(
                user_id=user_id,
                post_id=post_id,
                position=OTHER_POST_POSITION_START + offset,
            )
        )


def replace_promoted_authors(db: Session, user_id: int, author_ids: list[int]) -> None:
    db.query(models.BestFriend).filter(models.BestFriend.user_id == user_id).delete(synchronize_session=False)

    for position, author_id in enumerate(author_ids, 1):
        db.add(
            models.BestFriend(
                user_id=user_id,
                friend_user_id=author_id,
                position=position,
            )
        )


def _next_available_position(db: Session, model, user_id: int, start: int, end: int) -> Optional[int]:
    used_positions = {
        row[0]
        for row in db.query(model.position)
        .filter(
            model.user_id == user_id,
            model.position.between(start, end),
        )
        .all()
    }
    for position in range(start, end + 1):
        if position not in used_positions:
            return position
    return None


def add_promoted_post(db: Session, user_id: int, post: models.Post) -> tuple[bool, Optional[str]]:
    if is_post_promoted_by_user(db, user_id, post.id):
        return True, None

    if post.user_id == user_id:
        position = _next_available_position(
            db,
            models.FeaturedPost,
            user_id,
            OWN_POST_POSITION_START,
            OWN_POST_POSITION_END,
        )
        error = "own_post_limit"
    else:
        position = _next_available_position(
            db,
            models.FeaturedPost,
            user_id,
            OTHER_POST_POSITION_START,
            OTHER_POST_POSITION_END,
        )
        error = "other_post_limit"

    if position is None:
        return False, error

    db.add(models.FeaturedPost(user_id=user_id, post_id=post.id, position=position))
    return True, None


def remove_promoted_post(db: Session, user_id: int, post_id: int) -> bool:
    removed = (
        db.query(models.FeaturedPost)
        .filter(
            models.FeaturedPost.user_id == user_id,
            models.FeaturedPost.post_id == post_id,
        )
        .delete(synchronize_session=False)
    )
    return bool(removed)


def add_promoted_author(db: Session, user_id: int, author_id: int) -> tuple[bool, Optional[str]]:
    if is_author_promoted_by_user(db, user_id, author_id):
        return True, None
    position = _next_available_position(db, models.BestFriend, user_id, 1, PROMOTED_AUTHOR_LIMIT)
    if position is None:
        return False, "author_limit"
    db.add(models.BestFriend(user_id=user_id, friend_user_id=author_id, position=position))
    return True, None


def remove_promoted_author(db: Session, user_id: int, author_id: int) -> bool:
    removed = (
        db.query(models.BestFriend)
        .filter(
            models.BestFriend.user_id == user_id,
            models.BestFriend.friend_user_id == author_id,
        )
        .delete(synchronize_session=False)
    )
    return bool(removed)


def search_promotable_content(db: Session, user: models.User, term: str, limit: int = 8):
    term = term.strip()
    if len(term) < 2:
        return {"own_posts": [], "authors": [], "other_posts": []}

    pattern = f"%{term}%"
    has_approved_posts = (
        db.query(models.Post.id)
        .filter(
            models.Post.user_id == models.User.id,
            models.Post.moderation_status == "approved",
        )
        .exists()
    )

    own_posts = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(
            models.Post.user_id == user.id,
            models.Post.moderation_status == "approved",
            or_(models.Post.title.ilike(pattern), models.Post.content.ilike(pattern)),
        )
        .order_by(models.Post.created_at.desc())
        .limit(limit)
        .all()
    )

    authors = (
        db.query(models.User)
        .filter(
            models.User.id != user.id,
            models.User.is_suspended == False,
            has_approved_posts,
            or_(
                models.User.username.ilike(pattern),
                models.User.subtitle.ilike(pattern),
            ),
        )
        .order_by(models.User.username.asc())
        .limit(limit)
        .all()
    )

    other_posts = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .join(models.Post.owner)
        .filter(
            models.Post.user_id != user.id,
            models.Post.moderation_status == "approved",
            models.User.is_suspended == False,
            or_(
                models.Post.title.ilike(pattern),
                models.Post.content.ilike(pattern),
                models.User.username.ilike(pattern),
            ),
        )
        .order_by(models.Post.created_at.desc())
        .limit(limit)
        .all()
    )

    return {"own_posts": own_posts, "authors": authors, "other_posts": other_posts}

# ===================================
# AWARDS
# ===================================

def get_user_awards(db: Session, user_id: int):
    return db.query(models.UserAward).filter(models.UserAward.user_id == user_id).order_by(models.UserAward.award_date.desc()).all()


# ===================================
# GOLOGANI / SHOP
# ===================================
