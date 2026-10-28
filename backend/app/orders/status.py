from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order

CUSTOMER_CANCELLABLE = frozenset({"new", "contacted"})


class OrderStatusError(ValueError):
    pass


async def cancel_order_by_customer(
    db: Session,
    *,
    order_id: int,
    telegram_user_id: int,
) -> Order:
    order = db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    if order is None or order.telegram_user_id != telegram_user_id:
        raise OrderStatusError("Заказ не найден")
    if order.status == "cancelled":
        raise OrderStatusError("Заказ уже отменён")
    if order.status not in CUSTOMER_CANCELLABLE:
        raise OrderStatusError("Этот заказ уже обрабатывается — напишите менеджеру")

    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order
