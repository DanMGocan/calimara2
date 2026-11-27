from ._shared import *
from .posts import get_post
from .referrals import apply_referral_reward_for_earning
from sqlalchemy.exc import SQLAlchemyError

DEFAULT_GOLOGANI_REWARD_SETTINGS = [
    {
        "event_type": "post_approved",
        "label": "Text aprobat",
        "description": "Autorul primește recompensa când o postare devine aprobată.",
        "amount": 25,
        "sort_order": 10,
    },
    {
        "event_type": "comment_approved",
        "label": "Comentariu aprobat",
        "description": "Autorul primește recompensa când un comentariu devine aprobat.",
        "amount": 8,
        "sort_order": 20,
    },
    {
        "event_type": "like_given",
        "label": "Apreciere oferită",
        "description": "Cititorul primește recompensa când apreciază textul altcuiva.",
        "amount": 1,
        "sort_order": 30,
    },
    {
        "event_type": "like_received",
        "label": "Apreciere primită",
        "description": "Autorul primește recompensa când textul lui primește o apreciere.",
        "amount": 2,
        "sort_order": 40,
    },
    {
        "event_type": "super_like_given",
        "label": "Super-apreciere oferită",
        "description": "Cititorul primește recompensa când oferă Super-apreciez.",
        "amount": 5,
        "sort_order": 50,
    },
    {
        "event_type": "super_like_received",
        "label": "Super-apreciere primită",
        "description": "Autorul primește recompensa când textul lui primește Super-apreciez.",
        "amount": 15,
        "sort_order": 60,
    },
    {
        "event_type": "forum_thread_approved",
        "label": "Discuție forum aprobată",
        "description": "Autorul primește recompensa când o discuție de forum devine aprobată.",
        "amount": 15,
        "sort_order": 70,
    },
    {
        "event_type": "forum_reply_approved",
        "label": "Răspuns forum aprobat",
        "description": "Autorul primește recompensa când un răspuns de forum devine aprobat.",
        "amount": 8,
        "sort_order": 80,
    },
]

GOLOGANI_REWARDS = {item["event_type"]: item["amount"] for item in DEFAULT_GOLOGANI_REWARD_SETTINGS}
GOLOGANI_REWARD_DEFAULTS = {item["event_type"]: item for item in DEFAULT_GOLOGANI_REWARD_SETTINGS}

DEFAULT_SHOP_ITEMS = [
    {
        "slug": "manuscrisul-scrisorii-a-iii-a",
        "name": "Manuscrisul Scrisorii a III-a",
        "description": "Un manuscris de vitrină pentru profilul tău.",
        "price": 120,
        "slot": "profile_badge",
        "sort_order": 10,
    },
    {
        "slug": "costumul-de-nunta-al-lui-nichita-stanescu",
        "name": "Costumul de nuntă al lui Nichita Stănescu",
        "description": "Un costum literar pentru apariții de cenaclu.",
        "price": 250,
        "slot": "costume",
        "sort_order": 20,
    },
    {
        "slug": "sicriul-de-plumb-al-lui-bacovia",
        "name": "Sicriul de plumb al lui Bacovia",
        "description": "„Dormeau adânc sicriele de plumb...” Un artefact simbolist din universul lui George Bacovia.",
        "price": 220,
        "slot": "profile_badge",
        "asset_url": "/assets/items/profile_badge/sicriul-de-plumb-al-lui-bacovia.png",
        "sort_order": 40,
    },
    {
        "slug": "dintele-de-balena-al-lui-marin-sorescu",
        "name": "Dintele de balenă al lui Marin Sorescu",
        "description": "O relicvă gravată din burta chitului lui Iona, în spiritul lui Marin Sorescu.",
        "price": 190,
        "slot": "profile_badge",
        "asset_url": "/assets/items/profile_badge/dintele-de-balena-al-lui-marin-sorescu.png",
        "sort_order": 50,
    },
    {
        "slug": "portretul-veronicai-al-lui-mihai-eminescu",
        "name": "Portretul Veronicăi al lui Mihai Eminescu",
        "description": "Un medalion oval de epocă păstrând chipul Veronicăi Micle, muza lui Mihai Eminescu.",
        "price": 240,
        "slot": "profile_badge",
        "asset_url": "/assets/items/profile_badge/portretul-veronicai-al-lui-mihai-eminescu.png",
        "sort_order": 60,
    },
]

class EconomyError(Exception):
    """Base class for Gologani/shop errors."""

class InsufficientGologaniError(EconomyError):
    pass

class ShopItemNotFoundError(EconomyError):
    pass

class ShopItemInactiveError(EconomyError):
    pass

class ShopItemDuplicateSlugError(EconomyError):
    pass

class GologaniRewardSettingNotFoundError(EconomyError):
    pass

class InventoryDuplicateError(EconomyError):
    pass

class InventoryItemNotFoundError(EconomyError):
    pass

def _normalize_balance(user: models.User) -> int:
    return int(user.gologani_balance or 0)

def seed_default_gologani_reward_settings(db: Session) -> None:
    changed = False
    for setting_data in DEFAULT_GOLOGANI_REWARD_SETTINGS:
        existing = (
            db.query(models.GologaniRewardSetting)
            .filter(models.GologaniRewardSetting.event_type == setting_data["event_type"])
            .first()
        )
        if existing:
            for key in ("label", "description", "sort_order"):
                if getattr(existing, key) != setting_data[key]:
                    setattr(existing, key, setting_data[key])
                    changed = True
            continue
        db.add(models.GologaniRewardSetting(**setting_data))
        changed = True
    if changed:
        db.commit()

def list_gologani_reward_settings(db: Session) -> List[models.GologaniRewardSetting]:
    seed_default_gologani_reward_settings(db)
    return (
        db.query(models.GologaniRewardSetting)
        .order_by(models.GologaniRewardSetting.sort_order.asc(), models.GologaniRewardSetting.event_type.asc())
        .all()
    )

def get_gologani_reward_setting(db: Session, event_type: str) -> Optional[models.GologaniRewardSetting]:
    return (
        db.query(models.GologaniRewardSetting)
        .filter(models.GologaniRewardSetting.event_type == event_type)
        .first()
    )

def update_gologani_reward_setting(
    db: Session,
    event_type: str,
    data: schemas.GologaniRewardSettingUpdate,
    *,
    updated_by: Optional[int] = None,
) -> models.GologaniRewardSetting:
    defaults = GOLOGANI_REWARD_DEFAULTS.get(event_type)
    setting = get_gologani_reward_setting(db, event_type)
    if not setting and defaults:
        setting = models.GologaniRewardSetting(**defaults)
        db.add(setting)
        db.flush()
    if not setting:
        raise GologaniRewardSettingNotFoundError()
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(setting, key, value)
    setting.updated_by = updated_by
    db.commit()
    db.refresh(setting)
    return setting

def get_gologani_reward_amount(db: Session, event_type: str) -> int:
    default_amount = int(GOLOGANI_REWARDS.get(event_type, 0))
    try:
        setting = get_gologani_reward_setting(db, event_type)
    except SQLAlchemyError:
        db.rollback()
        return default_amount
    if not setting:
        return default_amount
    if not setting.is_active:
        return 0
    return max(0, int(setting.amount or 0))

def grant_gologani(
    db: Session,
    *,
    user_id: Optional[int],
    amount: int,
    event_type: str,
    idempotency_key: str,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    description: Optional[str] = None,
    extra_data: Optional[dict] = None,
) -> Optional[models.GologaniTransaction]:
    if not user_id or amount == 0:
        return None
    existing = (
        db.query(models.GologaniTransaction)
        .filter(models.GologaniTransaction.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        if existing.amount > 0:
            apply_referral_reward_for_earning(db, existing.user_id)
        return existing
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    user.gologani_balance = _normalize_balance(user) + amount
    transaction = models.GologaniTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=user.gologani_balance,
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        description=description,
        extra_data=extra_data or {},
    )
    db.add(transaction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return (
            db.query(models.GologaniTransaction)
            .filter(models.GologaniTransaction.idempotency_key == idempotency_key)
            .first()
        )
    db.refresh(transaction)
    if transaction.amount > 0:
        apply_referral_reward_for_earning(db, user.id)
    return transaction

def award_content_approved(db: Session, content_type: str, content) -> Optional[models.GologaniTransaction]:
    reward_key = f"{content_type}_approved"
    amount = get_gologani_reward_amount(db, reward_key)
    if not amount:
        return None
    if getattr(content, "moderation_status", None) != "approved":
        return None
    if content_type == "post":
        user_id = getattr(content, "user_id", None)
        label = "Postare aprobată"
    elif content_type == "comment":
        if getattr(content, "is_robot", False):
            return None
        user_id = getattr(content, "user_id", None)
        label = "Comentariu aprobat"
    elif content_type == "forum_thread":
        user_id = getattr(content, "author_id", None)
        label = "Discuție de forum aprobată"
    elif content_type == "forum_reply":
        user_id = getattr(content, "author_id", None)
        label = "Răspuns de forum aprobat"
    else:
        return None
    source_id = getattr(content, "id", None)
    return grant_gologani(
        db,
        user_id=user_id,
        amount=amount,
        event_type=reward_key,
        source_type=content_type,
        source_id=source_id,
        idempotency_key=f"reward:{reward_key}:{source_id}",
        description=label,
    )

def award_like_created(db: Session, like: models.Like) -> None:
    if not like.user_id:
        return
    post = like.post or get_post(db, like.post_id)
    if not post or post.moderation_status != "approved" or post.user_id == like.user_id:
        return
    grant_gologani(
        db,
        user_id=like.user_id,
        amount=get_gologani_reward_amount(db, "like_given"),
        event_type="like_given",
        source_type="like",
        source_id=like.id,
        idempotency_key=f"reward:like_given:{like.user_id}:{like.post_id}",
        description="Apreciere oferită",
    )
    grant_gologani(
        db,
        user_id=post.user_id,
        amount=get_gologani_reward_amount(db, "like_received"),
        event_type="like_received",
        source_type="like",
        source_id=like.id,
        idempotency_key=f"reward:like_received:{like.user_id}:{like.post_id}",
        description="Apreciere primită",
    )

def award_super_like_created(db: Session, super_like: models.SuperLike) -> None:
    post = super_like.post or get_post(db, super_like.post_id)
    if not post or post.moderation_status != "approved" or post.user_id == super_like.user_id:
        return
    grant_gologani(
        db,
        user_id=super_like.user_id,
        amount=get_gologani_reward_amount(db, "super_like_given"),
        event_type="super_like_given",
        source_type="super_like",
        source_id=super_like.id,
        idempotency_key=f"reward:super_like_given:{super_like.user_id}:{super_like.post_id}",
        description="Super-apreciere oferită",
    )
    grant_gologani(
        db,
        user_id=post.user_id,
        amount=get_gologani_reward_amount(db, "super_like_received"),
        event_type="super_like_received",
        source_type="super_like",
        source_id=super_like.id,
        idempotency_key=f"reward:super_like_received:{super_like.user_id}:{super_like.post_id}",
        description="Super-apreciere primită",
    )

def seed_default_shop_items(db: Session) -> None:
    changed = False
    for item_data in DEFAULT_SHOP_ITEMS:
        exists = db.query(models.ShopItem.id).filter(models.ShopItem.slug == item_data["slug"]).first()
        if not exists:
            db.add(models.ShopItem(**item_data))
            changed = True
    if changed:
        db.commit()

def list_shop_items(db: Session, include_inactive: bool = False) -> List[models.ShopItem]:
    query = db.query(models.ShopItem)
    if not include_inactive:
        query = query.filter(models.ShopItem.is_active == True)
    return query.order_by(models.ShopItem.sort_order.asc(), models.ShopItem.id.asc()).all()

def get_shop_item(db: Session, item_id: int) -> Optional[models.ShopItem]:
    return db.query(models.ShopItem).filter(models.ShopItem.id == item_id).first()

def create_shop_item(db: Session, data: schemas.ShopItemCreate) -> models.ShopItem:
    item = models.ShopItem(**data.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ShopItemDuplicateSlugError()
    db.refresh(item)
    return item

def update_shop_item(db: Session, item_id: int, data: schemas.ShopItemUpdate) -> Optional[models.ShopItem]:
    item = get_shop_item(db, item_id)
    if not item:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ShopItemDuplicateSlugError()
    db.refresh(item)
    return item

def get_inventory_for_user(db: Session, user_id: int) -> List[models.UserInventoryItem]:
    return (
        db.query(models.UserInventoryItem)
        .options(joinedload(models.UserInventoryItem.item))
        .filter(models.UserInventoryItem.user_id == user_id)
        .order_by(models.UserInventoryItem.purchased_at.desc(), models.UserInventoryItem.id.desc())
        .all()
    )

def get_equipped_items_for_user(db: Session, user_id: int) -> List[models.UserEquippedItem]:
    return (
        db.query(models.UserEquippedItem)
        .options(joinedload(models.UserEquippedItem.item))
        .filter(models.UserEquippedItem.user_id == user_id)
        .order_by(models.UserEquippedItem.slot.asc())
        .all()
    )

def purchase_shop_item(db: Session, user: models.User, item_id: int) -> models.UserInventoryItem:
    item = get_shop_item(db, item_id)
    if not item:
        raise ShopItemNotFoundError()
    if not item.is_active:
        raise ShopItemInactiveError()
    buyer = db.query(models.User).filter(models.User.id == user.id).first()
    if not buyer:
        raise ShopItemNotFoundError()
    existing = (
        db.query(models.UserInventoryItem)
        .filter(
            models.UserInventoryItem.user_id == buyer.id,
            models.UserInventoryItem.item_id == item.id,
        )
        .first()
    )
    if existing:
        raise InventoryDuplicateError()
    if _normalize_balance(buyer) < item.price:
        raise InsufficientGologaniError()
    buyer.gologani_balance = _normalize_balance(buyer) - item.price
    inventory_item = models.UserInventoryItem(user_id=buyer.id, item_id=item.id)
    transaction = models.GologaniTransaction(
        user_id=buyer.id,
        amount=-item.price,
        balance_after=buyer.gologani_balance,
        event_type="shop_purchase",
        source_type="shop_item",
        source_id=item.id,
        idempotency_key=f"purchase:{buyer.id}:{item.id}",
        description=f"Cumpărat: {item.name}",
        extra_data={"item_slug": item.slug, "item_slot": item.slot},
    )
    db.add(inventory_item)
    db.add(transaction)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise InventoryDuplicateError()
    db.refresh(inventory_item)
    return inventory_item

def equip_inventory_item(db: Session, user: models.User, item_id: int) -> models.UserEquippedItem:
    inventory_item = (
        db.query(models.UserInventoryItem)
        .options(joinedload(models.UserInventoryItem.item))
        .filter(
            models.UserInventoryItem.user_id == user.id,
            models.UserInventoryItem.item_id == item_id,
        )
        .first()
    )
    if not inventory_item or not inventory_item.item:
        raise InventoryItemNotFoundError()
    equipped = (
        db.query(models.UserEquippedItem)
        .filter(
            models.UserEquippedItem.user_id == user.id,
            models.UserEquippedItem.slot == inventory_item.item.slot,
        )
        .first()
    )
    if equipped:
        equipped.item_id = inventory_item.item_id
        equipped.equipped_at = func.now()
    else:
        equipped = models.UserEquippedItem(
            user_id=user.id,
            item_id=inventory_item.item_id,
            slot=inventory_item.item.slot,
        )
        db.add(equipped)
    db.commit()
    db.refresh(equipped)
    return equipped

def unequip_slot(db: Session, user: models.User, slot: str) -> bool:
    equipped = (
        db.query(models.UserEquippedItem)
        .filter(
            models.UserEquippedItem.user_id == user.id,
            models.UserEquippedItem.slot == slot,
        )
        .first()
    )
    if not equipped:
        return False
    db.delete(equipped)
    db.commit()
    return True


# ===================================
# FORUM CRUD FUNCTIONS
# ===================================
