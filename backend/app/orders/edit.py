from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.integrations.google_sheets import GoogleSheets, SheetsError
from app.models import Order, OrderItem, Variant
from app.orders.stock import apply_stock_delta, available_units
from app.promos.service import PromoError, preview_promo

ADMIN_EDITABLE = frozenset({"new", "contacted", "accepted"})


class OrderEditError(ValueError):
    pass


def _load_order(db: Session, order_id: int) -> Order:
    order = db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    if order is None:
        raise OrderEditError("Заказ не найден")
    if order.status not in ADMIN_EDITABLE:
        raise OrderEditError("Редактировать можно только активные заказы (до отмены)")
    return order


def _find_item(order: Order, item_id: int) -> OrderItem:
    for item in order.items:
        if item.id == item_id:
            return item
    raise OrderEditError("Позиция не найдена")


def recompute_order_totals(db: Session, order: Order) -> None:
    if not order.items:
        raise OrderEditError("В заказе должна остаться хотя бы одна позиция")
    subtotal = sum(item.unit_price * item.quantity for item in order.items)
    discount = 0
    if order.promo_code.strip():
        try:
            _, discount = preview_promo(db, order.promo_code, subtotal)
        except PromoError:
            discount = 0
    order.discount = discount
    order.total = max(subtotal - discount, 0)


async def _sync_stock_for_delta(
    db: Session,
    sheets: GoogleSheets,
    *,
    order: Order,
    variant: Variant,
    quantity_delta: int,
    demo: bool = False,
) -> None:
    """quantity_delta < 0 убрали из заказа → вернуть в таблицу; > 0 добавили → списать."""
    if order.status != "accepted" or quantity_delta == 0:
        return
    stock_delta = -quantity_delta
    try:
        await apply_stock_delta(db, sheets, variant, stock_delta, demo=demo)
    except SheetsError as exc:
        raise OrderEditError(str(exc)) from exc


async def change_order_item_quantity(
    db: Session,
    sheets: GoogleSheets,
    *,
    order_id: int,
    item_id: int,
    delta: int,
    demo: bool = False,
) -> Order:
    if delta not in (-1, 1):
        raise OrderEditError("Некорректное изменение количества")

    order = _load_order(db, order_id)
    item = _find_item(order, item_id)
    old_quantity = item.quantity
    new_quantity = old_quantity + delta
    if new_quantity < 1:
        raise OrderEditError("Чтобы убрать позицию, нажмите «Удалить»")

    variant = db.get(Variant, item.variant_id)
    if variant is None:
        raise OrderEditError("Вариант больше не продаётся")

    if order.status == "accepted" and delta > 0 and variant.stock < delta:
        raise OrderEditError(f"На складе только {variant.stock} шт.")
    else:
        free = available_units(db, variant, exclude_order_id=order_id)
        if free < new_quantity:
            raise OrderEditError(f"По остаткам можно не больше {free} шт. в этой позиции")

    await _sync_stock_for_delta(
        db,
        sheets,
        order=order,
        variant=variant,
        quantity_delta=new_quantity - old_quantity,
        demo=demo,
    )

    item.quantity = new_quantity
    recompute_order_totals(db, order)
    db.commit()
    return db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )


async def remove_order_item(
    db: Session,
    sheets: GoogleSheets,
    *,
    order_id: int,
    item_id: int,
    demo: bool = False,
) -> Order:
    order = _load_order(db, order_id)
    if len(order.items) <= 1:
        raise OrderEditError("Это последняя позиция — отмените заказ целиком")
    item = _find_item(order, item_id)
    variant = db.get(Variant, item.variant_id)
    if variant is None:
        raise OrderEditError("Вариант больше не продаётся")

    await _sync_stock_for_delta(
        db,
        sheets,
        order=order,
        variant=variant,
        quantity_delta=-item.quantity,
        demo=demo,
    )

    db.delete(item)
    order.items.remove(item)
    recompute_order_totals(db, order)
    db.commit()
    return db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
