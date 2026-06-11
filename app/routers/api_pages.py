"""
JSON API endpoints that serve the data previously embedded in Jinja2 templates.
These endpoints power the React frontend.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from sqlalchemy import func, or_

from .. import cache, models, crud, auth, statistics, pdf_exporter, profile_media, rich_text
from ..database import get_db
from ..utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX, default_cover_seed, get_avatar_url, get_client_ip, get_cover_url
from ..categories import CATEGORIES, get_category_name

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api-pages"])

SUPPORT_LINK_PREMIUM_TIERS = {"trubadur", "cronicar", "rapsod"}
LIKE_SESSION_KEY = "liked_post_ids"


def _public_cache_key(db: Session, request: Optional[Request], current_user: Optional[models.User], prefix: str, *parts):
    if current_user:
        return None
    if getattr(db.get_bind().dialect, "name", "") != "postgresql":
        return None
    liked_ids = []
    if request:
        values = request.session.get(LIKE_SESSION_KEY, [])
        if isinstance(values, list):
            for value in values:
                try:
                    liked_ids.append(int(value))
                except (TypeError, ValueError):
                    continue
    client_ip = get_client_ip(request) if request else "unknown"
    return (prefix, *parts, client_ip, tuple(sorted(set(liked_ids))))


def _can_use_support_links(user) -> bool:
    premium_tier = getattr(user, "premium_tier", "free") or "free"
    return bool(getattr(user, "is_premium", False)) and premium_tier in SUPPORT_LINK_PREMIUM_TIERS


def serialize_user(user):
    """Serialize a user object to dict for JSON response"""
    profile_photo_url = None
    cover_photo_url = None
    support_links_visible = _can_use_support_links(user)
    if getattr(user, "is_premium", False):
        if getattr(user, "profile_photo_storage_key", None):
            profile_photo_url = profile_media.public_media_url(user.username, "profil")
        if getattr(user, "cover_photo_storage_key", None):
            cover_photo_url = profile_media.public_media_url(user.username, "coperta")
    cover_seed = getattr(user, "cover_seed", None) or default_cover_seed(user)
    equipped_items = [
        {
            "slot": equipped.slot,
            "item": {
                "id": equipped.item.id,
                "slug": equipped.item.slug,
                "name": equipped.item.name,
                "description": equipped.item.description,
                "price": equipped.item.price,
                "slot": equipped.item.slot,
                "asset_url": equipped.item.asset_url,
            },
        }
        for equipped in sorted(getattr(user, "equipped_items", []) or [], key=lambda item: item.slot)
        if getattr(equipped, "item", None)
    ]
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": rich_text.sanitize_optional_rich_text(user.subtitle),
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "cover_seed": cover_seed,
        "avatar_url": profile_photo_url or get_avatar_url(user, size=160),
        "profile_photo_url": profile_photo_url,
        "cover_photo_url": cover_photo_url,
        "cover_url": cover_photo_url or get_cover_url(cover_seed),
        "has_profile_photo": bool(getattr(user, "profile_photo_storage_key", None)),
        "has_cover_photo": bool(getattr(user, "cover_photo_storage_key", None)),
        "location": getattr(user, "location", None),
        "youtube_playlist_url": getattr(user, "youtube_playlist_url", None),
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
        "gologani_balance": getattr(user, "gologani_balance", 0) or 0,
        "seconds_listened": getattr(user, "seconds_listened", 0) or 0,
        "equipped_items": equipped_items,
        "facebook_url": getattr(user, 'facebook_url', None),
        "tiktok_url": getattr(user, 'tiktok_url', None),
        "instagram_url": getattr(user, 'instagram_url', None),
        "x_url": getattr(user, 'x_url', None),
        "bluesky_url": getattr(user, 'bluesky_url', None),
        "patreon_url": getattr(user, 'patreon_url', None) if support_links_visible else None,
        "paypal_url": getattr(user, 'paypal_url', None) if support_links_visible else None,
        "buymeacoffee_url": getattr(user, 'buymeacoffee_url', None) if support_links_visible else None,
    }


def serialize_shop_item(item, owned=False, equipped=False):
    return {
        "id": item.id,
        "slug": item.slug,
        "name": item.name,
        "description": item.description,
        "price": item.price,
        "slot": item.slot,
        "asset_url": item.asset_url,
        "is_active": item.is_active,
        "sort_order": item.sort_order,
        "owned": owned,
        "equipped": equipped,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_inventory_item(entry, equipped_ids):
    return {
        "id": entry.id,
        "item": serialize_shop_item(
            entry.item,
            owned=True,
            equipped=entry.item_id in equipped_ids,
        ),
        "purchased_at": entry.purchased_at,
    }


def serialize_equipped_item(entry):
    return {
        "id": entry.id,
        "slot": entry.slot,
        "item": serialize_shop_item(entry.item, owned=True, equipped=True),
        "equipped_at": entry.equipped_at,
    }


def serialize_post(
    post,
    include_owner=False,
    super_likes_count=None,
    viewer_super_liked=False,
    viewer_liked=False,
    comments_count=None,
    viewer_promoted=False,
):
    """Serialize a post object to dict for JSON response.

    super_likes_count/viewer_super_liked are accepted as precomputed values so
    callers handling post lists can avoid N+1 queries. If super_likes_count is
    None, it falls back to the hybrid property (one query per post).
    """
    if super_likes_count is None:
        super_likes_count = post.super_likes_count
    result = {
        "id": post.id,
        "user_id": post.user_id,
        "title": post.title,
        "slug": post.slug,
        "content": rich_text.sanitize_rich_text(post.content),
        "explanatory_note": post.explanatory_note,
        "category": post.category,
        "category_name": get_category_name(post.category) if post.category else "",
        "view_count": post.view_count,
        "vizualizari": post.view_count,
        "seconds_listened": post.seconds_listened or 0,
        "likes_count": post.likes_count,
        "viewer_liked": viewer_liked,
        "comments_count": comments_count if comments_count is not None else len(post.approved_comments),
        "super_likes_count": super_likes_count,
        "viewer_super_liked": viewer_super_liked,
        "viewer_promoted": viewer_promoted,
        "moderation_status": post.moderation_status,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
    }
    if include_owner and post.owner:
        result["owner"] = {
            "id": post.owner.id,
            "username": post.owner.username,
            "avatar_seed": post.owner.avatar_seed or f"{post.owner.username}-shapes",
            "subtitle": rich_text.sanitize_optional_rich_text(post.owner.subtitle),
            "is_premium": getattr(post.owner, "is_premium", False),
            "premium_tier": getattr(post.owner, "premium_tier", "free") or "free",
        }
    return result


def compute_super_like_fields(db: Session, posts, current_user):
    """Return two dicts: {post_id: count} and {post_id: bool} for the given posts.

    Uses two aggregate queries (or one if current_user is None) regardless of
    list size.
    """
    if not posts:
        return {}, {}
    post_ids = [p.id for p in posts]
    counts = dict(
        db.query(models.SuperLike.post_id, func.count(models.SuperLike.id))
        .filter(models.SuperLike.post_id.in_(post_ids))
        .group_by(models.SuperLike.post_id)
        .all()
    )
    liked = {}
    if current_user:
        liked_ids = {
            row[0]
            for row in db.query(models.SuperLike.post_id)
            .filter(
                models.SuperLike.user_id == current_user.id,
                models.SuperLike.post_id.in_(post_ids),
            )
            .all()
        }
        liked = {pid: (pid in liked_ids) for pid in post_ids}
    return counts, liked


def compute_like_fields(db: Session, posts, current_user, request: Optional[Request] = None):
    if not posts:
        return {}
    post_ids = [p.id for p in posts]
    session_liked_ids = set()
    if request:
        values = request.session.get(LIKE_SESSION_KEY, [])
        if isinstance(values, list):
            for value in values:
                try:
                    session_liked_ids.add(int(value))
                except (TypeError, ValueError):
                    continue
    identity_filters = []
    if current_user:
        identity_filters.append(models.Like.user_id == current_user.id)
    if request:
        identity_filters.append(models.Like.ip_address == get_client_ip(request))
    liked_ids = set()
    if identity_filters:
        query = db.query(models.Like.post_id).filter(models.Like.post_id.in_(post_ids))
        query = query.filter(or_(*identity_filters))
        liked_ids = {row[0] for row in query.all()}
    liked_ids.update(pid for pid in session_liked_ids if pid in post_ids)
    return {pid: (pid in liked_ids) for pid in post_ids}


COMMENT_VISIBLE_STATUSES = ("approved", "pending", "flagged")


def compute_approved_comment_counts(db: Session, posts):
    if not posts:
        return {}
    post_ids = [p.id for p in posts]
    return dict(
        db.query(models.Comment.post_id, func.count(models.Comment.id))
        .filter(
            models.Comment.post_id.in_(post_ids),
            models.Comment.moderation_status.in_(COMMENT_VISIBLE_STATUSES),
            crud.not_human_rejected_condition("comment", models.Comment.id),
        )
        .group_by(models.Comment.post_id)
        .all()
    )


def visible_comments_for_post(db: Session, post_id: int):
    return (
        db.query(models.Comment)
        .options(joinedload(models.Comment.commenter))
        .filter(
            models.Comment.post_id == post_id,
            models.Comment.moderation_status.in_(COMMENT_VISIBLE_STATUSES),
            crud.not_human_rejected_condition("comment", models.Comment.id),
        )
        .order_by(models.Comment.created_at.asc(), models.Comment.id.asc())
        .all()
    )


def compute_promoted_post_fields(db: Session, posts, current_user):
    if not posts or not current_user:
        return {}
    post_ids = [p.id for p in posts]
    promoted_ids = {
        row[0]
        for row in db.query(models.FeaturedPost.post_id)
        .filter(
            models.FeaturedPost.user_id == current_user.id,
            models.FeaturedPost.post_id.in_(post_ids),
        )
        .all()
    }
    return {pid: (pid in promoted_ids) for pid in post_ids}


def serialize_posts_with_super_likes(db, posts, current_user, include_owner=False, include_comments=False, request: Optional[Request] = None):
    """Serialize a list of posts with efficient bulk super-like lookups."""
    counts, liked = compute_super_like_fields(db, posts, current_user)
    viewer_liked = compute_like_fields(db, posts, current_user, request)
    comment_counts = compute_approved_comment_counts(db, posts)
    promoted = compute_promoted_post_fields(db, posts, current_user)
    comments_by_post = {}
    comment_reaction_counts = {}
    comment_viewer_reactions = {}
    if include_comments:
        all_comments = []
        for post in posts:
            post_comments = visible_comments_for_post(db, post.id)
            comments_by_post[post.id] = post_comments
            all_comments.extend(post_comments)
        comment_reaction_counts, comment_viewer_reactions = compute_comment_reaction_fields(db, all_comments, current_user)
    serialized = []
    for post in posts:
        item = serialize_post(
            post,
            include_owner=include_owner,
            super_likes_count=counts.get(post.id, 0),
            viewer_super_liked=liked.get(post.id, False),
            viewer_liked=viewer_liked.get(post.id, False),
            comments_count=comment_counts.get(post.id, 0),
            viewer_promoted=promoted.get(post.id, False),
        )
        if include_comments:
            item["approved_comments"] = [
                serialize_comment(
                    comment,
                    db,
                    reaction_counts=comment_reaction_counts.get(comment.id),
                    viewer_reaction=comment_viewer_reactions.get(comment.id),
                )
                for comment in comments_by_post.get(post.id, [])
            ]
        serialized.append(item)
    return serialized


def serialize_series_summary(db: Session, series):
    owner = series.owner
    return {
        "id": series.id,
        "owner_id": series.owner_id,
        "title": series.title,
        "slug": series.slug,
        "description": series.description,
        "owner": {
            "id": owner.id,
            "username": owner.username,
            "avatar_seed": owner.avatar_seed or f"{owner.username}-shapes",
            "is_premium": getattr(owner, "is_premium", False),
            "premium_tier": getattr(owner, "premium_tier", "free") or "free",
        } if owner else None,
        "post_count": crud.count_series_posts(db, series.id, approved_only=True),
        "created_at": series.created_at.isoformat() if series.created_at else None,
        "updated_at": series.updated_at.isoformat() if series.updated_at else None,
    }


def serialize_comment(
    comment,
    db: Optional[Session] = None,
    reaction_counts: Optional[dict[str, int]] = None,
    viewer_reaction: Optional[str] = None,
):
    """Serialize a comment for JSON response"""
    content = rich_text.sanitize_rich_text(comment.content)
    if db is not None:
        content = crud.link_mentions_in_rich_text(db, comment.content)
    if reaction_counts is None:
        if db is not None:
            summary = crud.comment_reaction_summary(db, comment.id)
            reaction_counts = summary["counts"]
        else:
            reaction_counts = crud.empty_comment_reaction_counts()
    result = {
        "id": comment.id,
        "post_id": comment.post_id,
        "user_id": comment.user_id,
        "author_name": comment.author_name,
        "author_email": comment.author_email,
        "content": content,
        "approved": comment.approved,
        "is_robot": getattr(comment, "is_robot", False),
        "moderation_status": comment.moderation_status,
        "reaction_counts": reaction_counts,
        "reaction_total": sum(int(value or 0) for value in reaction_counts.values()),
        "viewer_reaction": viewer_reaction,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "user": None,
    }
    if comment.commenter:
        result["user"] = {
            "username": comment.commenter.username,
            "avatar_seed": comment.commenter.avatar_seed or f"{comment.commenter.username}-shapes",
            "is_premium": getattr(comment.commenter, "is_premium", False),
            "premium_tier": getattr(comment.commenter, "premium_tier", "free") or "free",
        }
    return result


def compute_comment_reaction_fields(db: Session, comments, current_user):
    if not comments:
        return {}, {}
    comment_ids = [comment.id for comment in comments]
    counts = {
        comment_id: crud.empty_comment_reaction_counts()
        for comment_id in comment_ids
    }
    for comment_id, reaction_type, count in (
        db.query(
            models.CommentReaction.comment_id,
            models.CommentReaction.reaction_type,
            func.count(models.CommentReaction.id),
        )
        .filter(models.CommentReaction.comment_id.in_(comment_ids))
        .group_by(models.CommentReaction.comment_id, models.CommentReaction.reaction_type)
        .all()
    ):
        if reaction_type in counts[comment_id]:
            counts[comment_id][reaction_type] = int(count or 0)

    viewer = {}
    if current_user:
        viewer = {
            comment_id: reaction_type
            for comment_id, reaction_type in (
                db.query(models.CommentReaction.comment_id, models.CommentReaction.reaction_type)
                .filter(
                    models.CommentReaction.user_id == current_user.id,
                    models.CommentReaction.comment_id.in_(comment_ids),
                )
                .all()
            )
        }
    return counts, viewer


@router.get("/api/prima-pagina")
@router.get("/api/landing", include_in_schema=False)
def landing_data(
    request: Request,
    category: str = "toate",
    post_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Landing page data: one random post for the selected category."""
    statistics.record_view(db, request, "landing", None, "home", None, current_user)
    selected_post = crud.get_post(db, post_id) if post_id else None
    if selected_post and selected_post.moderation_status == "approved" and (
        category == "toate" or selected_post.category == category
    ):
        random_posts = [selected_post]
    elif category == "toate":
        random_posts = crud.get_weighted_random_posts(db, limit=1)
    elif category in CATEGORIES:
        random_posts = crud.get_weighted_random_posts_by_category(db, category, limit=1)
    else:
        random_posts = []

    for post in random_posts:
        statistics.record_view(db, request, "post", post.id, post.slug, post.user_id, current_user)

    return {
        "random_posts": serialize_posts_with_super_likes(db, random_posts, current_user, include_owner=True, include_comments=True, request=request),
        "stats": crud.get_platform_stats(db),
    }


@router.get("/api/bloguri/{username}")
def blog_data(
    request: Request,
    username: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Blog homepage data for a specific user"""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")

    statistics.record_view(db, request, "blog", user.id, username, user.id, current_user)

    cache_key = _public_cache_key(db, request, current_user, "blog", user.id, month or 0, year or 0)
    cached_payload = cache.public_cache.get(cache_key) if cache_key else None
    if cached_payload is not None:
        return cached_payload

    # Promoted slots on the public profile.
    promoted_own_entries = crud.get_promoted_own_post_entries_for_user(db, user.id)
    promoted_other_entries = crud.get_promoted_other_post_entries_for_user(db, user.id)
    promoted_own_posts = [entry.post for entry in promoted_own_entries if entry.post]
    promoted_other_posts = [entry.post for entry in promoted_other_entries if entry.post]

    # Latest posts
    latest_posts = crud.get_latest_posts_for_user(db, user.id, limit=3)

    # All posts (filtered by month/year)
    if month and year:
        all_posts = crud.get_posts_by_month_year(db, user.id, month, year, limit=50)
    else:
        all_posts = crud.get_latest_posts_for_user(db, user.id, limit=50)

    # Available months
    available_months = crud.get_available_months_for_user(db, user.id)

    # Promoted authors
    promoted_author_entries = crud.get_promoted_authors_for_user(db, user.id)
    promoted_authors = []
    for bf in promoted_author_entries:
        friend_user = bf.friend if hasattr(bf, 'friend') else None
        if friend_user:
            promoted_authors.append({
                "user": serialize_user(friend_user),
                "position": bf.position,
            })

    # Awards and stats
    user_awards = crud.get_user_awards(db, user.id)
    total_likes = crud.get_user_total_likes(db, user.id)
    total_comments = crud.get_user_total_comments(db, user.id)
    category_counts = crud.get_user_post_counts_by_category(db, user.id)

    # Blog categories
    blog_categories = crud.get_distinct_categories_used(db, user_id=user.id)
    user_series = [
        serialize_series_summary(db, series)
        for series in crud.get_series_by_owner(db, user.id)
    ]
    user_series = [series for series in user_series if series["post_count"] > 0]
    viewer_friendship = crud.get_friendship_between(db, current_user.id, user.id) if current_user and current_user.id != user.id else None

    payload = {
        "blog_owner": serialize_user(user),
        "featured_posts": serialize_posts_with_super_likes(db, promoted_own_posts, current_user, request=request),
        "promoted_own_posts": serialize_posts_with_super_likes(db, promoted_own_posts, current_user, include_owner=True, request=request),
        "promoted_authors": promoted_authors,
        "promoted_external_posts": serialize_posts_with_super_likes(db, promoted_other_posts, current_user, include_owner=True, request=request),
        "latest_posts": serialize_posts_with_super_likes(db, latest_posts, current_user, request=request),
        "all_posts": serialize_posts_with_super_likes(db, all_posts, current_user, request=request),
        "available_months": [
            {"month": m["month"], "year": m["year"], "count": m["post_count"]}
            for m in available_months
        ] if available_months else [],
        "blog_categories": blog_categories or [],
        "best_friends": promoted_authors,
        "friend_count": crud.get_friend_count_for_user(db, user.id),
        "follower_count": crud.get_follower_count_for_user(db, user.id),
        "following_count": crud.get_following_count_for_user(db, user.id),
        "ready_audio_count": crud.get_ready_audio_post_count_for_author(db, user.id),
        "viewer_friendship_status": crud.get_friendship_status_for_viewer(
            db,
            current_user.id if current_user else None,
            user.id,
        ),
        "viewer_friendship_id": viewer_friendship.id if viewer_friendship else None,
        "viewer_following": (
            bool(current_user)
            and current_user.id != user.id
            and crud.is_following(db, current_user.id, user.id)
        ),
        "viewer_promoted_author": (
            bool(current_user)
            and current_user.id != user.id
            and crud.is_author_promoted_by_user(db, current_user.id, user.id)
        ),
        "promotion_limits": crud.promotion_limits(),
        "user_awards": [
            {
                "id": a.id,
                "achievement_key": a.achievement_key,
                "award_title": a.award_title,
                "award_description": a.award_description,
                "award_date": a.award_date.isoformat() if a.award_date else None,
                "award_type": a.award_type,
                "awarded_at": a.awarded_at.isoformat() if a.awarded_at else None,
                "source_type": a.source_type,
                "source_id": a.source_id,
                "metadata": a.extra_data or {},
            }
            for a in (user_awards or [])
        ],
        "total_likes": total_likes or 0,
        "total_comments": total_comments or 0,
        "category_counts": [
            {"category": key, "category_name": get_category_name(key), "count": category_counts.get(key, 0)}
            for key in CATEGORIES
        ],
        "series": user_series,
    }
    if cache_key:
        cache.public_cache.set(cache_key, payload)
    return payload


@router.get("/api/bloguri/{username}/toate-operele")
def blog_all_works_data(
    request: Request,
    username: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """All approved posts for a public author profile."""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")

    cache_key = _public_cache_key(db, request, current_user, "all_works", user.id)
    cached_payload = cache.public_cache.get(cache_key) if cache_key else None
    if cached_payload is not None:
        return cached_payload

    posts = (
        db.query(models.Post)
        .filter(
            models.Post.user_id == user.id,
            models.Post.moderation_status == "approved",
        )
        .order_by(models.Post.created_at.desc(), models.Post.id.desc())
        .all()
    )
    category_counts = crud.get_user_post_counts_by_category(db, user.id)

    payload = {
        "blog_owner": serialize_user(user),
        "posts": serialize_posts_with_super_likes(db, posts, current_user, request=request),
        "category_counts": [
            {"category": key, "category_name": get_category_name(key), "count": category_counts.get(key, 0)}
            for key in CATEGORIES
        ],
    }
    if cache_key:
        cache.public_cache.set(cache_key, payload)
    return payload


@router.get("/api/bloguri/{username}/postari/{slug}")
def post_detail_data(
    request: Request,
    username: str,
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Post detail page data"""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")

    post = crud.get_post_by_slug(db, slug)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    can_view_pending = bool(
        current_user
        and (
            current_user.id == post.user_id
            or current_user.is_admin
            or current_user.is_moderator
        )
    )
    if post.moderation_status == "rejected" or crud.content_has_human_rejection(db, "post", post.id):
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    if post.moderation_status != "approved" and not can_view_pending:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    # Track view with bot detection and deduplication
    statistics.record_view(db, request, "post", post.id, post.slug, post.user_id, current_user)

    # Related posts from same user
    related_posts = crud.get_latest_posts_for_user(db, user.id, limit=5)
    related_posts = [p for p in related_posts if p.id != post.id][:3]

    # Random other authors
    other_authors = crud.get_random_users(db, limit=8)
    other_authors = [u for u in other_authors if u.id != user.id][:5]

    # Serialize post with comments (bulk-compute super-like fields for post + related posts in one pass)
    post_group = [post] + list(related_posts)
    counts, liked = compute_super_like_fields(db, post_group, current_user)
    viewer_liked = compute_like_fields(db, post_group, current_user, request)
    promoted = compute_promoted_post_fields(db, post_group, current_user)
    approved_comments = visible_comments_for_post(db, post.id)
    post_data = serialize_post(
        post,
        super_likes_count=counts.get(post.id, 0),
        viewer_super_liked=liked.get(post.id, False),
        viewer_liked=viewer_liked.get(post.id, False),
        comments_count=len(approved_comments),
        viewer_promoted=promoted.get(post.id, False),
    )
    comment_reaction_counts, comment_viewer_reactions = compute_comment_reaction_fields(db, approved_comments, current_user)
    post_data["approved_comments"] = [
        serialize_comment(
            c,
            db,
            reaction_counts=comment_reaction_counts.get(c.id),
            viewer_reaction=comment_viewer_reactions.get(c.id),
        )
        for c in approved_comments
    ]
    series_context = crud.get_series_context_for_post(db, post, include_unapproved=can_view_pending)

    return {
        "blog_owner": serialize_user(user),
        "post": post_data,
        "series_context": series_context,
        "related_posts": [
            serialize_post(
                p,
                super_likes_count=counts.get(p.id, 0),
                viewer_super_liked=liked.get(p.id, False),
                viewer_liked=viewer_liked.get(p.id, False),
                viewer_promoted=promoted.get(p.id, False),
            )
            for p in related_posts
        ],
        "other_authors": [serialize_user(u) for u in other_authors],
    }


@router.get("/api/bloguri/{username}/postari/{slug}/pdf")
def post_pdf_download(
    request: Request,
    username: str,
    slug: str,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")

    post = crud.get_post_by_slug(db, slug)
    if not post or post.user_id != user.id or post.moderation_status != "approved":
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    page_url = pdf_exporter.post_page_url(request, user.username, post.slug)
    pdf_bytes = pdf_exporter.render_post_pdf(
        post=post,
        author=user,
        page_url=page_url,
        category_label=get_category_name(post.category) if post.category else "",
    )
    return Response(
        content=pdf_bytes,
        media_type=pdf_exporter.PDF_MEDIA_TYPE,
        headers=pdf_exporter.pdf_response_headers(post.slug),
    )


@router.get("/api/utilizator/{username}/profil")
def user_public_profile(
    username: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Public user profile data"""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")

    payload = serialize_user(user)
    payload["friend_count"] = crud.get_friend_count_for_user(db, user.id)
    payload["follower_count"] = crud.get_follower_count_for_user(db, user.id)
    payload["following_count"] = crud.get_following_count_for_user(db, user.id)
    viewer_friendship = crud.get_friendship_between(db, current_user.id, user.id) if current_user and current_user.id != user.id else None
    payload["viewer_friendship_status"] = crud.get_friendship_status_for_viewer(
        db,
        current_user.id if current_user else None,
        user.id,
    )
    payload["viewer_friendship_id"] = viewer_friendship.id if viewer_friendship else None
    payload["viewer_following"] = (
        bool(current_user)
        and current_user.id != user.id
        and crud.is_following(db, current_user.id, user.id)
    )
    return payload


@router.get("/api/utilizator/{username}/inventar")
def user_public_inventory(
    username: str,
    db: Session = Depends(get_db),
):
    """Public read-only inventory for a user profile."""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")

    inventory = crud.get_inventory_for_user(db, user.id)
    equipped = crud.get_equipped_items_for_user(db, user.id)
    equipped_ids = {entry.item_id for entry in equipped}

    return {
        "owner": serialize_user(user),
        "inventory": [
            serialize_inventory_item(entry, equipped_ids)
            for entry in inventory
            if entry.item
        ],
        "equipped": [
            serialize_equipped_item(entry)
            for entry in equipped
            if entry.item
        ],
    }
