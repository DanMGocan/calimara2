import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, crud, auth, admin, statistics
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["statistics"])


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Format dată invalid: {value}. Folosiți YYYY-MM-DD.")


@router.get("/api/stats/post/{post_id}")
async def post_stats(
    post_id: int,
    db: Session = Depends(get_db),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Statistics for a specific post."""
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    return statistics.get_post_stats(db, post_id, _parse_date(from_date), _parse_date(to_date))


@router.get("/api/stats/author/{username}")
async def author_stats(
    username: str,
    db: Session = Depends(get_db),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Statistics for a specific author."""
    user = crud.get_user_by_username(db, username=username)
    if not user:
        raise HTTPException(status_code=404, detail="Autorul nu a fost găsit")

    return statistics.get_author_stats(db, user.id, _parse_date(from_date), _parse_date(to_date))


@router.get("/api/stats/category/{category_key}")
async def category_stats(
    category_key: str,
    db: Session = Depends(get_db),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Statistics for a specific category."""
    return statistics.get_category_stats(db, category_key, _parse_date(from_date), _parse_date(to_date))


@router.get("/api/stats/tag/{tag_name}")
async def tag_stats(
    tag_name: str,
    db: Session = Depends(get_db),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Statistics for a specific tag."""
    return statistics.get_tag_stats(db, tag_name, _parse_date(from_date), _parse_date(to_date))


@router.get("/api/stats/overview")
async def overview_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Platform-wide statistics (admin only)."""
    return statistics.get_overview_stats(db, _parse_date(from_date), _parse_date(to_date))


@router.get("/api/stats/my")
async def my_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Statistics for the current user's content."""
    return statistics.get_my_stats(db, current_user.id, _parse_date(from_date), _parse_date(to_date))
