from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.models import Order

STATUS_LINE = {
    "new": "",
    "contacted": "📞 Связались",
    "accepted": "✅ Принят",
    "cancelled": "❌ Отменён",
}


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
            f"({item.unit_price * item.quantity:,} ₽)".replace(",", " ")
            for item in order.items
        ],
        "",
        f"Итого: {order.total:,} ₽".replace(",", " "),
    ]
    if (order.discount or 0) > 0:
        lines.append(f"Промокод {order.promo_code}: -{order.discount:,} ₽".replace(",", " "))
    lines.extend(
        [
            f"Клиент: {order.customer_name}",
            f"Телефон: {order.phone}",
            f"Город: {order.city or 'не указан'}",
            f"Получение: {order.delivery or 'уточнить'}",
        ]
    )
    if order.telegram_username:
        lines.append(f"Telegram: @{order.telegram_username}")
    else:
        lines.append(f"Telegram ID: {order.telegram_user_id}")
    if order.comment:
        lines.append(f"Комментарий: {order.comment}")
    return "\n".join(lines)


def order_action_markup(order_id: int, status: str, webapp_url: str) -> InlineKeyboardMarkup | None:
    if status in {"accepted", "cancelled"}:
        return None
    cancel_row = [
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"order:{order_id}:cancelled"),
    ]
    if status == "contacted":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принять",
                        callback_data=f"order:{order_id}:accepted",
                    ),
                ],
                cancel_row,
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"order:{order_id}:accepted"),
                InlineKeyboardButton(text="📞 Связались", callback_data=f"order:{order_id}:contacted"),
            ],
            cancel_row,
        ]
    )


def user_accepted_markup(order_id: int, webapp_url: str) -> InlineKeyboardMarkup:
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
