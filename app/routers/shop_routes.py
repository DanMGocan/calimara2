from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import admin, auth, crud, models, schemas
from ..database import get_db

router = APIRouter(tags=["shop"])

# Magazinul și inventarul sunt vizibile, dar încă în dezvoltare: cumpărarea,
# echiparea și dezechiparea sunt blocate. Pune False ca să le redeschizi.
SHOP_ACTIONS_LOCKED = True
SHOP_LOCKED_DETAIL = (
    "În dezvoltare. Tu continuă să aduni gologani și noi ne asigurăm că ai pe ce îi cheltui!"
)


def require_shop_open() -> None:
    if SHOP_ACTIONS_LOCKED:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=SHOP_LOCKED_DETAIL)


def _audit_shop_item_change(
    db: Session,
    request: Request,
    actor: models.User,
    *,
    action: str,
    item: models.ShopItem,
) -> None:
    admin.write_admin_audit_log(
        db,
        actor,
        action=action,
        target_type="shop_item",
        target_id=item.id,
        request=request,
        extra_data={"slug": item.slug},
    )


def _audit_gologani_reward_change(
    db: Session,
    request: Request,
    actor: models.User,
    *,
    action: str,
    setting: models.GologaniRewardSetting,
) -> None:
    admin.write_admin_audit_log(
        db,
        actor,
        action=action,
        target_type="gologani_reward",
        request=request,
        extra_data={
            "event_type": setting.event_type,
            "amount": setting.amount,
            "is_active": setting.is_active,
        },
    )


def _item_payload(item: models.ShopItem, owned_ids=None, equipped_ids=None) -> dict:
    owned_ids = owned_ids or set()
    equipped_ids = equipped_ids or set()
    return {
        "id": item.id,
        "slug": item.slug,
        "name": item.name,
        "description": item.description,
        "price": item.price,
        "slot": item.slot,
        "asset_url": item.asset_url,
        "is_active": item.is_active,
        "sort_order": item.sort_order,
        "owned": item.id in owned_ids,
        "equipped": item.id in equipped_ids,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _inventory_payload(entry: models.UserInventoryItem, equipped_ids: set[int]) -> dict:
    return {
        "id": entry.id,
        "item": _item_payload(entry.item, owned_ids={entry.item_id}, equipped_ids=equipped_ids),
        "purchased_at": entry.purchased_at,
    }


def _equipped_payload(entry: models.UserEquippedItem) -> dict:
    return {
        "id": entry.id,
        "slot": entry.slot,
        "item": _item_payload(entry.item, owned_ids={entry.item_id}, equipped_ids={entry.item_id}),
        "equipped_at": entry.equipped_at,
    }


def _shop_state(db: Session, user: models.User) -> dict:
    db.refresh(user)
    inventory = crud.get_inventory_for_user(db, user.id)
    equipped = crud.get_equipped_items_for_user(db, user.id)
    owned_ids = {entry.item_id for entry in inventory}
    equipped_ids = {entry.item_id for entry in equipped}
    items = crud.list_shop_items(db, include_inactive=False)
    return {
        "balance": user.gologani_balance or 0,
        "items": [_item_payload(item, owned_ids=owned_ids, equipped_ids=equipped_ids) for item in items],
        "inventory": [_inventory_payload(entry, equipped_ids) for entry in inventory if entry.item],
        "equipped": [_equipped_payload(entry) for entry in equipped if entry.item],
    }


@router.get("/api/magazin/obiecte", response_model=schemas.ShopState)
def list_shop_items_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return _shop_state(db, current_user)


@router.get("/api/magazin/eu", response_model=schemas.ShopState)
def get_my_shop_state_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return _shop_state(db, current_user)


@router.post(
    "/api/magazin/obiecte/{item_id}/cumpara",
    response_model=schemas.ShopState,
    dependencies=[Depends(require_shop_open)],
)
def purchase_shop_item_api(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        crud.purchase_shop_item(db, current_user, item_id)
    except crud.ShopItemNotFoundError:
        raise HTTPException(status_code=404, detail="Obiectul nu a fost găsit")
    except crud.ShopItemInactiveError:
        raise HTTPException(status_code=409, detail="Obiectul nu mai este disponibil")
    except crud.InventoryDuplicateError:
        raise HTTPException(status_code=409, detail="Ai deja acest obiect în inventar")
    except crud.InsufficientGologaniError:
        raise HTTPException(status_code=402, detail="Nu ai destui Gologani")
    return _shop_state(db, current_user)


@router.post(
    "/api/inventar/echipeaza",
    response_model=schemas.ShopState,
    dependencies=[Depends(require_shop_open)],
)
def equip_inventory_item_api(
    data: schemas.EquipItemRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        crud.equip_inventory_item(db, current_user, data.item_id)
    except crud.InventoryItemNotFoundError:
        raise HTTPException(status_code=404, detail="Obiectul nu este în inventarul tău")
    return _shop_state(db, current_user)


@router.delete(
    "/api/inventar/echipate/{slot}",
    response_model=schemas.ShopState,
    dependencies=[Depends(require_shop_open)],
)
def unequip_slot_api(
    slot: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    crud.unequip_slot(db, current_user, slot)
    return _shop_state(db, current_user)


@router.get("/api/moderare/magazin/obiecte", response_model=list[schemas.ShopItemOut])
def admin_list_shop_items_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    return [_item_payload(item) for item in crud.list_shop_items(db, include_inactive=True)]


@router.post(
    "/api/moderare/magazin/obiecte",
    response_model=schemas.ShopItemOut,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_shop_item_api(
    data: schemas.ShopItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    try:
        item = crud.create_shop_item(db, data)
    except crud.ShopItemDuplicateSlugError:
        raise HTTPException(status_code=409, detail="Există deja un obiect cu acest slug")
    _audit_shop_item_change(db, request, current_user, action="shop_item_create", item=item)
    return _item_payload(item)


@router.put("/api/moderare/magazin/obiecte/{item_id}", response_model=schemas.ShopItemOut)
def admin_update_shop_item_api(
    item_id: int,
    data: schemas.ShopItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    try:
        item = crud.update_shop_item(db, item_id, data)
    except crud.ShopItemDuplicateSlugError:
        raise HTTPException(status_code=409, detail="Există deja un obiect cu acest slug")
    if not item:
        raise HTTPException(status_code=404, detail="Obiectul nu a fost găsit")
    _audit_shop_item_change(db, request, current_user, action="shop_item_update", item=item)
    return _item_payload(item)


@router.get("/api/moderare/gologani/recompense", response_model=list[schemas.GologaniRewardSettingOut])
def admin_list_gologani_rewards_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    return crud.list_gologani_reward_settings(db)


@router.put("/api/moderare/gologani/recompense/{event_type}", response_model=schemas.GologaniRewardSettingOut)
def admin_update_gologani_reward_api(
    event_type: str,
    data: schemas.GologaniRewardSettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    try:
        setting = crud.update_gologani_reward_setting(db, event_type, data, updated_by=current_user.id)
    except crud.GologaniRewardSettingNotFoundError:
        raise HTTPException(status_code=404, detail="Recompensa nu a fost găsită")
    _audit_gologani_reward_change(db, request, current_user, action="gologani_reward_update", setting=setting)
    return setting
