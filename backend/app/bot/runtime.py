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
from app.models import Order, Product, RestockSubscription, SupportTopic, Variant


class TelegramService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bot = Bot(settings.bot_token) if settings.bot_token else None
        self.dispatcher = Dispatcher()
        self.router = Router()
        self.dispatcher.include_router(self.router)
        self.polling_task: asyncio.Task | None = None
        self.waiting_users: set[int] = set()
        self.admin_replies: dict[int, tuple[int, int | None]] = {}
        self.log = logging.getLogger("telegram")
        self._register_handlers()

    @property
    def target_chat_ids(self) -> list[int]:
        if self.settings.support_chat_id_int is not None:
            return [self.settings.support_chat_id_int]
        return list(self.settings.admin_id_set)

    def _register_handlers(self) -> None:
        router = self.router

        @router.message(CommandStart())
        async def start(message: Message) -> None:
            args = (message.text or "").split(maxsplit=1)
            if len(args) > 1 and args[1] == "support":
                self.waiting_users.add(message.from_user.id)
                await message.answer(
                    "Напишите сообщение менеджеру. Можно отправить текст, фото или видео.",
                    reply_markup=self._home_keyboard(),
                )
                return
            await message.answer(
                "Добро пожаловать в Ches Hockey.\nЭкипировка в наличии с быстрым оформлением через менеджера.",
                reply_markup=self._start_keyboard(),
            )

        @router.callback_query(F.data == "support")
        async def support(call: CallbackQuery) -> None:
            self.waiting_users.add(call.from_user.id)
            await call.answer()
            await call.message.answer("Напишите сообщение. Менеджер ответит прямо сюда.")

        @router.callback_query(F.data.startswith("reply:"))
        async def arm_reply(call: CallbackQuery) -> None:
            if call.from_user.id not in self.settings.admin_id_set:
                await call.answer("Нет доступа", show_alert=True)
                return
            target = call.data.removeprefix("reply:")
            if not target.isdigit():
                await call.answer()
                return
            self.admin_replies[call.from_user.id] = (
                int(target),
                call.message.message_thread_id if call.message else None,
            )
            await call.answer()
            await call.message.answer("Введите ответ пользователю.")

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
            with SessionLocal() as db:
                order = db.get(Order, int(parts[1]))
                if order is None:
                    await call.answer("Заказ не найден", show_alert=True)
                    return
                order.status = new_status
                user_id = order.telegram_user_id
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

        @router.message()
        async def route_message(message: Message) -> None:
            if message.from_user is None or self.bot is None:
                return
            if message.from_user.id in self.admin_replies:
                await self._handle_admin_message(message)
                return
            support_chat_id = self.settings.support_chat_id_int
            if support_chat_id is not None and message.chat.id == support_chat_id:
                await self._handle_admin_message(message)
                return
            if message.chat.type != "private" or (message.text or "").startswith("/"):
                return
            if message.from_user.id not in self.waiting_users:
                return
            await self._forward_ticket(message)

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

    async def _forward_ticket(self, message: Message) -> None:
        chat_id = self.settings.support_chat_id_int
        if chat_id is None:
            for admin_id in self.settings.admin_id_set:
                await self._copy_with_header(message, admin_id, None)
        else:
            thread_id = await self._topic_for(message, chat_id)
            await self._copy_with_header(message, chat_id, thread_id)
        await message.answer("Сообщение передано. Ответ менеджера придёт сюда.")

    async def _topic_for(self, message: Message, chat_id: int) -> int:
        with SessionLocal() as db:
            topic = db.get(SupportTopic, message.from_user.id)
            if topic:
                return topic.thread_id
            name = message.from_user.full_name
            if message.from_user.username:
                name += f" @{message.from_user.username}"
            created = await self.bot.create_forum_topic(chat_id, name=name[:128])
            db.add(
                SupportTopic(
                    telegram_user_id=message.from_user.id,
                    thread_id=created.message_thread_id,
                )
            )
            db.commit()
            return created.message_thread_id

    async def _copy_with_header(self, message: Message, chat_id: int, thread_id: int | None) -> None:
        kwargs = {"message_thread_id": thread_id} if thread_id else {}
        username = f"@{message.from_user.username}" if message.from_user.username else "без username"
        header = f"{message.from_user.full_name} · {username} · ID {message.from_user.id}"
        await self.bot.send_message(
            chat_id,
            header,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Ответить", callback_data=f"reply:{message.from_user.id}")]
                ]
            ),
            **kwargs,
        )
        await self.bot.copy_message(chat_id, message.chat.id, message.message_id, **kwargs)

    async def _handle_admin_message(self, message: Message) -> None:
        if message.from_user.id not in self.settings.admin_id_set:
            return
        armed = self.admin_replies.pop(message.from_user.id, None)
        if armed is None:
            return
        target_id, thread_id = armed
        try:
            await self.bot.copy_message(target_id, message.chat.id, message.message_id)
            kwargs = {"message_thread_id": thread_id} if thread_id else {}
            await self.bot.send_message(message.chat.id, "Отправлено пользователю.", **kwargs)
        except Exception:
            self.log.exception("support reply failed")

    def _start_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Открыть магазин",
                        web_app=WebAppInfo(url=self.settings.public_webapp_url),
                    )
                ],
                [InlineKeyboardButton(text="Написать менеджеру", callback_data="support")],
            ]
        )

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
