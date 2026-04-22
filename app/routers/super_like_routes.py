from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import auth, crud, models, schemas
from ..database import get_db
from ..week_util import end_of_iso_week_utc

router = APIRouter(tags=["super-apreciez"])


def _require_user(current_user: Optional[models.User]) -> models.User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trebuie să fii autentificat pentru a super-aprecia.",
        )
    return current_user


@router.post(
    "/api/posts/{post_id}/super-likes",
    response_model=schemas.SuperLike,
    status_code=status.HTTP_201_CREATED,
)
def add_super_like(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    try:
        return crud.create_super_like(db, user=user, post_id=post_id)
    except crud.SuperLikePostNotFoundError:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită.")
    except crud.SuperLikeSelfError:
        raise HTTPException(
            status_code=403,
            detail="Nu îți poți super-aprecia propria postare.",
        )
    except crud.SuperLikeDuplicateError:
        raise HTTPException(
            status_code=409,
            detail="Ai super-apreciat deja această postare.",
        )
    except crud.SuperLikeQuotaError:
        raise HTTPException(
            status_code=403,
            detail="Ai epuizat super-aprecierile pentru această săptămână.",
            headers={"X-Error-Code": "quota_exhausted"},
        )


@router.delete(
    "/api/posts/{post_id}/super-likes",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_super_like(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    removed = crud.delete_super_like(db, user=user, post_id=post_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Nicio super-apreciere de retras.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/users/me/super-likes/quota", response_model=schemas.SuperLikeQuota)
def get_quota(
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    quota = crud.weekly_quota_for_user(user)
    used = crud.get_user_weekly_super_like_count(db, user.id)
    return schemas.SuperLikeQuota(
        weekly_quota=quota,
        used_this_week=used,
        remaining=max(0, quota - used),
        week_resets_at=end_of_iso_week_utc(),
        is_premium=user.is_premium,
    )
