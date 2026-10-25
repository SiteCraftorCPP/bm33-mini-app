from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.integrations.google_sheets import GoogleSheets, SheetsError, StockUpdate
from app.models import Order, OrderItem, Variant

# Остаток в таблице и локально списываем только после «Принять».
RESERVING_STATUSES = ("new", "contacted")


def pending_quantities(db: Session, *, exclude_order_id: int | None = None) -> Counter[str]:
    stmt = (
        select(OrderItem.variant_id, OrderItem.quantity)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status.in_(RESERVING_STATUSES))
    )
    if exclude_order_id is not None:
        stmt = stmt.where(Order.id != exclude_order_id)
    counts: Counter[str] = Counter()
    for variant_id, quantity in db.execute(stmt).all():
        counts[variant_id] += quantity
    return counts


def available_units(db: Session, variant: Variant, *, exclude_order_id: int | None = None) -> int:
    pending = pending_quantities(db, exclude_order_id=exclude_order_id)
    return max(variant.stock - pending.get(variant.id, 0), 0)


def _stock_update(variant: Variant, expected_stock: int, new_stock: int) -> StockUpdate:
    return StockUpdate(
        variant_id=variant.id,
        expected_stock=expected_stock,
        new_stock=new_stock,
        sheet_gid=variant.sheet_gid,
        sheet_row=variant.sheet_row,
        stock_column=variant.stock_column,
    )


async def fulfill_accepted_order(
    db: Session,
    sheets: GoogleSheets,
    order_id: int,
    *,
    demo: bool = False,
) -> None:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    )
    if order is None:
        raise SheetsError("Заказ не найден")

    quantities = Counter[str]()
    for item in order.items:
        quantities[item.variant_id] += item.quantity

    variant_ids = list(quantities)
    variants = db.scalars(
        select(Variant)
        .where(Variant.id.in_(variant_ids))
        .options(selectinload(Variant.product))
        .with_for_update()
    ).all()
    by_id = {variant.id: variant for variant in variants}

    for variant_id, quantity in quantities.items():
        variant = by_id.get(variant_id)
        if variant is None:
            raise SheetsError("Один из вариантов больше не продаётся")
        if available_units(db, variant, exclude_order_id=order.id) < quantity:
            raise SheetsError(
                f"«{variant.product.name}»: недостаточно остатка для подтверждения (нужно {quantity} шт.)"
            )

    sheet_variants = [by_id[vid] for vid in quantities if by_id[vid].sheet_gid != "demo"]
    updates = [
        _stock_update(
            variant,
            variant.stock,
            variant.stock - quantities[variant.id],
        )
        for variant in sheet_variants
    ]
    before = [
        _stock_update(
            variant,
            variant.stock - quantities[variant.id],
            variant.stock,
        )
        for variant in sheet_variants
    ]

    if not demo and updates:
        await sheets.update_stocks(updates)

    for variant_id, quantity in quantities.items():
        by_id[variant_id].stock -= quantity
