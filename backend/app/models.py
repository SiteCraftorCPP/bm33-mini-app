from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    variants: Mapped[list[Variant]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="Variant.sheet_row",
    )


class Variant(Base):
    __tablename__ = "variants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    sheet_gid: Mapped[str] = mapped_column(String(20), index=True)
    sheet_row: Mapped[int] = mapped_column(Integer)
    stock_column: Mapped[int] = mapped_column(Integer)
    option1_name: Mapped[str] = mapped_column(String(32), default="")
    option1_value: Mapped[str] = mapped_column(String(100), default="")
    option2_name: Mapped[str] = mapped_column(String(32), default="")
    option2_value: Mapped[str] = mapped_column(String(100), default="")
    side: Mapped[str] = mapped_column(String(1), default="")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product: Mapped[Product] = relationship(back_populates="variants")

    @property
    def label(self) -> str:
        parts = [value for value in (self.option1_value, self.option2_value, self.side) if value]
        return " / ".join(parts) or "Стандарт"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, index=True)
    telegram_username: Mapped[str] = mapped_column(String(64), default="")
    customer_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(40))
    city: Mapped[str] = mapped_column(String(120), default="")
    delivery: Mapped[str] = mapped_column(String(80), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    promo_code: Mapped[str] = mapped_column(String(32), default="")
    discount: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    variant_id: Mapped[str] = mapped_column(String(64))
    product_name: Mapped[str] = mapped_column(String(240))
    variant_label: Mapped[str] = mapped_column(String(240))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class RestockSubscription(Base):
    __tablename__ = "restock_subscriptions"
    __table_args__ = (UniqueConstraint("telegram_user_id", "variant_id", name="uq_restock_user_variant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, index=True)
    variant_id: Mapped[str] = mapped_column(String(64), index=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromoCode(Base):
    __tablename__ = "promo_codes"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupportTopic(Base):
    __tablename__ = "support_topics"

    telegram_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
