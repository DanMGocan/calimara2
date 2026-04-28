from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import admin, auth, crud, models, schemas
from ..database import get_db

router = APIRouter(tags=["shop"])


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


@router.get("/api/shop/items", response_model=schemas.ShopState)
def list_shop_items_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return _shop_state(db, current_user)


@router.get("/api/shop/me", response_model=schemas.ShopState)
def get_my_shop_state_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return _shop_state(db, current_user)


@router.post("/api/shop/items/{item_id}/purchase", response_model=schemas.ShopState)
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


@router.post("/api/inventory/equip", response_model=schemas.ShopState)
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


@router.delete("/api/inventory/equipped/{slot}", response_model=schemas.ShopState)
def unequip_slot_api(
    slot: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    crud.unequip_slot(db, current_user, slot)
    return _shop_state(db, current_user)


@router.get("/api/admin/shop/items", response_model=list[schemas.ShopItemOut])
def admin_list_shop_items_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    return [_item_payload(item) for item in crud.list_shop_items(db, include_inactive=True)]


@router.post(
    "/api/admin/shop/items",
    response_model=schemas.ShopItemOut,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_shop_item_api(
    data: schemas.ShopItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    try:
        item = crud.create_shop_item(db, data)
    except crud.ShopItemDuplicateSlugError:
        raise HTTPException(status_code=409, detail="Există deja un obiect cu acest slug")
    return _item_payload(item)


@router.put("/api/admin/shop/items/{item_id}", response_model=schemas.ShopItemOut)
def admin_update_shop_item_api(
    item_id: int,
    data: schemas.ShopItemUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    try:
        item = crud.update_shop_item(db, item_id, data)
    except crud.ShopItemDuplicateSlugError:
        raise HTTPException(status_code=409, detail="Există deja un obiect cu acest slug")
    if not item:
        raise HTTPException(status_code=404, detail="Obiectul nu a fost găsit")
    return _item_payload(item)
