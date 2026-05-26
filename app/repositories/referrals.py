from ._shared import *

import secrets
import string


REFERRAL_GOLD_THRESHOLD = 600
REFERRAL_REWARD_DAYS = 7
REFERRAL_REWARD_TIER = "trubadur"
_REFERRAL_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_TIER_RANK = {"free": 0, "trubadur": 1, "cronicar": 2, "rapsod": 3}


def normalize_referral_code(code: Optional[str]) -> str:
    return "".join(ch for ch in str(code or "").upper() if ch in string.ascii_uppercase + string.digits)[:24]


def generate_referral_code(length: int = 10) -> str:
    return "".join(secrets.choice(_REFERRAL_CODE_ALPHABET) for _ in range(length))


def ensure_referral_code(db: Session, user: models.User) -> str:
    if user.referral_code:
        return user.referral_code
    for _attempt in range(12):
        code = generate_referral_code()
        user.referral_code = code
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.query(models.User).filter(models.User.id == user.id).first()
            if not user:
                raise
            if user.referral_code:
                return user.referral_code
            continue
        db.refresh(user)
        return code
    raise RuntimeError("Nu am putut genera un cod de recomandare unic.")


def get_referrer_by_referral_code(db: Session, code: Optional[str]) -> Optional[models.User]:
    normalized = normalize_referral_code(code)
    if not normalized:
        return None
    return (
        db.query(models.User)
        .filter(
            func.upper(models.User.referral_code) == normalized,
            models.User.is_suspended == False,
        )
        .first()
    )


def referral_code_allows_access(db: Session, code: Optional[str]) -> bool:
    return get_referrer_by_referral_code(db, code) is not None


def apply_referral_to_user(db: Session, user: models.User, code: Optional[str]) -> Optional[models.User]:
    if not user or user.referred_by_user_id:
        return None
    referrer = get_referrer_by_referral_code(db, code)
    if not referrer or referrer.id == user.id:
        return None
    user.referred_by_user_id = referrer.id
    db.add(user)
    db.commit()
    db.refresh(user)
    return referrer


def referred_user_earned_gologani(db: Session, user_id: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(models.GologaniTransaction.amount), 0))
        .filter(
            models.GologaniTransaction.user_id == user_id,
            models.GologaniTransaction.amount > 0,
        )
        .scalar()
    )
    return int(total or 0)


def _premium_tier_after_referral(referrer: models.User) -> str:
    current_tier = referrer.premium_tier or "free"
    if referrer.is_premium and _TIER_RANK.get(current_tier, 0) >= _TIER_RANK[REFERRAL_REWARD_TIER]:
        return current_tier
    return REFERRAL_REWARD_TIER


def apply_referral_reward_for_earning(db: Session, referred_user_id: int) -> Optional[dict]:
    referred = (
        db.query(models.User)
        .filter(models.User.id == referred_user_id)
        .with_for_update()
        .first()
    )
    if not referred or not referred.referred_by_user_id or referred.referral_rewarded_at:
        return None

    earned = referred_user_earned_gologani(db, referred.id)
    if earned < REFERRAL_GOLD_THRESHOLD:
        return None

    referrer = db.query(models.User).filter(models.User.id == referred.referred_by_user_id).first()
    if not referrer or referrer.id == referred.id or referrer.is_suspended:
        return None

    now = utcnow_naive()
    active_until = referrer.premium_until if referrer.premium_until and referrer.premium_until > now else now
    premium_until = active_until + timedelta(days=REFERRAL_REWARD_DAYS)

    referrer.premium_tier = _premium_tier_after_referral(referrer)
    if not referrer.premium_period_start or not referrer.is_premium:
        referrer.premium_period_start = now
    referrer.premium_until = premium_until

    referred.referral_rewarded_at = now
    referred.referral_reward_premium_until = premium_until
    referred.referral_reward_qualified_gologani = earned

    db.add(referrer)
    db.add(referred)
    db.add(
        models.Notification(
            user_id=referrer.id,
            type="referral_reward",
            title="Recompensă de recomandare",
            message=(
                f"{referred.username} a câștigat {earned} Gologani. "
                f"Ai primit {REFERRAL_REWARD_DAYS} zile de Trubadur."
            ),
            link="/invitatii",
            extra_data={
                "referred_user_id": referred.id,
                "referred_username": referred.username,
                "earned_gologani": earned,
                "premium_tier": REFERRAL_REWARD_TIER,
                "reward_days": REFERRAL_REWARD_DAYS,
            },
        )
    )
    db.commit()
    db.refresh(referrer)
    db.refresh(referred)
    return {
        "referrer_id": referrer.id,
        "referred_user_id": referred.id,
        "earned_gologani": earned,
        "premium_until": premium_until,
    }


def _positive_gologani_by_user(db: Session, user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    rows = (
        db.query(
            models.GologaniTransaction.user_id,
            func.coalesce(func.sum(models.GologaniTransaction.amount), 0),
        )
        .filter(
            models.GologaniTransaction.user_id.in_(user_ids),
            models.GologaniTransaction.amount > 0,
        )
        .group_by(models.GologaniTransaction.user_id)
        .all()
    )
    return {int(user_id): int(total or 0) for user_id, total in rows}


def _approved_post_count_by_user(db: Session, user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    rows = (
        db.query(models.Post.user_id, func.count(models.Post.id))
        .filter(
            models.Post.user_id.in_(user_ids),
            models.Post.moderation_status == "approved",
        )
        .group_by(models.Post.user_id)
        .all()
    )
    return {int(user_id): int(total or 0) for user_id, total in rows}


def referral_summary(db: Session, user: models.User, *, limit: Optional[int] = None) -> dict:
    code = ensure_referral_code(db, user)
    query = (
        db.query(models.User)
        .filter(models.User.referred_by_user_id == user.id)
        .order_by(models.User.created_at.desc(), models.User.id.desc())
    )
    if limit is not None:
        query = query.limit(max(1, min(int(limit or 50), 500)))
    referred_users = query.all()
    referred_user_ids = [referred.id for referred in referred_users]
    earned_by_user = _positive_gologani_by_user(db, referred_user_ids)
    post_count_by_user = _approved_post_count_by_user(db, referred_user_ids)
    referrals = []
    rewarded_count = 0
    for referred in referred_users:
        earned = earned_by_user.get(referred.id, 0)
        rewarded = bool(referred.referral_rewarded_at)
        if rewarded:
            rewarded_count += 1
        remaining = max(0, REFERRAL_GOLD_THRESHOLD - earned)
        progress_percent = 100 if REFERRAL_GOLD_THRESHOLD <= 0 else min(100, round((earned / REFERRAL_GOLD_THRESHOLD) * 100))
        referrals.append(
            {
                "user_id": referred.id,
                "username": referred.username,
                "created_at": referred.created_at.isoformat() if referred.created_at else None,
                "post_count": post_count_by_user.get(referred.id, 0),
                "gologani_balance": int(referred.gologani_balance or 0),
                "earned_gologani": earned,
                "remaining_gologani": remaining,
                "progress_percent": progress_percent,
                "rewarded_at": referred.referral_rewarded_at.isoformat() if referred.referral_rewarded_at else None,
                "reward_premium_until": referred.referral_reward_premium_until.isoformat() if referred.referral_reward_premium_until else None,
            }
        )
    return {
        "referral_code": code,
        "referral_path": f"/?ref={code}&auth_modal=1",
        "threshold_gologani": REFERRAL_GOLD_THRESHOLD,
        "reward_days": REFERRAL_REWARD_DAYS,
        "reward_tier": REFERRAL_REWARD_TIER,
        "referred_count": len(referrals),
        "pending_count": len(referrals) - rewarded_count,
        "rewarded_count": rewarded_count,
        "referrals": referrals,
    }
