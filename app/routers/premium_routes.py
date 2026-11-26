import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .. import auth, crud, models, schemas, stripe_service
from ..achievements.service import AchievementDefinition, grant_achievement
from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["premium"])


def _require_user(current_user: Optional[models.User]) -> models.User:
    if not current_user:
        raise HTTPException(status_code=401, detail="Autentificare necesară.")
    return current_user


@router.get("/api/premium/planuri", response_model=list[schemas.PremiumPlan])
def list_plans():
    return stripe_service.list_premium_plans()


@router.get("/api/recomandari/eu")
def my_referrals(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    payload = crud.referral_summary(db, user)
    payload["referral_url"] = f"{str(request.base_url).rstrip('/')}{payload['referral_path']}"
    return payload


@router.post("/api/premium/plata", response_model=schemas.PremiumCheckoutResponse)
def create_checkout(
    body: schemas.PremiumCheckoutRequest = schemas.PremiumCheckoutRequest(),
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
    try:
        url = stripe_service.create_checkout_session(
            customer_id=customer_id, user_id=user.id, tier=body.tier
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
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


@router.get("/api/premium/cafea", response_model=schemas.CoffeeOffer)
def coffee_offer():
    return stripe_service.coffee_offer()


@router.post("/api/premium/cafea", response_model=schemas.PremiumCheckoutResponse)
def create_coffee_checkout(
    body: schemas.CoffeeCheckoutRequest = schemas.CoffeeCheckoutRequest(),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Anyone can buy coffees; logged-in buyers also get the supporter trophy."""
    customer_id = None
    try:
        if current_user:
            customer_id = stripe_service.create_or_get_customer(
                email=current_user.email,
                user_id=current_user.id,
                existing_customer_id=current_user.stripe_customer_id,
            )
            if not current_user.stripe_customer_id:
                crud.upsert_stripe_customer_id(db, user_id=current_user.id, customer_id=customer_id)
        url = stripe_service.create_coffee_checkout_session(
            quantity=body.quantity,
            user_id=current_user.id if current_user else None,
            customer_id=customer_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return schemas.PremiumCheckoutResponse(url=url)


@router.post("/api/stripe/notificare")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.verify_webhook(payload, sig_header)
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Semnătură invalidă")

    event_id = event["id"]
    event_type = event["type"]
    if crud.stripe_event_already_processed(db, event_id):
        return Response(status_code=200)

    # Handle first, record afterwards: if handling fails we return 500 and
    # Stripe retries the event instead of it being silently marked as done.
    # The handlers are idempotent, so a duplicate delivery is harmless.
    try:
        if event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            _apply_subscription_event(db, event)
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(db, event)
        elif event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            _handle_coffee_checkout(db, event)
        # Unhandled types -> 200 so Stripe does not retry.
    except Exception:
        db.rollback()
        logger.exception("Stripe webhook %s (%s) failed; Stripe will retry", event_id, event_type)
        raise HTTPException(status_code=500, detail="Eroare la procesarea evenimentului")

    try:
        crud.record_stripe_event(db, event_id=event_id, event_type=event_type)
    except Exception:
        # A concurrent delivery of the same event recorded it first.
        db.rollback()
    return Response(status_code=200)


# Statuses that pay for (or legitimately grant) the current period. Anything
# else (incomplete, past_due, unpaid, paused, ...) must not grant or extend
# premium; access then runs out at the last paid premium_until.
GRANTING_SUBSCRIPTION_STATUSES = {"active", "trialing"}


def _first_item_value(data: dict, key: str):
    """Billing period fields live on subscription items in API >= 2025-03-31."""
    for item in ((data.get("items") or {}).get("data") or []):
        value = item.get(key) if item else None
        if value is not None:
            return value
    return None


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
    status = data.get("status", "active")
    if status not in GRANTING_SUBSCRIPTION_STATUSES:
        logger.info(
            "Stripe subscription %s for user %s is %s; not granting premium",
            data.get("id"), user.id, status,
        )
        return
    period_end_ts = data.get("current_period_end")
    if period_end_ts is None:
        period_end_ts = _first_item_value(data, "current_period_end")
    if period_end_ts is None:
        return
    period_start_ts = data.get("current_period_start")
    if period_start_ts is None:
        period_start_ts = _first_item_value(data, "current_period_start")
    premium_until = datetime.fromtimestamp(int(period_end_ts), tz=timezone.utc).replace(tzinfo=None)
    premium_period_start = (
        datetime.fromtimestamp(int(period_start_ts), tz=timezone.utc).replace(tzinfo=None)
        if period_start_ts is not None
        else None
    )
    premium_tier = stripe_service.subscription_tier_from_event_object(data)
    crud.set_premium_from_subscription(
        db,
        user_id=user.id,
        subscription_id=data.get("id"),
        premium_until=premium_until,
        premium_tier=premium_tier,
        premium_period_start=premium_period_start,
    )


COFFEE_TROPHY = AchievementDefinition(
    key="coffee_supporter",
    title="Susținător cu cafea",
    description="A cumpărat o cafea pentru Călimara. Mulțumim!",
    award_type="special",
    event_type="stripe.coffee_purchased",
    awardee_user_id=lambda _db, event: event.actor_user_id,
    condition=lambda _db, _event: True,
    dedupe_key=lambda _db, _event: "coffee",
)


def _handle_coffee_checkout(db: Session, event) -> None:
    session = event["data"]["object"]
    if not stripe_service.is_paid_coffee_session(session):
        return
    raw_user_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("user_id")
    if not raw_user_id or not str(raw_user_id).isdigit():
        return  # anonymous buyer: Stripe emails the receipt, nothing to store
    user = db.get(models.User, int(raw_user_id))
    if not user:
        return
    quantity = stripe_service.coffee_quantity_from_session(session)
    # One trophy per supporter (dedupe key "coffee"); later coffees don't duplicate it.
    grant_achievement(
        db,
        COFFEE_TROPHY,
        user_id=user.id,
        dedupe_key="coffee",
        source_type="stripe_checkout",
        metadata={"checkout_session": session.get("id"), "quantity": quantity},
        notification_link="/premium",
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
            message="Ultima încercare de încasare a abonamentului a eșuat. Actualizează metoda de plată în portalul de facturare.",
            link="/premium",
        )
    )
    db.commit()
