from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.auth import TelegramIdentity, current_user, require_admin
from app.catalog.service import catalog_payload, sync_catalog
from app.db import get_db
from app.integrations.google_sheets import GoogleSheets, SheetsError
from app.orders.stock import available_units
from app.models import Order, OrderItem, Product, RestockSubscription, Variant

router = APIRouter(prefix="/api")

ORDER_STATUS_LABELS = {
    "new": "Новый",
    "accepted": "Подтверждён",
    "contacted": "Связались",
}


def _order_summary(order: Order) -> dict:
    return {
        "id": order.id,
        "status": order.status,
        "statusLabel": ORDER_STATUS_LABELS.get(order.status, order.status),
        "total": order.total,
        "createdAt": order.created_at.isoformat(),
        "itemCount": sum(item.quantity for item in order.items),
    }


class CartLine(BaseModel):
    variantId: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=99)


class OrderRequest(BaseModel):
    items: list[CartLine] = Field(min_length=1, max_length=30)
    customerName: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=5, max_length=40)
    city: str = Field(default="", max_length=120)
    delivery: str = Field(default="", max_length=80)
    comment: str = Field(default="", max_length=1500)


class SubscriptionRequest(BaseModel):
    variantId: str = Field(min_length=1, max_length=64)


def sheets_from(request: Request) -> GoogleSheets:
    return request.app.state.sheets


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/config")
def public_config(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "managerTelegramUrl": settings.manager_telegram_url,
    }


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)) -> dict:
    return catalog_payload(db)


@router.post("/catalog/sync")
async def force_sync(
    request: Request,
    user: TelegramIdentity = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    settings = request.app.state.settings
    if user.id not in settings.admin_id_set and not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Только для администратора")
    try:
        imported = await sheets_from(request).fetch_catalog(force=True)
    except SheetsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    restocked = sync_catalog(db, imported)
    return {"ok": True, "products": len(imported), "restocked": len(restocked)}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderRequest,
    request: Request,
    user: TelegramIdentity = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    demo_order = user.is_demo

    quantities = Counter[str]()
    for line in payload.items:
        quantities[line.variantId] += line.quantity

    variants = db.scalars(
        select(Variant)
        .where(Variant.id.in_(quantities))
        .options(selectinload(Variant.product))
        .with_for_update()
    ).all()
    by_id = {variant.id: variant for variant in variants}
    missing = [variant_id for variant_id in quantities if variant_id not in by_id]
    if missing:
        raise HTTPException(status_code=409, detail="Один из вариантов больше не продаётся")

    for variant_id, quantity in quantities.items():
        variant = by_id[variant_id]
        if not variant.product.active:
            raise HTTPException(status_code=409, detail=f"{variant.product.name} больше не продаётся")
        free = available_units(db, variant)
        if free < quantity:
            raise HTTPException(
                status_code=409,
                detail=f"«{variant.product.name}»: доступно только {free} шт.",
            )

    total = sum(by_id[variant_id].price * quantity for variant_id, quantity in quantities.items())
    order = Order(
        telegram_user_id=user.id,
        telegram_username=user.username,
        customer_name=payload.customerName.strip(),
        phone=payload.phone.strip(),
        city=payload.city.strip(),
        delivery=payload.delivery.strip(),
        comment=payload.comment.strip(),
        total=total,
    )
    db.add(order)
    for variant_id, quantity in quantities.items():
        variant = by_id[variant_id]
        order.items.append(
            OrderItem(
                variant_id=variant.id,
                product_name=variant.product.name,
                variant_label=variant.label,
                quantity=quantity,
                unit_price=variant.price,
            )
        )
    try:
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось сохранить заказ")

    try:
        await request.app.state.telegram.notify_order(order.id)
    except Exception:
        request.app.state.logger.exception("order notification failed", extra={"order_id": order.id})

    return {"id": order.id, "status": order.status, "total": order.total}


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
def subscribe(
    payload: SubscriptionRequest,
    user: TelegramIdentity = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    variant = db.get(Variant, payload.variantId)
    if variant is None:
        raise HTTPException(status_code=404, detail="Вариант не найден")
    existing = db.scalar(
        select(RestockSubscription).where(
            RestockSubscription.telegram_user_id == user.id,
            RestockSubscription.variant_id == payload.variantId,
        )
    )
    if existing is None:
        db.add(RestockSubscription(telegram_user_id=user.id, variant_id=payload.variantId))
    else:
        existing.notified = False
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True}


@router.get("/me")
def me(request: Request, user: TelegramIdentity = Depends(current_user)) -> dict:
    settings = request.app.state.settings
    return {
        "id": user.id,
        "username": user.username,
        "firstName": user.first_name,
        "isDemo": user.is_demo,
        "isAdmin": user.id in settings.admin_id_set,
    }


@router.get("/orders")
def my_orders(
    user: TelegramIdentity = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    orders = db.scalars(
        select(Order)
        .where(Order.telegram_user_id == user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(50)
    ).all()
    return {"orders": [_order_summary(order) for order in orders]}


@router.get("/orders/{order_id}")
def order_status(
    order_id: int,
    user: TelegramIdentity = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    order = db.scalar(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    if order is None or order.telegram_user_id != user.id:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return {
        "id": order.id,
        "status": order.status,
        "statusLabel": ORDER_STATUS_LABELS.get(order.status, order.status),
        "total": order.total,
        "createdAt": order.created_at.isoformat(),
        "customerName": order.customer_name,
        "phone": order.phone,
        "city": order.city,
        "comment": order.comment,
        "items": [
            {
                "name": item.product_name,
                "variant": item.variant_label,
                "quantity": item.quantity,
                "price": item.unit_price,
            }
            for item in order.items
        ],
    }


@router.get("/admin/orders")
def admin_orders(
    user: TelegramIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(40)
    ).all()
    return {
        "orders": [
            {
                **_order_summary(order),
                "customerName": order.customer_name,
                "phone": order.phone,
                "telegramUserId": order.telegram_user_id,
            }
            for order in orders
        ]
    }


@router.post("/admin/catalog/sync")
async def admin_catalog_sync(
    request: Request,
    user: TelegramIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    sheets = sheets_from(request)
    if not sheets.can_write:
        raise HTTPException(
            status_code=503,
            detail="Нет доступа к Google service account на сервере. Проверьте права /etc/ches-hockey.",
        )
    try:
        imported = await sheets.fetch_catalog(force=True)
    except SheetsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=503,
            detail="Сервер не может прочитать ключ Google Sheets (права файла).",
        ) from exc
    restocked = sync_catalog(db, imported)
    return {"ok": True, "products": len(imported), "restocked": len(restocked)}
