import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models, schemas, auth, crud
from ..database import get_db
from ..utils import validate_social_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])


@router.get("/api/user/me")
def get_current_user_info(current_user: Optional[models.User] = Depends(auth.get_current_user)):
    """Endpoint to check current user authentication status"""
    if current_user:
        data = {
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "subtitle": current_user.subtitle,
                "avatar_seed": current_user.avatar_seed,
                "is_admin": current_user.is_admin,
                "is_moderator": current_user.is_moderator,
                "is_suspended": current_user.is_suspended,
                "is_premium": current_user.is_premium,
                "premium_until": current_user.premium_until.isoformat() if current_user.premium_until else None,
            }
        }
    else:
        data = {"authenticated": False, "user": None}
    response = JSONResponse(content=data)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.put("/api/user/me", response_model=schemas.UserInDB)
def update_current_user(
    user_update: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea profilului pentru utilizatorul: {current_user.username}")

    # Update subtitle
    if user_update.subtitle is not None:
        current_user.subtitle = user_update.subtitle

    # Update avatar seed
    if user_update.avatar_seed is not None:
        current_user.avatar_seed = user_update.avatar_seed

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Profil utilizator actualizat cu succes: {current_user.username}")
    return current_user


@router.put("/api/user/social-links", response_model=schemas.UserInDB)
def update_user_social_links(
    social_update: schemas.SocialLinksUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    logger.info(f"Se încearcă actualizarea link-urilor sociale pentru utilizatorul: {current_user.username}")

    # Validate URLs for each platform
    validation_errors = []

    if social_update.facebook_url and not validate_social_url(social_update.facebook_url, 'facebook'):
        validation_errors.append("URL-ul Facebook trebuie să conțină facebook.com sau fb.com")

    if social_update.instagram_url and not validate_social_url(social_update.instagram_url, 'instagram'):
        validation_errors.append("URL-ul Instagram trebuie să conțină instagram.com")

    if social_update.tiktok_url and not validate_social_url(social_update.tiktok_url, 'tiktok'):
        validation_errors.append("URL-ul TikTok trebuie să conțină tiktok.com")

    if social_update.x_url and not validate_social_url(social_update.x_url, 'x'):
        validation_errors.append("URL-ul X trebuie să conțină x.com sau twitter.com")

    if social_update.bluesky_url and not validate_social_url(social_update.bluesky_url, 'bluesky'):
        validation_errors.append("URL-ul BlueSky trebuie să conțină bsky.app")

    if social_update.buymeacoffee_url and not validate_social_url(social_update.buymeacoffee_url, 'buymeacoffee'):
        validation_errors.append("URL-ul Cumpără-mi o cafea trebuie să conțină buymeacoffee.com")

    if validation_errors:
        raise HTTPException(status_code=422, detail="; ".join(validation_errors))

    # Update social media links
    if social_update.facebook_url is not None:
        current_user.facebook_url = social_update.facebook_url.strip() or None
    if social_update.tiktok_url is not None:
        current_user.tiktok_url = social_update.tiktok_url.strip() or None
    if social_update.instagram_url is not None:
        current_user.instagram_url = social_update.instagram_url.strip() or None
    if social_update.x_url is not None:
        current_user.x_url = social_update.x_url.strip() or None
    if social_update.bluesky_url is not None:
        current_user.bluesky_url = social_update.bluesky_url.strip() or None

    # Update donation links
    if social_update.buymeacoffee_url is not None:
        current_user.buymeacoffee_url = social_update.buymeacoffee_url.strip() or None

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    logger.info(f"Link-uri sociale actualizate cu succes pentru utilizatorul: {current_user.username}")
    return current_user


@router.put("/api/user/best-friends")
def update_best_friends(
    best_friends_data: schemas.BestFriendsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Update user's best friends list (max 3 friends)"""
    try:
        friend_usernames = best_friends_data.friends

        # Validate max 3 friends
        if len(friend_usernames) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 best friends allowed")

        # Remove existing best friends using ORM
        db.query(models.BestFriend).filter(models.BestFriend.user_id == current_user.id).delete()

        # Add new best friends
        for position, username in enumerate(friend_usernames, 1):
            if username.strip():  # Skip empty usernames
                friend = db.query(models.User).filter(models.User.username == username.strip()).first()
                if friend and friend.id != current_user.id:  # Can't add self as best friend
                    new_friendship = models.BestFriend(
                        user_id=current_user.id,
                        friend_user_id=friend.id,
                        position=position
                    )
                    db.add(new_friendship)

        db.commit()
        logger.info(f"Best friends actualizați pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Best friends updated successfully"}

    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea best friends pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update best friends")


@router.get("/api/users/search")
def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Search for users by username for best friends selection"""
    if len(q.strip()) < 2:
        return []

    users = db.query(models.User).filter(
        models.User.username.contains(q.strip()),
        models.User.id != current_user.id  # Exclude current user
    ).limit(10).all()

    return [{"username": user.username, "subtitle": user.subtitle} for user in users]


@router.get("/api/users/random")
def get_random_user(db: Session = Depends(get_db)):
    """Return a single random user who has at least one approved post."""
    user = crud.get_random_user_with_posts(db)
    if not user:
        raise HTTPException(status_code=404, detail="No authors available")
    return {
        "id": user.id,
        "username": user.username,
        "subtitle": user.subtitle,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
    }


@router.put("/api/user/featured-posts")
def update_featured_posts(
    featured_posts_data: schemas.FeaturedPostsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Update user's featured posts list (max 3 posts)"""
    try:
        post_ids = featured_posts_data.post_ids

        # Validate max 3 posts
        if len(post_ids) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 featured posts allowed")

        # Validate that all posts belong to the user
        for post_id in post_ids:
            if post_id:  # Skip empty IDs
                post = db.query(models.Post).filter(
                    models.Post.id == post_id,
                    models.Post.user_id == current_user.id
                ).first()
                if not post:
                    raise HTTPException(status_code=400, detail=f"Post {post_id} not found or not owned by user")

        # Remove existing featured posts using ORM
        db.query(models.FeaturedPost).filter(models.FeaturedPost.user_id == current_user.id).delete()

        # Add new featured posts
        for position, post_id in enumerate(post_ids, 1):
            if post_id:  # Skip empty post IDs
                new_featured = models.FeaturedPost(
                    user_id=current_user.id,
                    post_id=post_id,
                    position=position
                )
                db.add(new_featured)

        db.commit()
        logger.info(f"Featured posts actualizate pentru utilizatorul: {current_user.username}")
        return {"success": True, "message": "Featured posts updated successfully"}

    except Exception as e:
        db.rollback()
        logger.error(f"Eroare la actualizarea featured posts pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update featured posts")
