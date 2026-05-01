"""
JSON API endpoints that serve the data previously embedded in Jinja2 templates.
These endpoints power the React frontend.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from sqlalchemy import func

from .. import models, crud, auth, statistics, pdf_exporter, profile_media, rich_text
from ..database import get_db
from ..utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX, get_avatar_url
from ..categories import CATEGORIES, get_category_name

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api-pages"])


def serialize_user(user):
    """Serialize a user object to dict for JSON response"""
    profile_photo_url = None
    cover_photo_url = None
    if getattr(user, "is_premium", False):
        if getattr(user, "profile_photo_storage_key", None):
            profile_photo_url = profile_media.public_media_url(user.username, "profil")
        if getattr(user, "cover_photo_storage_key", None):
            cover_photo_url = profile_media.public_media_url(user.username, "coperta")
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
        "avatar_url": profile_photo_url or get_avatar_url(user, size=160),
        "profile_photo_url": profile_photo_url,
        "cover_photo_url": cover_photo_url,
        "has_profile_photo": bool(getattr(user, "profile_photo_storage_key", None)),
        "has_cover_photo": bool(getattr(user, "cover_photo_storage_key", None)),
        "location": getattr(user, "location", None),
        "youtube_playlist_url": getattr(user, "youtube_playlist_url", None),
        "is_premium": getattr(user, "is_premium", False),
        "gologani_balance": getattr(user, "gologani_balance", 0) or 0,
        "equipped_items": equipped_items,
        "facebook_url": getattr(user, 'facebook_url', None),
        "tiktok_url": getattr(user, 'tiktok_url', None),
        "instagram_url": getattr(user, 'instagram_url', None),
        "x_url": getattr(user, 'x_url', None),
        "bluesky_url": getattr(user, 'bluesky_url', None),
        "patreon_url": getattr(user, 'patreon_url', None),
        "paypal_url": getattr(user, 'paypal_url', None),
        "buymeacoffee_url": getattr(user, 'buymeacoffee_url', None),
    }


def serialize_post(post, include_owner=False, super_likes_count=None, viewer_super_liked=False):
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
        "category": post.category,
        "category_name": get_category_name(post.category) if post.category else "",
        "view_count": post.view_count,
        "likes_count": post.likes_count,
        "super_likes_count": super_likes_count,
        "viewer_super_liked": viewer_super_liked,
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


def serialize_posts_with_super_likes(db, posts, current_user, include_owner=False):
    """Serialize a list of posts with efficient bulk super-like lookups."""
    counts, liked = compute_super_like_fields(db, posts, current_user)
    return [
        serialize_post(
            p,
            include_owner=include_owner,
            super_likes_count=counts.get(p.id, 0),
            viewer_super_liked=liked.get(p.id, False),
        )
        for p in posts
    ]


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
        } if owner else None,
        "post_count": crud.count_series_posts(db, series.id, approved_only=True),
        "created_at": series.created_at.isoformat() if series.created_at else None,
        "updated_at": series.updated_at.isoformat() if series.updated_at else None,
    }


def serialize_comment(comment):
    """Serialize a comment for JSON response"""
    result = {
        "id": comment.id,
        "post_id": comment.post_id,
        "user_id": comment.user_id,
        "author_name": comment.author_name,
        "author_email": comment.author_email,
        "content": rich_text.sanitize_rich_text(comment.content),
        "approved": comment.approved,
        "is_robot": getattr(comment, "is_robot", False),
        "moderation_status": comment.moderation_status,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "user": None,
    }
    if comment.commenter:
        result["user"] = {
            "username": comment.commenter.username,
            "avatar_seed": comment.commenter.avatar_seed or f"{comment.commenter.username}-shapes",
        }
    return result


@router.get("/api/prima-pagina")
@router.get("/api/landing", include_in_schema=False)
def landing_data(
    request: Request,
    category: str = "toate",
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Landing page data: one random post for the selected category."""
    statistics.record_view(db, request, "landing", None, "home", None, current_user)
    if category == "toate":
        random_posts = crud.get_weighted_random_posts(db, limit=1)
    elif category in CATEGORIES:
        random_posts = crud.get_weighted_random_posts_by_category(db, category, limit=1)
    else:
        random_posts = []

    return {
        "random_posts": serialize_posts_with_super_likes(db, random_posts, current_user, include_owner=True),
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

    # Featured posts
    featured_posts_data = crud.get_featured_posts_for_user(db, user.id)
    featured_posts = [fp.post for fp in featured_posts_data]

    # Latest posts
    latest_posts = crud.get_latest_posts_for_user(db, user.id, limit=3)

    # All posts (filtered by month/year)
    if month and year:
        all_posts = crud.get_posts_by_month_year(db, user.id, month, year, limit=50)
    else:
        all_posts = crud.get_latest_posts_for_user(db, user.id, limit=50)

    # Available months
    available_months = crud.get_available_months_for_user(db, user.id)

    # Best friends
    best_friends_data = crud.get_best_friends_for_user(db, user.id)
    best_friends = []
    for bf in best_friends_data:
        friend_user = bf.friend if hasattr(bf, 'friend') else None
        if friend_user:
            best_friends.append({
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

    return {
        "blog_owner": serialize_user(user),
        "featured_posts": serialize_posts_with_super_likes(db, featured_posts, current_user),
        "latest_posts": serialize_posts_with_super_likes(db, latest_posts, current_user),
        "all_posts": serialize_posts_with_super_likes(db, all_posts, current_user),
        "available_months": [
            {"month": m["month"], "year": m["year"], "count": m["post_count"]}
            for m in available_months
        ] if available_months else [],
        "blog_categories": blog_categories or [],
        "best_friends": best_friends,
        "user_awards": [
            {
                "id": a.id,
                "award_title": a.award_title,
                "award_description": a.award_description,
                "award_date": a.award_date.isoformat() if a.award_date else None,
                "award_type": a.award_type,
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
    counts, liked = compute_super_like_fields(db, [post] + list(related_posts), current_user)
    post_data = serialize_post(
        post,
        super_likes_count=counts.get(post.id, 0),
        viewer_super_liked=liked.get(post.id, False),
    )
    post_data["approved_comments"] = [
        serialize_comment(c) for c in (post.approved_comments or [])
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


@router.get("/api/categorii/{category_key}")
def category_page_data(
    request: Request,
    category_key: str,
    sort_by: str = "newest",
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Category page data"""
    if category_key not in CATEGORIES:
        raise HTTPException(status_code=404, detail="Categoria nu a fost găsită")

    posts = crud.get_posts_by_category_sorted(db, category_key, sort_by=sort_by, limit=6)
    statistics.record_view(db, request, "category", None, category_key, None, None)

    return {
        "category_key": category_key,
        "category_name": get_category_name(category_key),
        "posts": serialize_posts_with_super_likes(db, posts, current_user, include_owner=True),
        "sort_by": sort_by,
    }


@router.get("/api/utilizator/{username}/profil")
def user_public_profile(
    username: str,
    db: Session = Depends(get_db),
):
    """Public user profile data"""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")

    return serialize_user(user)
