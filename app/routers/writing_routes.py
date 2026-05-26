import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from .. import auth, crud, diacritics, email_service, models, schemas, text_formatting
from ..database import get_db
from ..mistral_context import MistralContextWindowExceeded

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["writing"])


def _quota_with_diacritics_status(payload: dict) -> dict:
    service_status = diacritics.diacritics_service_status()
    payload.update(service_status)
    payload["can_request"] = bool(payload.get("can_request") and service_status["service_available"])
    return payload


def _queue_ai_service_alert(
    db: Session,
    *,
    request: Request,
    service: str,
    summary: str,
    error_message: str,
    user_id: int | None = None,
    context: dict | None = None,
) -> None:
    alert_context = {
        "path": getattr(getattr(request, "url", None), "path", None),
        "user_id": user_id,
        **(context or {}),
    }
    email_service.queue_system_alert_email(
        db,
        service=service,
        summary=summary,
        error_message=error_message,
        context=alert_context,
    )


@router.get("/api/scriere/diacritice/cota", response_model=schemas.DiacriticsQuota)
def get_diacritics_quota(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return _quota_with_diacritics_status(crud.diacritics_quota_payload(db, current_user))


@router.post("/api/scriere/diacritice", response_model=schemas.DiacriticsResponse)
@limiter.limit("20/minute")
def add_diacritics_api(
    request: Request,
    body: schemas.DiacriticsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    usage_event = None
    try:
        if body.kind == "theatre_play":
            diacritics.validate_theatre_play_diacritics_context(
                title=body.title,
                description=body.description,
                characters=[item.model_dump() for item in body.characters],
            )
        else:
            diacritics.validate_diacritics_request_context(
                title=body.title,
                content=body.content or "",
                kind=body.kind,
            )
        requested_characters = crud.diacritics_character_count_for_request(body)
        diacritics.ensure_diacritics_service_available()
        usage_event, quota = crud.reserve_diacritics_usage(
            db,
            user=current_user,
            kind=body.kind,
            character_count=requested_characters,
        )
        if body.kind == "theatre_play":
            result = diacritics.add_theatre_play_diacritics(
                title=body.title,
                description=body.description,
                characters=[item.model_dump() for item in body.characters],
            )
        else:
            result = diacritics.add_diacritics(
                title=body.title,
                content=body.content or "",
                kind=body.kind,
            )
        crud.mark_diacritics_usage_succeeded(db, usage_event)
        result["quota"] = _quota_with_diacritics_status(quota)
        return result
    except crud.DiacriticsQuotaExceeded as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Limita lunară de caractere pentru Diacritice ar fi depășită. "
                f"Disponibil: {exc.remaining}, cerut: {exc.requested}."
            ),
        )
    except crud.DiacriticsQuotaUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except MistralContextWindowExceeded as exc:
        raise HTTPException(
            status_code=413,
            detail=(
                "Textul este prea lung pentru modelul AI configurat. "
                f"Estimare: {exc.estimated_input_tokens} tokeni intrare, "
                f"rezervă răspuns: {exc.max_output_tokens}, limită: {exc.context_limit}."
            ),
        )
    except RuntimeError as exc:
        if usage_event is not None:
            crud.mark_diacritics_usage_failed(db, usage_event, str(exc))
        logger.warning("AI diacritics failed for user %s: %s", current_user.id, exc)
        _queue_ai_service_alert(
            db,
            request=request,
            service="Diacritice",
            summary="Conversia automată la diacritice a eșuat.",
            error_message=str(exc),
            user_id=current_user.id,
            context={"kind": body.kind},
        )
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/api/scriere/formatare-ai", response_model=schemas.PostFormatResponse)
@limiter.limit("10/minute")
def format_post_with_ai_api(
    request: Request,
    body: schemas.PostFormatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        text_formatting.validate_post_formatting_context(
            content=body.content,
            category=body.category,
        )
        return text_formatting.format_post_content(
            content=body.content,
            category=body.category,
        )
    except MistralContextWindowExceeded as exc:
        raise HTTPException(
            status_code=413,
            detail=(
                "Textul este prea lung pentru modelul AI configurat. "
                f"Estimare: {exc.estimated_input_tokens} tokeni intrare, "
                f"rezervă răspuns: {exc.max_output_tokens}, limită: {exc.context_limit}."
            ),
        )
    except RuntimeError as exc:
        logger.warning("AI post formatting failed for user %s: %s", current_user.id, exc)
        _queue_ai_service_alert(
            db,
            request=request,
            service="AI formatting",
            summary="Curățarea formatării cu AI a eșuat.",
            error_message=str(exc),
            user_id=current_user.id,
            context={"category": body.category},
        )
        raise HTTPException(status_code=503, detail=str(exc))
