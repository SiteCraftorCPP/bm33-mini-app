from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PromoCode


class PromoError(ValueError):
    pass


def normalize_code(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def calculate_discount(subtotal: int, promo: PromoCode) -> int:
    if promo.kind == "percent":
        return max(0, min(subtotal, subtotal * promo.value // 100))
    if promo.kind == "fixed":
        return max(0, min(subtotal, promo.value))
    raise PromoError("Некорректный тип промокода")


def _load_promo(db: Session, code: str, *, lock: bool) -> PromoCode | None:
    stmt = select(PromoCode).where(PromoCode.code == code)
    if lock:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def _check_promo(promo: PromoCode | None, subtotal: int) -> int:
    if promo is None:
        raise PromoError("Промокод не найден")
    if not promo.active:
        raise PromoError("Промокод отключён")
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        raise PromoError("Промокод исчерпан")
    discount = calculate_discount(subtotal, promo)
    if discount <= 0:
        raise PromoError("Промокод не даёт скидку для этой суммы")
    return discount


def preview_promo(db: Session, raw_code: str, subtotal: int) -> tuple[PromoCode, int]:
    code = normalize_code(raw_code)
    if not code:
        raise PromoError("Введите промокод")
    if subtotal <= 0:
        raise PromoError("Сумма заказа должна быть больше нуля")
    promo = _load_promo(db, code, lock=False)
    discount = _check_promo(promo, subtotal)
    return promo, discount


def apply_promo(db: Session, raw_code: str, subtotal: int) -> tuple[PromoCode, int]:
    code = normalize_code(raw_code)
    if not code:
        raise PromoError("Введите промокод")
    promo = _load_promo(db, code, lock=True)
    discount = _check_promo(promo, subtotal)
    promo.used_count += 1
    return promo, discount


def promo_to_dict(promo: PromoCode) -> dict:
    return {
        "code": promo.code,
        "kind": promo.kind,
        "value": promo.value,
        "maxUses": promo.max_uses,
        "usedCount": promo.used_count,
        "active": promo.active,
        "note": promo.note,
        "createdAt": promo.created_at.isoformat(),
    }
