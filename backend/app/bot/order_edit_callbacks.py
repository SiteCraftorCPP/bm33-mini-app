from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.order_messages import (
    format_order_edit_confirm_remove,
    format_order_edit_header,
    format_order_edit_item_screen,
    format_order_text,
    order_action_markup,
    order_action_markup_accepted_edit,
    order_edit_confirm_remove_markup,
    order_edit_item_markup,
    order_edit_list_markup,
    user_order_markup,
)
from app.db import SessionLocal
from app.models import Order
from app.orders.edit import OrderEditError, change_order_item_quantity, remove_order_item

if TYPE_CHECKING:
    from app.bot.runtime import TelegramService


def _parse_oed(data: str) -> tuple[int, str, int | None, int]:
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "oed" or not parts[1].isdigit():
        raise ValueError("bad callback")
    order_id = int(parts[1])
    action = parts[2]
    item_id: int | None = None
    page = 0
    if len(parts) >= 4:
        if parts[3].isdigit():
            if action in {"list", "noop"}:
                page = int(parts[3])
            else:
                item_id = int(parts[3])
    return order_id, action, item_id, page


async def handle_order_edit_callback(service: TelegramService, call: CallbackQuery) -> None:
    log = logging.getLogger("telegram")
    if call.from_user.id not in service.settings.admin_id_set:
        await call.answer("Нет доступа", show_alert=True)
        return

    try:
        order_id, action, item_id, page = _parse_oed(call.data or "")
    except ValueError:
        await call.answer()
        return

    if action == "noop":
        await call.answer()
        return

    notify_user = False
    with SessionLocal() as db:
        order = db.scalar(
            select(Order).where(Order.id == order_id).options(selectinload(Order.items))
        )
        if order is None:
            await call.answer("Заказ не найден", show_alert=True)
            return

        try:
            if action in {"p", "d"} and item_id is not None:
                delta = 1 if action == "p" else -1
                order = await change_order_item_quantity(
                    db,
                    service.sheets,
                    order_id=order_id,
                    item_id=item_id,
                    delta=delta,
                )
                await call.answer("Сохранено")
            elif action == "x" and item_id is not None:
                order = await remove_order_item(
                    db,
                    service.sheets,
                    order_id=order_id,
                    item_id=item_id,
                )
                await call.answer("Позиция убрана")
                page = 0
            elif action not in {"list", "done", "i", "xd"}:
                await call.answer()
                return
            else:
                await call.answer()
            if action == "done":
                notify_user = True
        except OrderEditError as exc:
            await call.answer(str(exc), show_alert=True)
            return

        user_id = order.telegram_user_id

    if not call.message or not service.bot:
        return

    try:
        text: str
        markup = None
        if action == "done":
            text = format_order_text(order)
            if order.status == "accepted":
                markup = order_action_markup_accepted_edit(order_id)
            else:
                markup = order_action_markup(
                    order_id,
                    order.status,
                    service.settings.webapp_base_url,
                )
        elif action == "xd" and item_id is not None:
            item = next((i for i in order.items if i.id == item_id), None)
            if item is None:
                text = format_order_edit_header(order, page=page)
                markup = order_edit_list_markup(order, page=page)
            else:
                text = format_order_edit_confirm_remove(order, item)
                markup = order_edit_confirm_remove_markup(order_id, item_id)
        elif action == "i" and item_id is not None:
            item = next((i for i in order.items if i.id == item_id), None)
            if item is None:
                text = format_order_edit_header(order, page=page)
                markup = order_edit_list_markup(order, page=page)
            else:
                text = format_order_edit_item_screen(order, item)
                markup = order_edit_item_markup(order_id, item_id)
        elif action == "x":
            text = format_order_edit_header(order, page=page)
            markup = order_edit_list_markup(order, page=page)
        else:
            if action in {"p", "d"} and item_id is not None:
                item = next((i for i in order.items if i.id == item_id), None)
                if item:
                    text = format_order_edit_item_screen(order, item)
                    markup = order_edit_item_markup(order_id, item_id)
                else:
                    text = format_order_edit_header(order, page=page)
                    markup = order_edit_list_markup(order, page=page)
            else:
                text = format_order_edit_header(order, page=page)
                markup = order_edit_list_markup(order, page=page)
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:
        log.exception("order edit card failed")

    if notify_user:
        try:
            await service.bot.send_message(
                user_id,
                f"Менеджер обновил заказ №{order_id}. Итого: {order.total:,} ₽".replace(",", " "),
                reply_markup=user_order_markup(order_id, service.settings.webapp_base_url),
            )
        except Exception:
            log.exception("order edit user notify failed", extra={"order_id": order_id})
