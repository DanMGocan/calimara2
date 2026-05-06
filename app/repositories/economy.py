from ._shared import *
from .posts import get_post

GOLOGANI_REWARDS = {
    "post_approved": 25,
    "comment_approved": 8,
    "like_given": 1,
    "like_received": 2,
    "super_like_given": 5,
    "super_like_received": 15,
    "forum_thread_approved": 15,
    "forum_reply_approved": 8,
}

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

class InventoryDuplicateError(EconomyError):
    pass

class InventoryItemNotFoundError(EconomyError):
    pass

def _normalize_balance(user: models.User) -> int:
    return int(user.gologani_balance or 0)

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
    return transaction

def award_content_approved(db: Session, content_type: str, content) -> Optional[models.GologaniTransaction]:
    reward_key = f"{content_type}_approved"
    amount = GOLOGANI_REWARDS.get(reward_key)
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
        amount=GOLOGANI_REWARDS["like_given"],
        event_type="like_given",
        source_type="like",
        source_id=like.id,
        idempotency_key=f"reward:like_given:{like.user_id}:{like.post_id}",
        description="Apreciere oferită",
    )
    grant_gologani(
        db,
        user_id=post.user_id,
        amount=GOLOGANI_REWARDS["like_received"],
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
        amount=GOLOGANI_REWARDS["super_like_given"],
        event_type="super_like_given",
        source_type="super_like",
        source_id=super_like.id,
        idempotency_key=f"reward:super_like_given:{super_like.user_id}:{super_like.post_id}",
        description="Super-apreciere oferită",
    )
    grant_gologani(
        db,
        user_id=post.user_id,
        amount=GOLOGANI_REWARDS["super_like_received"],
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
