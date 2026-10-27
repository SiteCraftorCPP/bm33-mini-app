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

from app.bot.order_messages import format_order_text, order_action_markup, user_accepted_markup
from app.config import Settings
from app.db import SessionLocal
from app.integrations.google_sheets import GoogleSheets, SheetsError
from app.models import Order, Product, RestockSubscription, Variant
from app.orders.stock import fulfill_accepted_order, restore_accepted_order_stock


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
            inline_keyboard=[[InlineKeyboardButton(text="💬 Написать менеджеру", url=url)]]
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
                        "💬 Напишите менеджеру в Telegram - ответит в личных сообщениях.",
                        reply_markup=markup,
                    )
                else:
                    await message.answer(
                        "Контакт менеджера пока не настроен. 🏒 Оформите заказ в магазине - мы свяжемся с вами.",
                        reply_markup=self._home_keyboard(),
                    )
                return
            await message.answer(
                "🏒 Добро пожаловать в Ches Hockey!\n\n"
                "🧤 Экипировка в наличии - быстрое оформление через менеджера",
                reply_markup=self._start_keyboard(),
            )

        @router.callback_query(F.data == "support")
        async def support(call: CallbackQuery) -> None:
            markup = self._manager_link_markup()
            await call.answer()
            if markup and call.message:
                await call.message.answer("📲 Перейдите в чат с менеджером:", reply_markup=markup)
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
            labels = {
                "accepted": "Принят",
                "contacted": "Связались",
                "cancelled": "Отменён",
            }
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
                if order.status == "cancelled":
                    await call.answer("Заказ уже отменён", show_alert=True)
                    return
                previous_status = order.status
                user_id = order.telegram_user_id
                if new_status == "accepted" and previous_status != "accepted":
                    try:
                        await fulfill_accepted_order(db, self.sheets, order_id)
                    except SheetsError as exc:
                        await call.answer(str(exc), show_alert=True)
                        return
                if new_status == "cancelled" and previous_status == "accepted":
                    try:
                        await restore_accepted_order_stock(db, self.sheets, order_id)
                    except SheetsError as exc:
                        await call.answer(str(exc), show_alert=True)
                        return
                order = db.get(Order, order_id)
                if order is None:
                    await call.answer("Заказ не найден", show_alert=True)
                    return
                order.status = new_status
                db.commit()
                order = db.scalar(
                    select(Order)
                    .where(Order.id == order_id)
                    .options(selectinload(Order.items))
                )

            await call.answer(labels[new_status])
            if self.bot and order:
                try:
                    card_text = format_order_text(order)
                    markup = order_action_markup(
                        order_id,
                        order.status,
                        self.settings.public_webapp_url,
                    )
                    if call.message:
                        await call.message.edit_text(card_text, reply_markup=markup)
                except Exception:
                    self.log.exception("order card edit failed")

                admin_name = call.from_user.full_name or "Менеджер"
                admin_note = f"Заказ №{order_id}: {labels[new_status].lower()} ({admin_name})"
                for chat_id in self.target_chat_ids:
                    if call.message and call.message.chat.id == chat_id:
                        continue
                    try:
                        await self.bot.send_message(chat_id, admin_note)
                    except Exception:
                        self.log.exception("order status admin notify failed", extra={"chat_id": chat_id})

                if new_status == "accepted":
                    try:
                        await self.bot.send_message(
                            user_id,
                            f"Заказ №{order_id} принят. Спасибо за заказ!",
                            reply_markup=user_accepted_markup(
                                order_id,
                                self.settings.public_webapp_url,
                            ),
                        )
                    except Exception:
                        self.log.exception("order status user notify failed")
                elif new_status == "cancelled":
                    try:
                        await self.bot.send_message(
                            user_id,
                            f"Заказ №{order_id} отменён. Если нужна помощь - напишите менеджеру.",
                        )
                    except Exception:
                        self.log.exception("order cancel user notify failed")

    async def start(self) -> None:
        if self.bot is None:
            return
        try:
            await self.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🛒 Магазин",
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
            text = format_order_text(order)
            markup = order_action_markup(
                order_id,
                order.status,
                self.settings.public_webapp_url,
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
                    text="🛒 Открыть магазин",
                    web_app=WebAppInfo(url=self.settings.public_webapp_url),
                )
            ],
        ]
        url = self.settings.manager_telegram_url
        if url:
            rows.append([InlineKeyboardButton(text="💬 Написать менеджеру", url=url)])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def _home_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 Вернуться в магазин",
                        web_app=WebAppInfo(url=self.settings.public_webapp_url),
                    )
                ]
            ]
        )
