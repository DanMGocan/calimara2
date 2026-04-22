import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .. import auth, crud, models, schemas, stripe_service
from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["premium"])


def _require_user(current_user: Optional[models.User]) -> models.User:
    if not current_user:
        raise HTTPException(status_code=401, detail="Autentificare necesară.")
    return current_user


@router.post("/api/premium/checkout", response_model=schemas.PremiumCheckoutResponse)
def create_checkout(
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    try:
        customer_id = stripe_service.create_or_get_customer(
            email=user.email,
            user_id=user.id,
            existing_customer_id=user.stripe_customer_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not user.stripe_customer_id:
        crud.upsert_stripe_customer_id(db, user_id=user.id, customer_id=customer_id)
    url = stripe_service.create_checkout_session(customer_id=customer_id, user_id=user.id)
    return schemas.PremiumCheckoutResponse(url=url)


@router.post("/api/premium/portal", response_model=schemas.PremiumPortalResponse)
def open_portal(
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Nu există un abonament asociat.")
    try:
        url = stripe_service.create_billing_portal_session(user.stripe_customer_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return schemas.PremiumPortalResponse(url=url)


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.verify_webhook(payload, sig_header)
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id = event["id"]
    event_type = event["type"]
    if not crud.record_stripe_event(db, event_id=event_id, event_type=event_type):
        return Response(status_code=200)

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        _apply_subscription_event(db, event)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(db, event)
    # Unhandled types -> 200 so Stripe does not retry.
    return Response(status_code=200)


def _apply_subscription_event(db: Session, event) -> None:
    data = event["data"]["object"]
    customer_id = data.get("customer")
    if not customer_id:
        return
    user = crud.get_user_by_stripe_customer_id(db, customer_id)
    if not user:
        logger.warning("Stripe webhook for unknown customer %s", customer_id)
        return
    event_type = event["type"]
    if event_type == "customer.subscription.deleted":
        crud.clear_stripe_subscription(db, user_id=user.id)
        return
    period_end_ts = data.get("current_period_end")
    if period_end_ts is None:
        return
    premium_until = datetime.fromtimestamp(int(period_end_ts), tz=timezone.utc).replace(tzinfo=None)
    crud.set_premium_from_subscription(
        db,
        user_id=user.id,
        subscription_id=data.get("id"),
        premium_until=premium_until,
    )


def _handle_payment_failed(db: Session, event) -> None:
    data = event["data"]["object"]
    customer_id = data.get("customer")
    if not customer_id:
        return
    user = crud.get_user_by_stripe_customer_id(db, customer_id)
    if not user:
        return
    db.add(
        models.Notification(
            user_id=user.id,
            type="payment_failed",
            title="Plata abonamentului a eșuat",
            message="Ultima încercare de încasare a abonamentului Premium a eșuat. Actualizează metoda de plată în portalul de facturare.",
            link="/premium",
        )
    )
    db.commit()
