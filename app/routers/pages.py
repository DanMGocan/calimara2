import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models, crud, auth, admin
from ..database import get_db
from ..utils import templates, get_common_context, MAIN_DOMAIN, SUBDOMAIN_SUFFIX
from ..categories import (
    CATEGORIES_AND_GENRES, get_main_categories, get_all_categories,
    get_genres_for_category, get_category_name, get_genre_name,
    is_valid_category, is_valid_genre
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, category: str = "toate", month: int = None, year: int = None, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    # If it's a subdomain, render the blog page
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")

        # Get featured posts for the blog owner
        featured_posts_data = crud.get_featured_posts_for_user(db, user.id)
        featured_posts = [fp.post for fp in featured_posts_data]

        # Get latest 3 posts
        latest_posts = crud.get_latest_posts_for_user(db, user.id, limit=3)

        # Get all posts for archive with statistics (filtered by month/year if provided)
        if month and year:
            all_posts = crud.get_posts_by_month_year(db, user.id, month, year, limit=50)
        else:
            all_posts = crud.get_latest_posts_for_user(db, user.id, limit=50)

        # Get available months for filtering
        available_months = crud.get_available_months_for_user(db, user.id)

        # Get best friends for the blog owner
        best_friends = crud.get_best_friends_for_user(db, user.id)

        # Get user awards and statistics
        user_awards = crud.get_user_awards(db, user.id)
        total_likes = crud.get_user_total_likes(db, user.id)
        total_comments = crud.get_user_total_comments(db, user.id)

        # Comments, tags, and likes are now eager-loaded via selectinload in CRUD queries.
        # Use post.approved_comments in templates for approved-only comments.

        # Get distinct categories for this user's blog
        blog_categories = crud.get_distinct_categories_used(db, user_id=user.id)

        # Get user's dramas for blog sidebar
        user_dramas = crud.get_dramas_by_user(db, user.id, limit=5)

        context = get_common_context(request, current_user)
        context.update({
            "blog_owner": user,
            "featured_posts": featured_posts,
            "latest_posts": latest_posts,
            "all_posts": all_posts,
            "available_months": available_months,
            "blog_categories": blog_categories,
            "best_friends": best_friends,
            "user_awards": user_awards,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "user_dramas": user_dramas
        })
        return templates.TemplateResponse(request, "blog.html", context)
    else:
        # If not a subdomain (i.e., calimara.ro), always render the main landing page
        # Filter random posts based on category parameter
        if category == "toate":
            random_posts = crud.get_random_posts(db, limit=10)
        else:
            # Map category filter names to actual category keys
            category_mapping = {
                "poezie": "poezie",
                "proza": "proza",
                "teatru": "teatru",
                "eseu": "eseu",
                "critica_literara": "critica_literara",
                "jurnal": "jurnal",
                "altele": ["literatura_experimentala", "scrisoare"]  # Multiple categories for "altele"
            }

            if category in category_mapping:
                mapped_category = category_mapping[category]
                if isinstance(mapped_category, list):
                    # Handle multiple categories for "altele"
                    random_posts = crud.get_random_posts_by_categories(db, mapped_category, limit=10)
                else:
                    random_posts = crud.get_random_posts_by_category(db, mapped_category, limit=10)
            else:
                random_posts = []

        random_users = crud.get_random_users(db, limit=10)
        recent_dramas = crud.get_all_dramas(db, limit=6)
        context = get_common_context(request, current_user)
        context.update({
            "random_posts": random_posts,
            "random_users": random_users,
            "categories": CATEGORIES_AND_GENRES,  # Pass predefined categories for navigation
            "main_categories": get_main_categories(),  # Pass main categories for navigation
            "selected_category": category,  # Pass selected category for template
            "recent_dramas": recent_dramas
        })
        return templates.TemplateResponse(request, "index.html", context)


# Category and Genre Routes
@router.get("/category/{category_key}", response_class=HTMLResponse)
async def category_page(category_key: str, request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user), sort_by: str = "newest"):
    # Validate category
    if not is_valid_category(category_key):
        raise HTTPException(status_code=404, detail="Categoria nu a fost găsită")

    # Get posts for this category (comments, tags, likes are eager-loaded)
    posts = crud.get_posts_by_category_sorted(db, category_key, sort_by=sort_by, limit=6)

    context = get_common_context(request, current_user)
    context.update({
        "category_key": category_key,
        "category_name": get_category_name(category_key),
        "genres": get_genres_for_category(category_key),
        "posts": posts,
        "sort_by": sort_by,
        "categories": CATEGORIES_AND_GENRES
    })
    return templates.TemplateResponse(request, "category.html", context)


@router.get("/category/{category_key}/{genre_key}", response_class=HTMLResponse)
async def genre_page(category_key: str, genre_key: str, request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user), sort_by: str = "newest"):
    # Validate category and genre
    if not is_valid_category(category_key) or not is_valid_genre(category_key, genre_key):
        raise HTTPException(status_code=404, detail="Categoria sau genul nu a fost găsit")

    # Get posts for this category and genre (comments, tags, likes are eager-loaded)
    posts = crud.get_posts_by_category_sorted(db, category_key, genre_key, sort_by=sort_by, limit=6)

    context = get_common_context(request, current_user)
    context.update({
        "category_key": category_key,
        "category_name": get_category_name(category_key),
        "genre_key": genre_key,
        "genre_name": get_genre_name(category_key, genre_key),
        "posts": posts,
        "sort_by": sort_by,
        "categories": CATEGORIES_AND_GENRES
    })
    return templates.TemplateResponse(request, "genre.html", context)


# --- HTML Routes (Messages) ---

@router.get("/messages", response_class=HTMLResponse)
async def messages_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    """Messages inbox page"""
    # If logged in and on main domain, redirect to subdomain messages
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/messages", status_code=status.HTTP_302_FOUND)

    context = get_common_context(request, current_user)
    return templates.TemplateResponse(request, "messages.html", context)


@router.get("/messages/{conversation_id}", response_class=HTMLResponse)
async def conversation_page(conversation_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    """Individual conversation page"""
    # If logged in and on main domain, redirect to subdomain conversation
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/messages/{conversation_id}", status_code=status.HTTP_302_FOUND)

    # Verify user has access to this conversation
    conversation = crud.get_conversation_by_id(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    context = get_common_context(request, current_user)
    context.update({
        "conversation_id": conversation_id
    })
    return templates.TemplateResponse(request, "conversation.html", context)


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    # If logged in and on main domain, redirect to subdomain dashboard
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"https://{current_user.username}{SUBDOMAIN_SUFFIX}/dashboard", status_code=status.HTTP_302_FOUND)

    user_posts = crud.get_posts_by_user(db, current_user.id)
    # Comments are now auto-moderated by AI, no manual approval needed

    context = get_common_context(request, current_user)
    context.update({
        "user_posts": user_posts
    })
    return templates.TemplateResponse(request, "admin_dashboard.html", context)


@router.get("/create-post", response_class=HTMLResponse)
async def create_post_page(request: Request, current_user: models.User = Depends(auth.get_required_user)):
    # If logged in and on main domain, redirect to subdomain create-post
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/create-post", status_code=status.HTTP_302_FOUND)

    context = get_common_context(request, current_user)
    context.update({
        "categories": get_all_categories()
    })
    return templates.TemplateResponse(request, "create_post.html", context)


@router.get("/edit-post/{post_id}", response_class=HTMLResponse)
async def edit_post_page(post_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    # If logged in and on main domain, redirect to subdomain edit-post
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/edit-post/{post_id}", status_code=status.HTTP_302_FOUND)

    post = crud.get_post(db, post_id)
    if not post or post.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită sau nu aparține utilizatorului")
    context = get_common_context(request, current_user)
    context.update({
        "post": post
    })
    return templates.TemplateResponse(request, "edit_post.html", context)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: Optional[models.User] = Depends(auth.get_current_user)):
    # If logged in and on main domain, redirect to their subdomain
    if request.url.hostname == MAIN_DOMAIN and current_user:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(request, "register.html", get_common_context(request, current_user))


# ===================================
# ADMIN & MODERATION HTML ROUTES (before catch-all)
# ===================================

@router.get("/admin/moderation", response_class=HTMLResponse)
async def moderation_panel(
    request: Request,
    current_user: models.User = Depends(admin.require_moderator)
):
    """Admin moderation control panel - accessible to both admins and moderators"""
    # Always redirect to main domain for admin functions
    if request.url.hostname != MAIN_DOMAIN:
        return RedirectResponse(url=f"https://{MAIN_DOMAIN}/admin/moderation", status_code=status.HTTP_302_FOUND)

    context = get_common_context(request, current_user)
    logger.info(f"Moderation panel accessed by {current_user.username} (admin: {current_user.is_admin}, moderator: {current_user.is_moderator})")
    return templates.TemplateResponse(request, "admin_moderation.html", context)


# ===================================
# DRAMA PAGE ROUTES
# ===================================

@router.get("/piese", response_class=HTMLResponse)
async def drama_list_page(request: Request, status_filter: Optional[str] = None, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    """Drama listing page - on subdomain shows user's dramas, on main domain shows discovery"""
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost gasit")
        dramas = crud.get_dramas_by_user(db, user.id)
        participating = []
        if current_user:
            participating = crud.get_user_dramas_as_participant(db, current_user.id)
        context = get_common_context(request, current_user)
        context.update({
            "blog_owner": user,
            "dramas": dramas,
            "participating_dramas": participating,
            "is_discovery": False
        })
    else:
        dramas = crud.get_all_dramas(db, status_filter=status_filter)
        context = get_common_context(request, current_user)
        context.update({
            "dramas": dramas,
            "status_filter": status_filter,
            "is_discovery": True
        })
    return templates.TemplateResponse(request, "drama/list.html", context)


@router.get("/piese/creeaza", response_class=HTMLResponse)
async def drama_create_page(request: Request, current_user: models.User = Depends(auth.get_required_user)):
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/piese/creeaza", status_code=status.HTTP_302_FOUND)
    context = get_common_context(request, current_user)
    return templates.TemplateResponse(request, "drama/create.html", context)


@router.get("/piese/{slug}/gestioneaza", response_class=HTMLResponse)
async def drama_manage_page(request: Request, slug: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/piese/{slug}/gestioneaza", status_code=status.HTTP_302_FOUND)
    drama = crud.get_drama_by_slug(db, slug)
    if not drama or drama.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Piesa nu a fost gasita sau nu va apartine")
    pending_invitations = crud.get_pending_invitations_for_drama(db, drama.id)
    context = get_common_context(request, current_user)
    context.update({
        "drama": drama,
        "pending_invitations": pending_invitations
    })
    return templates.TemplateResponse(request, "drama/manage.html", context)


@router.get("/piese/{slug}", response_class=HTMLResponse)
async def drama_detail_page(request: Request, slug: str, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa nu a fost gasita")
    crud.increment_drama_view(db, drama.id)
    user_character = None
    if current_user:
        user_character = crud.get_character_for_user_in_drama(db, drama.id, current_user.id)
    context = get_common_context(request, current_user)
    context.update({
        "drama": drama,
        "blog_owner": drama.owner,
        "user_character": user_character
    })
    return templates.TemplateResponse(request, "drama/detail.html", context)


@router.get("/notificari", response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/notificari", status_code=status.HTTP_302_FOUND)
    context = get_common_context(request, current_user)
    return templates.TemplateResponse(request, "notifications.html", context)


# ===================================
# CATCH-ALL ROUTE (MUST be last)
# ===================================

@router.get("/{path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, path: str, month: int = None, year: int = None, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):

    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost găsit")

        # Check if path is a post slug
        if path and path != "":
            post = crud.get_post_by_slug(db, path)
            if post and post.user_id == user.id:
                # Increment view count
                crud.increment_post_view(db, post.id)

                # Comments, tags, and likes are eager-loaded on the post via relationships.
                # Use post.approved_comments in templates for approved-only comments.

                # Get related posts from same user
                related_posts = crud.get_posts_by_user(db, user.id, limit=5)
                related_posts = [p for p in related_posts if p.id != post.id][:3]

                # Get posts from other authors (excluding current author)
                other_authors_posts = crud.get_random_posts(db, limit=10)
                other_authors_posts = [p for p in other_authors_posts if p.user_id != user.id][:4]

                # Get random users (excluding current user)
                other_authors = crud.get_random_users(db, limit=8)
                other_authors = [u for u in other_authors if u.id != user.id][:5]

                context = get_common_context(request, current_user)
                context.update({
                    "blog_owner": user,
                    "post": post,
                    "related_posts": related_posts,
                    "other_authors_posts": other_authors_posts,
                    "other_authors": other_authors
                })
                return templates.TemplateResponse(request, "post_detail.html", context)

        # If no post slug or post not found, show blog homepage
        # Get featured posts for the blog owner
        featured_posts_data = crud.get_featured_posts_for_user(db, user.id)
        featured_posts = [fp.post for fp in featured_posts_data]

        # Get latest 3 posts
        latest_posts = crud.get_latest_posts_for_user(db, user.id, limit=3)

        # Get all posts for archive with statistics (filtered by month/year if provided)
        if month and year:
            all_posts = crud.get_posts_by_month_year(db, user.id, month, year, limit=50)
        else:
            all_posts = crud.get_latest_posts_for_user(db, user.id, limit=50)

        # Get available months for filtering
        available_months = crud.get_available_months_for_user(db, user.id)

        # Get best friends for the blog owner
        best_friends = crud.get_best_friends_for_user(db, user.id)

        # Get user awards and statistics
        user_awards = crud.get_user_awards(db, user.id)
        total_likes = crud.get_user_total_likes(db, user.id)
        total_comments = crud.get_user_total_comments(db, user.id)

        # Comments, tags, and likes are now eager-loaded via selectinload in CRUD queries.
        # Use post.approved_comments in templates for approved-only comments.

        # Get user's dramas for blog sidebar
        user_dramas = crud.get_dramas_by_user(db, user.id, limit=5)

        context = get_common_context(request, current_user)
        context.update({
            "blog_owner": user,
            "featured_posts": featured_posts,
            "latest_posts": latest_posts,
            "all_posts": all_posts,
            "available_months": available_months,
            "best_friends": best_friends,
            "user_awards": user_awards,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "user_dramas": user_dramas
        })
        return templates.TemplateResponse(request, "blog.html", context)
    else:
        # If not a subdomain and no specific route matched, return 404 for main domain
        raise HTTPException(status_code=404, detail="Pagina nu a fost găsită")
