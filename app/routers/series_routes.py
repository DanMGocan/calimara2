from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import auth, crud, models, pdf_exporter, schemas
from ..categories import get_category_name
from ..database import get_db

router = APIRouter(tags=["series"])


def _author_payload(user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
    }


def _post_ref_payload(post: Optional[models.Post]) -> Optional[dict]:
    if not post:
        return None
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "category": post.category,
        "moderation_status": post.moderation_status,
        "super_likes_count": post.super_likes_count,
        "owner": _author_payload(post.owner),
    }


def _series_summary_payload(series: models.Series, db: Session, approved_only: bool = True) -> dict:
    return {
        "id": series.id,
        "owner_id": series.owner_id,
        "title": series.title,
        "slug": series.slug,
        "description": series.description,
        "owner": _author_payload(series.owner),
        "post_count": crud.count_series_posts(db, series.id, approved_only=approved_only),
        "created_at": series.created_at,
        "updated_at": series.updated_at,
    }


def _entry_payload(entry: models.SeriesPost) -> dict:
    return {
        "id": entry.id,
        "series_id": entry.series_id,
        "post_id": entry.post_id,
        "position": entry.position,
        "created_at": entry.created_at,
        "post": _post_ref_payload(entry.post),
    }


def _get_owned_series_or_404(db: Session, series_id: int, user_id: int) -> models.Series:
    series = crud.get_series(db, series_id)
    if not series or series.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Seria nu a fost găsită")
    return series


@router.post("/api/serii/", status_code=status.HTTP_201_CREATED)
def create_series_api(
    data: schemas.SeriesCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    series = crud.create_series(db, owner_id=current_user.id, data=data)
    db.refresh(series)
    return _series_summary_payload(series, db, approved_only=False)


@router.get("/api/serii/aleatoriu")
def random_series_api(db: Session = Depends(get_db)):
    series = crud.get_random_series(db)
    if not series:
        raise HTTPException(status_code=404, detail="Nicio serie disponibilă")
    return _series_summary_payload(series, db)


@router.get("/api/serii/{slug}")
def get_series_by_slug_api(
    slug: str,
    db: Session = Depends(get_db),
):
    series = crud.get_series_by_slug(db, slug)
    if not series:
        raise HTTPException(status_code=404, detail="Seria nu a fost găsită")

    summary = _series_summary_payload(series, db)
    entries = crud.get_series_entries(db, series.id, approved_posts_only=True)
    return {**summary, "posts": [_entry_payload(entry) for entry in entries]}


@router.get("/api/serii/{slug}/pdf")
def series_pdf_download(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    series = crud.get_series_by_slug(db, slug)
    if not series:
        raise HTTPException(status_code=404, detail="Seria nu a fost găsită")

    entries = crud.get_series_entries(db, series.id, approved_posts_only=True)
    page_url = pdf_exporter.series_page_url(request, series.slug)
    pdf_bytes = pdf_exporter.render_series_pdf(
        series=series,
        owner=series.owner,
        entries=entries,
        page_url=page_url,
        category_label_for_post=lambda category: get_category_name(category) if category else "",
    )
    return Response(
        content=pdf_bytes,
        media_type=pdf_exporter.PDF_MEDIA_TYPE,
        headers=pdf_exporter.pdf_response_headers(f"serie-{series.slug}"),
    )


@router.get("/api/utilizatori/{username}/serii")
def list_user_series_public(
    username: str,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    series_items = crud.get_series_by_owner(db, user.id)
    return {
        "series": [_series_summary_payload(series, db) for series in series_items]
    }


@router.get("/api/utilizator/serii")
def list_my_series(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    series_items = crud.get_series_by_owner(db, current_user.id)
    return {
        "series": [
            _series_summary_payload(series, db, approved_only=False)
            for series in series_items
        ]
    }


@router.get("/api/utilizator/serii/{series_id}/gestioneaza")
def manage_my_series(
    series_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    series = _get_owned_series_or_404(db, series_id, current_user.id)
    entries = crud.get_series_entries(db, series.id, approved_posts_only=False)
    return {
        **_series_summary_payload(series, db, approved_only=False),
        "posts": [_entry_payload(entry) for entry in entries],
    }


@router.put("/api/serii/{series_id}")
def update_series_api(
    series_id: int,
    data: schemas.SeriesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    _get_owned_series_or_404(db, series_id, current_user.id)
    updated = crud.update_series(db, series_id, data)
    db.refresh(updated)
    return _series_summary_payload(updated, db, approved_only=False)


@router.delete("/api/serii/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_series_api(
    series_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    _get_owned_series_or_404(db, series_id, current_user.id)
    crud.delete_series(db, series_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/serii/{series_id}/postari")
def add_post_to_series_api(
    series_id: int,
    body: schemas.SeriesAddPostRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    series = _get_owned_series_or_404(db, series_id, current_user.id)
    post = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
        models.Post.id == body.post_id
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")

    entry, error = crud.add_post_to_series(db, series, post)
    if error == "wrong_author":
        raise HTTPException(status_code=403, detail="Poți adăuga doar postările tale într-o serie")
    if error == "already_in_series":
        raise HTTPException(status_code=409, detail="Postarea face deja parte din această serie")
    if error == "post_in_other_series":
        raise HTTPException(status_code=409, detail="Postarea face deja parte din altă serie")
    if entry is None:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    db.refresh(entry)
    return _entry_payload(entry)


@router.put("/api/serii/{series_id}/postari/ordine")
def reorder_series_posts_api(
    series_id: int,
    body: schemas.SeriesReorderRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    series = _get_owned_series_or_404(db, series_id, current_user.id)
    entries, error = crud.reorder_series_posts(db, series, body.post_ids)
    if error == "duplicate_posts":
        raise HTTPException(status_code=400, detail="Lista conține postări duplicate")
    if error == "mismatched_posts":
        raise HTTPException(status_code=400, detail="Lista trebuie să conțină exact postările seriei")
    return {
        **_series_summary_payload(series, db, approved_only=False),
        "posts": [_entry_payload(entry) for entry in (entries or [])],
    }


@router.delete("/api/serii/{series_id}/postari/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_series_entry_api(
    series_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    series = _get_owned_series_or_404(db, series_id, current_user.id)
    if not crud.remove_series_entry(db, series, post_id):
        raise HTTPException(status_code=404, detail="Postarea nu este în această serie")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/postari/{post_id}/serie")
def get_post_series(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    include_unapproved = bool(
        current_user
        and (
            current_user.id == post.user_id
            or current_user.is_admin
            or current_user.is_moderator
        )
    )
    if post.moderation_status != "approved" and not include_unapproved:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    context = crud.get_series_context_for_post(db, post, include_unapproved=include_unapproved)
    return context or {"series": None}
