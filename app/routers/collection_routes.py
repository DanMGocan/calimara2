import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, auth, crud
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["collections"])


# ----- helpers -----

def _author_payload(user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
    }


def _post_ref_payload(post: Optional[models.Post]) -> Optional[dict]:
    if not post:
        return None
    return {
        "id": post.id,
        "title": post.title,
        "slug": post.slug,
        "category": post.category,
        "super_likes_count": post.super_likes_count,
        "owner": _author_payload(post.owner),
    }


def _collection_summary_payload(
    collection: models.Collection,
    db: Session,
    include_pending: bool = False,
) -> dict:
    post_count = crud.count_collection_posts(db, collection.id, status="accepted")
    payload = {
        "id": collection.id,
        "owner_id": collection.owner_id,
        "title": collection.title,
        "slug": collection.slug,
        "description": collection.description,
        "owner": _author_payload(collection.owner),
        "post_count": post_count,
        "pending_count": 0,
        "created_at": collection.created_at,
        "updated_at": collection.updated_at,
    }
    if include_pending:
        payload["pending_count"] = crud.count_collection_posts(db, collection.id, status="pending")
    return payload


def _entry_payload(entry: models.CollectionPost) -> dict:
    return {
        "id": entry.id,
        "collection_id": entry.collection_id,
        "post_id": entry.post_id,
        "initiator_id": entry.initiator_id,
        "status": entry.status,
        "position": entry.position,
        "created_at": entry.created_at,
        "responded_at": entry.responded_at,
        "post": _post_ref_payload(entry.post),
    }


# ----- endpoints -----

@router.post("/api/collections/", status_code=status.HTTP_201_CREATED)
def create_collection_api(
    data: schemas.CollectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    collection = crud.create_collection(db, owner_id=current_user.id, data=data)
    db.refresh(collection)
    return _collection_summary_payload(collection, db, include_pending=True)


@router.get("/api/collections/{slug}")
def get_collection_by_slug_api(
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    collection = crud.get_collection_by_slug(db, slug)
    if not collection:
        raise HTTPException(status_code=404, detail="Colecția nu a fost găsită")
    is_owner = current_user is not None and current_user.id == collection.owner_id

    summary = _collection_summary_payload(collection, db, include_pending=is_owner)
    entries = crud.get_collection_entries(db, collection.id, status="accepted")
    posts_payload = [_entry_payload(e) for e in entries]
    return {**summary, "posts": posts_payload}


@router.get("/api/users/{username}/collections")
def list_user_collections_public(
    username: str,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    collections = crud.get_collections_by_owner(db, user.id)
    return {
        "collections": [_collection_summary_payload(c, db, include_pending=False) for c in collections]
    }


@router.put("/api/collections/{collection_id}")
def update_collection_api(
    collection_id: int,
    data: schemas.CollectionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    collection = crud.get_collection(db, collection_id)
    if not collection or collection.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Colecția nu a fost găsită")
    updated = crud.update_collection(db, collection_id, data)
    db.refresh(updated)
    return _collection_summary_payload(updated, db, include_pending=True)


@router.delete("/api/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection_api(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    collection = crud.get_collection(db, collection_id)
    if not collection or collection.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Colecția nu a fost găsită")
    crud.delete_collection(db, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/collections/{collection_id}/posts")
def add_post_to_collection_api(
    collection_id: int,
    body: schemas.CollectionAddPostRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    collection = db.query(models.Collection).options(
        joinedload(models.Collection.owner)
    ).filter(models.Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=404, detail="Colecția nu a fost găsită")
    post = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
        models.Post.id == body.post_id
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    if post.moderation_status != "approved":
        raise HTTPException(status_code=400, detail="Postarea nu este aprobată")

    entry, error = crud.add_post_to_collection(db, collection, post, current_user.id)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar proprietarul colecției sau autorul postării pot iniția această acțiune")
    if error == "already_in_collection":
        raise HTTPException(status_code=409, detail="Postarea face deja parte din colecție")
    if error == "already_pending":
        raise HTTPException(status_code=409, detail="Există deja o propunere în așteptare pentru această postare")
    if entry is None:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    return _entry_payload(entry)


@router.post("/api/collections/{collection_id}/posts/{post_id}/respond")
def respond_collection_entry_api(
    collection_id: int,
    post_id: int,
    body: schemas.CollectionRespondRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    entry = db.query(models.CollectionPost).options(
        joinedload(models.CollectionPost.collection).joinedload(models.Collection.owner),
        joinedload(models.CollectionPost.post).joinedload(models.Post.owner),
    ).filter(
        models.CollectionPost.collection_id == collection_id,
        models.CollectionPost.post_id == post_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Propunerea nu a fost găsită")

    updated, error = crud.respond_to_collection_entry(db, entry, current_user.id, body.action)
    if error == "bad_action":
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    if error == "not_pending":
        raise HTTPException(status_code=409, detail="Propunerea nu mai este în așteptare")
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Nu poți răspunde la această propunere")
    if error == "inconsistent_initiator":
        raise HTTPException(status_code=500, detail="Propunere inconsistentă")
    return _entry_payload(updated)


@router.delete("/api/collections/{collection_id}/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_collection_entry_api(
    collection_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    entry = db.query(models.CollectionPost).options(
        joinedload(models.CollectionPost.collection),
        joinedload(models.CollectionPost.post),
    ).filter(
        models.CollectionPost.collection_id == collection_id,
        models.CollectionPost.post_id == post_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Înregistrarea nu a fost găsită")
    ok, error = crud.remove_collection_entry(db, entry, current_user.id)
    if not ok:
        raise HTTPException(status_code=403, detail="Nu ai permisiunea să ștergi această înregistrare")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/user/collections")
def list_my_collections(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    collections = crud.get_collections_by_owner(db, current_user.id)
    return {
        "collections": [_collection_summary_payload(c, db, include_pending=True) for c in collections]
    }


@router.get("/api/user/collections/{collection_id}/manage")
def manage_my_collection(
    collection_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    collection = db.query(models.Collection).options(
        joinedload(models.Collection.owner)
    ).filter(models.Collection.id == collection_id).first()
    if not collection or collection.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Colecția nu a fost găsită")

    accepted = crud.get_collection_entries(db, collection.id, status="accepted")
    pending = crud.get_collection_entries(db, collection.id, status="pending", approved_posts_only=False)

    summary = _collection_summary_payload(collection, db, include_pending=True)
    return {
        **summary,
        "accepted": [_entry_payload(e) for e in accepted],
        "pending": [_entry_payload(e) for e in pending],
    }


@router.get("/api/user/collections/pending")
def my_pending_approvals(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    pairs = crud.get_pending_approvals_for_user(db, current_user.id)
    items = []
    for entry, direction in pairs:
        items.append({
            "entry": _entry_payload(entry),
            "direction": direction,
            "collection": _collection_summary_payload(entry.collection, db, include_pending=False),
            "post": _post_ref_payload(entry.post),
        })
    return {"items": items}


@router.get("/api/posts/{post_id}/collections")
def get_post_collections(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    collections = crud.get_collections_containing_post(db, post_id)
    return {
        "collections": [
            {
                "id": c.id,
                "title": c.title,
                "slug": c.slug,
                "owner": _author_payload(c.owner),
            }
            for c in collections
        ]
    }
