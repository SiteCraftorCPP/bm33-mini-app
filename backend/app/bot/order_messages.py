from __future__ import annotations

import math

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.models import Order
from app.phone import format_phone_display

EDIT_PAGE_SIZE = 8

STATUS_LINE = {
    "new": "",
    "contacted": "📞 Связались",
    "accepted": "✅ Принят",
    "cancelled": "❌ Отменён",
}


def _money(value: int) -> str:
    return f"{value:,} ₽".replace(",", " ")


def format_order_text(order: Order) -> str:
    status = STATUS_LINE.get(order.status, order.status)
    header = f"Новый заказ №{order.id}"
    if status:
        header = f"{header}\n{status}"

    lines = [
        header,
        "",
        *[
            f"{item.product_name} - {item.variant_label} x {item.quantity} "
            f"({_money(item.unit_price * item.quantity)})"
            for item in order.items
        ],
        "",
        f"Итого: {_money(order.total)}",
    ]
    if (order.discount or 0) > 0:
        lines.append(f"Промокод {order.promo_code}: -{_money(order.discount)}")
    lines.extend(
        [
            f"Клиент: {order.customer_name}",
            f"Телефон: {format_phone_display(order.phone)}",
            f"Город: {order.city or 'не указан'}",
            f"Получение: {order.delivery or 'уточнить'}",
        ]
    )
    if order.telegram_username:
        lines.append(f"Telegram: @{order.telegram_username}")
    else:
        lines.append(
            f"Telegram: без @username (ID {order.telegram_user_id}) - кнопка «Написать клиенту»"
        )
    if order.comment:
        lines.append(f"Комментарий: {order.comment}")
    return "\n".join(lines)


def _short_variant_label(label: str) -> str:
    text = label.strip() or "—"
    if len(text) > 16:
        return f"{text[:14]}…"
    return text


def _item_button_label(item) -> str:
    qty = item.quantity
    name = item.product_name.strip()
    if len(name) > 18:
        name = f"{name[:16]}…"
    var = _short_variant_label(item.variant_label)
    text = f"×{qty} {name} · {var}"
    return text[:64]


def _edit_pages(order: Order) -> int:
    return max(1, math.ceil(len(order.items) / EDIT_PAGE_SIZE))


def _edit_page_items(order: Order, page: int) -> list:
    page = max(0, min(page, _edit_pages(order) - 1))
    start = page * EDIT_PAGE_SIZE
    return order.items[start : start + EDIT_PAGE_SIZE]


def format_order_edit_header(order: Order, *, page: int = 0) -> str:
    count = sum(item.quantity for item in order.items)
    pages = _edit_pages(order)
    page = max(0, min(page, pages - 1))
    lines = [
        f"✏️ Состав заказа №{order.id}",
        f"Позиций: {len(order.items)}, товаров: {count}",
        f"Итого: {_money(order.total)}",
    ]
    if order.status == "accepted":
        lines.append("⚠️ Заказ принят — при уменьшении остаток вернётся в таблицу")
    if pages > 1:
        lines.append(f"Стр. {page + 1}/{pages}")
    lines.append("")
    for index, item in enumerate(_edit_page_items(order, page), start=page * EDIT_PAGE_SIZE + 1):
        lines.append(
            f"{index}. {item.product_name} — {item.variant_label}\n"
            f"   ×{item.quantity} = {_money(item.unit_price * item.quantity)}"
        )
    lines.append("")
    lines.append("Нажмите строку ниже для ±1 или удаления:")
    return "\n".join(lines)


def format_order_edit_item_screen(order: Order, item) -> str:
    count = sum(i.quantity for i in order.items)
    header = [
        f"✏️ Заказ №{order.id} · {_money(order.total)}",
        f"Позиций: {len(order.items)}, товаров: {count}",
    ]
    if order.status == "accepted":
        header.append("⚠️ Уменьшение вернёт остаток в таблицу")
    return "\n".join(
        [
            *header,
            "",
            item.product_name,
            item.variant_label,
            f"Количество: {item.quantity}",
            f"Цена: {_money(item.unit_price)} × {item.quantity} = {_money(item.unit_price * item.quantity)}",
            "",
            "➕ / ➖ — изменить, 🗑 — удалить позицию.",
        ]
    )


def order_edit_list_markup(order: Order, *, page: int = 0) -> InlineKeyboardMarkup:
    pages = _edit_pages(order)
    page = max(0, min(page, pages - 1))
    rows: list[list[InlineKeyboardButton]] = []
    for item in _edit_page_items(order, page):
        rows.append(
            [
                InlineKeyboardButton(
                    text=_item_button_label(item),
                    callback_data=f"oed:{order.id}:i:{item.id}",
                )
            ]
        )
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(text="◀️", callback_data=f"oed:{order.id}:list:{page - 1}")
            )
        nav.append(
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=f"oed:{order.id}:noop")
        )
        if page < pages - 1:
            nav.append(
                InlineKeyboardButton(text="▶️", callback_data=f"oed:{order.id}:list:{page + 1}")
            )
        rows.append(nav)
    rows.append(
        [InlineKeyboardButton(text="✅ Готово — к карточке заказа", callback_data=f"oed:{order.id}:done")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_edit_item_markup(order_id: int, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖ 1", callback_data=f"oed:{order_id}:d:{item_id}"),
                InlineKeyboardButton(text="➕ 1", callback_data=f"oed:{order_id}:p:{item_id}"),
            ],
            [
                InlineKeyboardButton(text="🗑 Удалить позицию", callback_data=f"oed:{order_id}:xd:{item_id}"),
            ],
            [
                InlineKeyboardButton(text="← К списку", callback_data=f"oed:{order_id}:list:0"),
            ],
        ]
    )


def order_edit_confirm_remove_markup(order_id: int, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, убрать", callback_data=f"oed:{order_id}:x:{item_id}"),
                InlineKeyboardButton(text="← Нет", callback_data=f"oed:{order_id}:i:{item_id}"),
            ],
        ]
    )


def format_order_edit_confirm_remove(order: Order, item) -> str:
    return "\n".join(
        [
            f"Убрать из заказа №{order.id}?",
            "",
            f"{item.product_name} — {item.variant_label}",
            f"×{item.quantity} = {_money(item.unit_price * item.quantity)}",
            "",
            "Остаток вернётся в таблицу, если заказ уже принят.",
        ]
    )


def _client_contact_row(telegram_user_id: int, telegram_username: str) -> list[InlineKeyboardButton]:
    if telegram_user_id <= 0:
        return []
    if telegram_username:
        handle = telegram_username.strip().lstrip("@")
        url = f"https://t.me/{handle}"
    else:
        url = f"tg://user?id={telegram_user_id}"
    return [InlineKeyboardButton(text="💬 Написать клиенту", url=url)]


def order_action_markup(
    order_id: int,
    status: str,
    webapp_url: str,
    *,
    telegram_user_id: int = 0,
    telegram_username: str = "",
) -> InlineKeyboardMarkup | None:
    if status == "cancelled":
        return None
    if status == "accepted":
        return order_action_markup_accepted_edit(
            order_id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
        )
    client_row = _client_contact_row(telegram_user_id, telegram_username)
    edit_row = [
        InlineKeyboardButton(text="✏️ Состав", callback_data=f"oed:{order_id}:list:0"),
    ]
    cancel_row = [
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"order:{order_id}:cancelled"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    if client_row:
        rows.append(client_row)
    if status == "contacted":
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text="✅ Принять",
                        callback_data=f"order:{order_id}:accepted",
                    ),
                ],
                edit_row,
                cancel_row,
            ]
        )
    else:
        rows.extend(
            [
                [
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"order:{order_id}:accepted"),
                    InlineKeyboardButton(text="📞 Связались", callback_data=f"order:{order_id}:contacted"),
                ],
                edit_row,
                cancel_row,
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_action_markup_accepted_edit(
    order_id: int,
    *,
    telegram_user_id: int = 0,
    telegram_username: str = "",
) -> InlineKeyboardMarkup:
    """Карточка принятого заказа: правка состава (возврат в таблицу при уменьшении)."""
    rows: list[list[InlineKeyboardButton]] = []
    client_row = _client_contact_row(telegram_user_id, telegram_username)
    if client_row:
        rows.append(client_row)
    rows.append(
        [
            InlineKeyboardButton(text="✏️ Состав", callback_data=f"oed:{order_id}:list:0"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_order_markup(order_id: int, webapp_url: str) -> InlineKeyboardMarkup:
    order_url = f"{webapp_url.rstrip('/')}?order={order_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть заказ",
                    web_app=WebAppInfo(url=order_url),
                )
            ]
        ]
    )


def user_accepted_markup(order_id: int, webapp_url: str) -> InlineKeyboardMarkup:
    return user_order_markup(order_id, webapp_url)
