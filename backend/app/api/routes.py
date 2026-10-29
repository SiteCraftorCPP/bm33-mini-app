from __future__ import annotations

import re
from collections import Counter

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.auth import TelegramIdentity, current_user, require_admin
from app.catalog.importer import (
    CatalogDataError,
    catalog_image_fetch_urls,
    extract_drive_file_id,
    stick_catalog_warnings,
)
from app.catalog.service import catalog_payload, sync_catalog
from app.config import Settings, get_settings
from app.db import get_db
from app.integrations.google_sheets import GoogleSheets, SheetsError
from app.models import PromoCode
from app.orders.status import OrderStatusError, cancel_order_by_customer
from app.orders.stock import available_units
from app.promos.service import PromoError, apply_promo, normalize_code, preview_promo, promo_to_dict
from app.models import Order, OrderItem, Product, RestockSubscription, Variant

router = APIRouter(prefix="/api")

ORDER_STATUS_LABELS = {
    "new": "Новый",
    "accepted": "Подтверждён",
    "contacted": "Связались",
    "cancelled": "Отменён",
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
    promoCode: str = Field(default="", max_length=32)


class PromoValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    subtotal: int = Field(ge=1)


class PromoCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    kind: str = Field(pattern="^(percent|fixed)$")
    value: int = Field(ge=1, le=1_000_000)
    maxUses: int | None = Field(default=None, ge=1, le=1_000_000)
    note: str = Field(default="", max_length=200)


class PromoPatchRequest(BaseModel):
    active: bool | None = None
    maxUses: int | None = Field(default=None, ge=1, le=1_000_000)
    note: str | None = Field(default=None, max_length=200)


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


_DRIVE_IMAGE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChesHockey/1.0)"}


def _drive_service_account_image(
    stored: str,
    settings: Settings,
    client: httpx.Client,
) -> httpx.Response | None:
    path = (settings.google_service_account_file or "").strip()
    if not path:
        return None
    for chunk in re.split(r"[|\n]+", stored):
        file_id = extract_drive_file_id(chunk.strip())
        if not file_id:
            continue
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests

            creds = service_account.Credentials.from_service_account_file(
                path,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            creds.refresh(google.auth.transport.requests.Request())
            response = client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"alt": "media", "supportsAllDrives": "true"},
                headers={"Authorization": f"Bearer {creds.token}"},
                timeout=60.0,
            )
            if response.status_code != 200:
                continue
            if len(response.content) < 512:
                continue
            return response
        except Exception:
            continue
    return None


@router.get("/catalog/image/{product_id}")
def catalog_product_image(
    product_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    product = db.get(Product, product_id)
    if product is None or not product.active:
        raise HTTPException(status_code=404, detail="Product not found")
    source = (product.image_url or "").strip()
    if not source:
        raise HTTPException(status_code=404, detail="No image")
    upstream = None
    last_error: Exception | None = None
    try:
        with httpx.Client(timeout=25.0, follow_redirects=True, headers=_DRIVE_IMAGE_HEADERS) as client:
            for candidate in catalog_image_fetch_urls(source):
                try:
                    response = client.get(candidate)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    last_error = exc
                    continue
                content_type = response.headers.get("content-type", "")
                body = response.content
                if not content_type.casefold().startswith("image/"):
                    if body[:3] == b"\xff\xd8\xff":
                        content_type = "image/jpeg"
                    elif body[:8] == b"\x89PNG\r\n\x1a\n":
                        content_type = "image/png"
                    elif body[:4] == b"RIFF" and body[8:12] == b"WEBP":
                        content_type = "image/webp"
                    else:
                        last_error = httpx.HTTPError(f"Not an image: {content_type}")
                        continue
                if len(body) < 512:
                    last_error = httpx.HTTPError("Image too small")
                    continue
                upstream = response
                break
            if upstream is None:
                upstream = _drive_service_account_image(source, settings, client)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Image fetch failed") from exc
    if upstream is None:
        raise HTTPException(status_code=502, detail="Image fetch failed") from last_error
    content_type = upstream.headers.get("content-type", "image/jpeg")
    return Response(
        content=upstream.content,
        media_type=content_type.split(";")[0].strip(),
        headers={"Cache-Control": "public, max-age=600, must-revalidate"},
    )


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

    subtotal = sum(by_id[variant_id].price * quantity for variant_id, quantity in quantities.items())
    discount = 0
    promo_code = ""
    if payload.promoCode.strip() and not demo_order:
        try:
            promo, discount = apply_promo(db, payload.promoCode, subtotal)
            promo_code = promo.code
        except PromoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    total = max(subtotal - discount, 0)
    order = Order(
        telegram_user_id=user.id,
        telegram_username=user.username,
        customer_name=payload.customerName.strip(),
        phone=payload.phone.strip(),
        city=payload.city.strip(),
        delivery=payload.delivery.strip(),
        comment=payload.comment.strip(),
        promo_code=promo_code,
        discount=discount,
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


@router.post("/promos/validate")
def validate_promo_code(
    payload: PromoValidateRequest,
    user: TelegramIdentity = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        promo, discount = preview_promo(db, payload.code, payload.subtotal)
    except PromoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "code": promo.code,
        "discount": discount,
        "total": max(payload.subtotal - discount, 0),
    }


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


@router.post("/orders/{order_id}/cancel")
async def cancel_my_order(
    order_id: int,
    request: Request,
    user: TelegramIdentity = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    if user.is_demo:
        raise HTTPException(status_code=400, detail="Демо-заказ нельзя отменить на сервере")
    try:
        order = await cancel_order_by_customer(
            db,
            order_id=order_id,
            telegram_user_id=user.id,
        )
    except OrderStatusError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        await request.app.state.telegram.notify_order_updated(
            order.id,
            prefix="❌ Клиент отменил заказ",
        )
    except Exception:
        request.app.state.logger.exception("order cancel notify failed", extra={"order_id": order.id})
    return {
        "id": order.id,
        "status": order.status,
        "statusLabel": ORDER_STATUS_LABELS.get(order.status, order.status),
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
    stick_warnings = stick_catalog_warnings(imported)
    return {
        "ok": True,
        "products": len(imported),
        "restocked": len(restocked),
        "stickWarnings": stick_warnings,
    }


@router.get("/admin/promos")
def admin_list_promos(
    user: TelegramIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    promos = db.scalars(select(PromoCode).order_by(PromoCode.created_at.desc())).all()
    return {"promos": [promo_to_dict(promo) for promo in promos]}


@router.post("/admin/promos", status_code=status.HTTP_201_CREATED)
def admin_create_promo(
    payload: PromoCreateRequest,
    user: TelegramIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    code = normalize_code(payload.code)
    if db.get(PromoCode, code):
        raise HTTPException(status_code=409, detail="Такой промокод уже есть")
    if payload.kind == "percent" and payload.value > 100:
        raise HTTPException(status_code=400, detail="Процент не может быть больше 100")
    promo = PromoCode(
        code=code,
        kind=payload.kind,
        value=payload.value,
        max_uses=payload.maxUses,
        note=payload.note.strip(),
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo_to_dict(promo)


@router.patch("/admin/promos/{code}")
def admin_patch_promo(
    code: str,
    payload: PromoPatchRequest,
    user: TelegramIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    promo = db.get(PromoCode, normalize_code(code))
    if promo is None:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    if payload.active is not None:
        promo.active = payload.active
    if payload.maxUses is not None:
        promo.max_uses = payload.maxUses
    if payload.note is not None:
        promo.note = payload.note.strip()
    db.commit()
    db.refresh(promo)
    return promo_to_dict(promo)


@router.delete("/admin/promos/{code}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_promo(
    code: str,
    user: TelegramIdentity = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    promo = db.get(PromoCode, normalize_code(code))
    if promo is None:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    db.delete(promo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
