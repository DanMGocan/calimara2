from ._shared import *

def upsert_stripe_customer_id(db: Session, user_id: int, customer_id: str) -> None:
    db.query(models.User).filter(models.User.id == user_id).update(
        {"stripe_customer_id": customer_id}
    )
    db.commit()

def get_user_by_stripe_customer_id(db: Session, customer_id: str) -> Optional[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.stripe_customer_id == customer_id)
        .first()
    )

def set_premium_from_subscription(
    db: Session,
    user_id: int,
    subscription_id: str,
    premium_until: datetime,
    premium_tier: str = "trubadur",
    premium_period_start: Optional[datetime] = None,
) -> None:
    fields = {
        "stripe_subscription_id": subscription_id,
        "premium_tier": premium_tier,
        "premium_until": premium_until,
    }
    if premium_period_start is not None:
        fields["premium_period_start"] = premium_period_start
    db.query(models.User).filter(models.User.id == user_id).update(fields)
    db.commit()

def clear_stripe_subscription(db: Session, user_id: int) -> None:
    db.query(models.User).filter(models.User.id == user_id).update(
        {"stripe_subscription_id": None}
    )
    db.commit()

def stripe_event_already_processed(db: Session, event_id: str) -> bool:
    return (
        db.query(models.StripeEvent.id).filter(models.StripeEvent.id == event_id).first()
        is not None
    )

def record_stripe_event(db: Session, event_id: str, event_type: str) -> bool:
    """Return True if this is a new event; False if already processed."""
    existing = db.query(models.StripeEvent).filter(models.StripeEvent.id == event_id).first()
    if existing:
        return False
    db.add(models.StripeEvent(id=event_id, type=event_type))
    db.commit()
    return True


# ===================================
# CLUB CRUD FUNCTIONS
# ===================================
