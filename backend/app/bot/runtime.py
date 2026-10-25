from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db import SessionLocal
from app.integrations.google_sheets import GoogleSheets, SheetsError
from app.models import Order, Product, RestockSubscription, Variant
from app.orders.stock import fulfill_accepted_order


class TelegramService:
    def __init__(self, settings: Settings, sheets: GoogleSheets):
        self.settings = settings
        self.sheets = sheets
        self.bot = Bot(settings.bot_token) if settings.bot_token else None
        self.dispatcher = Dispatcher()
        self.router = Router()
        self.dispatcher.include_router(self.router)
        self.polling_task: asyncio.Task | None = None
        self.log = logging.getLogger("telegram")
        self._register_handlers()

    @property
    def target_chat_ids(self) -> list[int]:
        if self.settings.support_chat_id_int is not None:
            return [self.settings.support_chat_id_int]
        return list(self.settings.admin_id_set)

    def _manager_link_markup(self) -> InlineKeyboardMarkup | None:
        url = self.settings.manager_telegram_url
        if not url:
            return None
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Написать менеджеру", url=url)]]
        )

    def _register_handlers(self) -> None:
        router = self.router

        @router.message(CommandStart())
        async def start(message: Message) -> None:
            args = (message.text or "").split(maxsplit=1)
            if len(args) > 1 and args[1] == "support":
                markup = self._manager_link_markup()
                if markup:
                    await message.answer(
                        "Напишите менеджеру в Telegram — ответит в личных сообщениях.",
                        reply_markup=markup,
                    )
                else:
                    await message.answer(
                        "Контакт менеджера пока не настроен. Оформите заказ в магазине — мы свяжемся с вами.",
                        reply_markup=self._home_keyboard(),
                    )
                return
            await message.answer(
                "Добро пожаловать в Ches Hockey.\nЭкипировка в наличии с быстрым оформлением через менеджера.",
                reply_markup=self._start_keyboard(),
            )

        @router.callback_query(F.data == "support")
        async def support(call: CallbackQuery) -> None:
            markup = self._manager_link_markup()
            await call.answer()
            if markup and call.message:
                await call.message.answer("Перейдите в чат с менеджером:", reply_markup=markup)
            elif call.message:
                await call.message.answer("Контакт менеджера пока не настроен.")

        @router.callback_query(F.data.startswith("order:"))
        async def update_order(call: CallbackQuery) -> None:
            if call.from_user.id not in self.settings.admin_id_set:
                await call.answer("Нет доступа", show_alert=True)
                return
            parts = call.data.split(":")
            if len(parts) != 3 or not parts[1].isdigit():
                await call.answer()
                return
            labels = {"accepted": "Принят", "contacted": "Связались"}
            new_status = parts[2]
            if new_status not in labels:
                await call.answer()
                return
            order_id = int(parts[1])
            with SessionLocal() as db:
                order = db.get(Order, order_id)
                if order is None:
                    await call.answer("Заказ не найден", show_alert=True)
                    return
                previous_status = order.status
                user_id = order.telegram_user_id
                if new_status == "accepted" and previous_status != "accepted":
                    try:
                        await fulfill_accepted_order(db, self.sheets, order_id)
                    except SheetsError as exc:
                        await call.answer(str(exc), show_alert=True)
                        return
                order = db.get(Order, order_id)
                if order is None:
                    await call.answer("Заказ не найден", show_alert=True)
                    return
                order.status = new_status
                db.commit()
            await call.answer(labels[new_status])
            if self.bot:
                try:
                    text = f"Статус заказа №{parts[1]}: {labels[new_status].lower()}."
                    markup = None
                    if new_status == "accepted":
                        order_url = f"{self.settings.public_webapp_url.rstrip('/')}?order={parts[1]}"
                        markup = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="Открыть заказ",
                                        web_app=WebAppInfo(url=order_url),
                                    )
                                ]
                            ]
                        )
                    await self.bot.send_message(user_id, text, reply_markup=markup)
                except Exception:
                    self.log.exception("order status notification failed")

    async def start(self) -> None:
        if self.bot is None:
            return
        try:
            await self.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть магазин",
                    web_app=WebAppInfo(url=self.settings.public_webapp_url),
                )
            )
        except Exception:
            self.log.exception("menu button setup failed; PUBLIC_WEBAPP_URL must be HTTPS")
        if self.settings.run_bot:
            self.polling_task = asyncio.create_task(
                self.dispatcher.start_polling(self.bot, handle_signals=False)
            )

    async def stop(self) -> None:
        if self.polling_task:
            self.polling_task.cancel()
            await asyncio.gather(self.polling_task, return_exceptions=True)
        if self.bot:
            await self.bot.session.close()

    async def notify_order(self, order_id: int) -> None:
        if self.bot is None:
            return
        with SessionLocal() as db:
            order = db.scalar(
                select(Order).where(Order.id == order_id).options(selectinload(Order.items))
            )
            if order is None:
                return
            lines = [
                f"Новый заказ №{order.id}",
                "",
                *[
                    f"• {item.product_name} — {item.variant_label} × {item.quantity} "
                    f"({item.unit_price * item.quantity:,} ₽)".replace(",", " ")
                    for item in order.items
                ],
                "",
                f"Итого: {order.total:,} ₽".replace(",", " "),
                f"Клиент: {order.customer_name}",
                f"Телефон: {order.phone}",
                f"Город: {order.city or 'не указан'}",
                f"Получение: {order.delivery or 'уточнить'}",
                f"Telegram: @{order.telegram_username}" if order.telegram_username else f"Telegram ID: {order.telegram_user_id}",
            ]
            if order.comment:
                lines.append(f"Комментарий: {order.comment}")
            text = "\n".join(lines)
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="Принять", callback_data=f"order:{order.id}:accepted"),
                        InlineKeyboardButton(text="Связались", callback_data=f"order:{order.id}:contacted"),
                    ]
                ]
            )
        for chat_id in self.target_chat_ids:
            await self.bot.send_message(chat_id, text, reply_markup=markup)

    async def notify_restock(self, variant_ids: list[str]) -> None:
        if self.bot is None or not variant_ids:
            return
        with SessionLocal() as db:
            subscriptions = db.scalars(
                select(RestockSubscription).where(
                    RestockSubscription.variant_id.in_(variant_ids),
                    RestockSubscription.notified.is_(False),
                )
            ).all()
            for subscription in subscriptions:
                variant = db.get(Variant, subscription.variant_id)
                product = db.get(Product, variant.product_id) if variant else None
                if not variant or not product or variant.stock <= 0:
                    continue
                try:
                    await self.bot.send_message(
                        subscription.telegram_user_id,
                        f"Снова в наличии: {product.name}, {variant.label}. Осталось {variant.stock} шт.",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="Открыть магазин",
                                        web_app=WebAppInfo(url=self.settings.public_webapp_url),
                                    )
                                ]
                            ]
                        ),
                    )
                    subscription.notified = True
                except Exception:
                    self.log.exception("restock notification failed")
            db.commit()

    def _start_keyboard(self) -> InlineKeyboardMarkup:
        rows = [
            [
                InlineKeyboardButton(
                    text="Открыть магазин",
                    web_app=WebAppInfo(url=self.settings.public_webapp_url),
                )
            ],
        ]
        url = self.settings.manager_telegram_url
        if url:
            rows.append([InlineKeyboardButton(text="Написать менеджеру", url=url)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _home_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Вернуться в магазин",
                        web_app=WebAppInfo(url=self.settings.public_webapp_url),
                    )
                ]
            ]
        )
