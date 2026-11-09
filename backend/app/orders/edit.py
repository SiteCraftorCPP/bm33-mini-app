from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderItem, Variant
from app.orders.status import CUSTOMER_CANCELLABLE
from app.orders.stock import available_units
from app.promos.service import PromoError, preview_promo


class OrderEditError(ValueError):
    pass


def _load_order(db: Session, order_id: int) -> Order:
    order = db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    if order is None:
        raise OrderEditError("Заказ не найден")
    if order.status not in CUSTOMER_CANCELLABLE:
        raise OrderEditError("Редактировать можно только до принятия заказа")
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


def change_order_item_quantity(
    db: Session,
    *,
    order_id: int,
    item_id: int,
    delta: int,
) -> Order:
    if delta not in (-1, 1):
        raise OrderEditError("Некорректное изменение количества")

    order = _load_order(db, order_id)
    item = _find_item(order, item_id)
    new_quantity = item.quantity + delta
    if new_quantity < 1:
        raise OrderEditError("Чтобы убрать позицию, нажмите «Удалить»")

    variant = db.get(Variant, item.variant_id)
    if variant is None:
        raise OrderEditError("Вариант больше не продаётся")
    free = available_units(db, variant, exclude_order_id=order_id)
    if free < new_quantity:
        raise OrderEditError(f"По остаткам можно не больше {free} шт. в этой позиции")

    item.quantity = new_quantity
    recompute_order_totals(db, order)
    db.commit()
    return db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )


def remove_order_item(db: Session, *, order_id: int, item_id: int) -> Order:
    order = _load_order(db, order_id)
    if len(order.items) <= 1:
        raise OrderEditError("Это последняя позиция — отмените заказ целиком")
    item = _find_item(order, item_id)
    db.delete(item)
    order.items.remove(item)
    recompute_order_totals(db, order)
    db.commit()
    return db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
