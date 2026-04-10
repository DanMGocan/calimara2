"""
JSON API endpoints that serve the data previously embedded in Jinja2 templates.
These endpoints power the React frontend.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, crud, auth, statistics
from ..database import get_db
from ..utils import MAIN_DOMAIN, SUBDOMAIN_SUFFIX, get_avatar_url
from ..categories import (
    CATEGORIES_AND_GENRES, get_main_categories, get_all_categories,
    get_genres_for_category, get_category_name, get_genre_name,
    is_valid_category, is_valid_genre
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api-pages"])


def serialize_user(user):
    """Serialize a user object to dict for JSON response"""
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": user.subtitle,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "facebook_url": getattr(user, 'facebook_url', None),
        "tiktok_url": getattr(user, 'tiktok_url', None),
        "instagram_url": getattr(user, 'instagram_url', None),
        "x_url": getattr(user, 'x_url', None),
        "bluesky_url": getattr(user, 'bluesky_url', None),
        "patreon_url": getattr(user, 'patreon_url', None),
        "paypal_url": getattr(user, 'paypal_url', None),
        "buymeacoffee_url": getattr(user, 'buymeacoffee_url', None),
    }


def serialize_post(post, include_owner=False):
    """Serialize a post object to dict for JSON response"""
    result = {
        "id": post.id,
        "user_id": post.user_id,
        "title": post.title,
        "slug": post.slug,
        "content": post.content,
        "category": post.category,
        "genre": post.genre,
        "view_count": post.view_count,
        "likes_count": post.likes_count,
        "moderation_status": post.moderation_status,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        "tags": [{"id": t.id, "tag_name": t.tag_name} for t in (post.tags or [])],
    }
    if include_owner and post.owner:
        result["owner"] = {
            "id": post.owner.id,
            "username": post.owner.username,
            "avatar_seed": post.owner.avatar_seed or f"{post.owner.username}-shapes",
            "subtitle": post.owner.subtitle,
        }
    return result


def serialize_comment(comment):
    """Serialize a comment for JSON response"""
    result = {
        "id": comment.id,
        "post_id": comment.post_id,
        "user_id": comment.user_id,
        "author_name": comment.author_name,
        "author_email": comment.author_email,
        "content": comment.content,
        "approved": comment.approved,
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


@router.get("/api/landing")
async def landing_data(
    request: Request,
    category: str = "toate",
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Landing page data: random posts and users"""
    statistics.record_view(db, request, "landing", None, "home", None, current_user)
    if category == "toate":
        random_posts = crud.get_random_posts(db, limit=10)
    else:
        category_mapping = {
            "poezie": "poezie",
            "proza": "proza",
            "teatru": "teatru",
            "eseu": "eseu",
            "critica_literara": "critica_literara",
            "jurnal": "jurnal",
            "altele": ["literatura_experimentala", "scrisoare"],
        }
        if category in category_mapping:
            mapped = category_mapping[category]
            if isinstance(mapped, list):
                random_posts = crud.get_random_posts_by_categories(db, mapped, limit=10)
            else:
                random_posts = crud.get_random_posts_by_category(db, mapped, limit=10)
        else:
            random_posts = []

    random_users = crud.get_random_users(db, limit=10)

    return {
        "random_posts": [serialize_post(p, include_owner=True) for p in random_posts],
        "random_users": [serialize_user(u) for u in random_users],
        "categories": CATEGORIES_AND_GENRES,
        "main_categories": get_main_categories(),
        "selected_category": category,
    }


@router.get("/api/blog/{username}")
async def blog_data(
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
        raise HTTPException(status_code=404, detail="Blogul nu a fost gasit")

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

    # Blog categories
    blog_categories = crud.get_distinct_categories_used(db, user_id=user.id)

    return {
        "blog_owner": serialize_user(user),
        "featured_posts": [serialize_post(p) for p in featured_posts],
        "latest_posts": [serialize_post(p) for p in latest_posts],
        "all_posts": [serialize_post(p) for p in all_posts],
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
    }


@router.get("/api/blog/{username}/post/{slug}")
async def post_detail_data(
    request: Request,
    username: str,
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Post detail page data"""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Blogul nu a fost gasit")

    post = crud.get_post_by_slug(db, slug)
    if not post or post.user_id != user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost gasita")

    # Track view with bot detection and deduplication
    statistics.record_view(db, request, "post", post.id, post.slug, post.user_id, current_user)

    # Related posts from same user
    related_posts = crud.get_posts_by_user(db, user.id, limit=5)
    related_posts = [p for p in related_posts if p.id != post.id][:3]

    # Posts from other authors
    other_authors_posts = crud.get_random_posts(db, limit=10)
    other_authors_posts = [p for p in other_authors_posts if p.user_id != user.id][:4]

    # Random other authors
    other_authors = crud.get_random_users(db, limit=8)
    other_authors = [u for u in other_authors if u.id != user.id][:5]

    # Serialize post with comments
    post_data = serialize_post(post)
    post_data["approved_comments"] = [
        serialize_comment(c) for c in (post.approved_comments or [])
    ]

    return {
        "blog_owner": serialize_user(user),
        "post": post_data,
        "related_posts": [serialize_post(p) for p in related_posts],
        "other_authors_posts": [serialize_post(p, include_owner=True) for p in other_authors_posts],
        "other_authors": [serialize_user(u) for u in other_authors],
    }


@router.get("/api/categories/{category_key}")
async def category_page_data(
    request: Request,
    category_key: str,
    sort_by: str = "newest",
    db: Session = Depends(get_db),
):
    """Category page data"""
    if not is_valid_category(category_key):
        raise HTTPException(status_code=404, detail="Categoria nu a fost gasita")

    posts = crud.get_posts_by_category_sorted(db, category_key, sort_by=sort_by, limit=6)
    statistics.record_view(db, request, "category", None, category_key, None, None)

    return {
        "category_key": category_key,
        "category_name": get_category_name(category_key),
        "genres": get_genres_for_category(category_key),
        "posts": [serialize_post(p, include_owner=True) for p in posts],
        "sort_by": sort_by,
    }


@router.get("/api/categories/{category_key}/{genre_key}")
async def genre_page_data(
    request: Request,
    category_key: str,
    genre_key: str,
    sort_by: str = "newest",
    db: Session = Depends(get_db),
):
    """Genre page data"""
    if not is_valid_category(category_key) or not is_valid_genre(category_key, genre_key):
        raise HTTPException(status_code=404, detail="Categoria sau genul nu a fost gasit")

    posts = crud.get_posts_by_category_sorted(db, category_key, genre_key, sort_by=sort_by, limit=6)
    statistics.record_view(db, request, "genre", None, f"{category_key}/{genre_key}", None, None)

    return {
        "category_key": category_key,
        "category_name": get_category_name(category_key),
        "genre_key": genre_key,
        "genre_name": get_genre_name(category_key, genre_key),
        "genres": get_genres_for_category(category_key),
        "posts": [serialize_post(p, include_owner=True) for p in posts],
        "sort_by": sort_by,
    }


@router.get("/api/user/{username}/profile")
async def user_public_profile(
    username: str,
    db: Session = Depends(get_db),
):
    """Public user profile data"""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost gasit")

    return serialize_user(user)
