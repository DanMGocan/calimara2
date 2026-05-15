import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import auth, diacritics, models, schemas

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["writing"])


@router.post("/api/scriere/diacritice", response_model=schemas.DiacriticsResponse)
@limiter.limit("20/minute")
def add_diacritics_api(
    request: Request,
    body: schemas.DiacriticsRequest,
    current_user: models.User = Depends(auth.require_premium_user),
):
    try:
        if body.kind == "theatre_play":
            return diacritics.add_theatre_play_diacritics(
                title=body.title,
                description=body.description,
                characters=[item.model_dump() for item in body.characters],
            )
        return diacritics.add_diacritics(
            title=body.title,
            content=body.content or "",
            kind=body.kind,
        )
    except RuntimeError as exc:
        logger.warning("AI diacritics failed for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=503, detail=str(exc))
