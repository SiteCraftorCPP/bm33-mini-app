import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import TelegramIdentity, current_user
from app.api.routes import router
from app.db import Base, get_db
from app.models import Order, OrderItem, Product, Variant


class FakeTelegram:
    def __init__(self) -> None:
        self.updates: list[tuple[int, str]] = []

    async def notify_order(self, order_id: int) -> None:
        pass

    async def notify_order_updated(self, order_id: int, *, prefix: str = "") -> None:
        self.updates.append((order_id, prefix))


@pytest.fixture
def cancel_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        product = Product(id="p1", name="Stick", category="Клюшки", active=True)
        product.variants.append(
            Variant(
                id="v1",
                sheet_gid="1",
                sheet_row=2,
                stock_column=4,
                option1_value="70",
                stock=3,
                price=1000,
            )
        )
        db.add(product)
        order = Order(
            telegram_user_id=42,
            customer_name="Test",
            phone="+79990000000",
            total=1000,
            status="new",
        )
        order.items.append(
            OrderItem(
                variant_id="v1",
                product_name="Stick",
                variant_label="70",
                quantity=1,
                unit_price=1000,
            )
        )
        db.add(order)
        db.commit()
        order_id = order.id

    app = FastAPI()
    app.include_router(router)
    telegram = FakeTelegram()
    app.state.telegram = telegram
    app.state.sheets = type("S", (), {"can_write": False})()
    app.state.logger = logging.getLogger("test")
    app.state.settings = type("Settings", (), {"admin_id_set": set(), "demo_mode": False})()

    def test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[current_user] = lambda: TelegramIdentity(id=42, username="u")
    return app, sessions, order_id, telegram


def test_customer_cancel_order(cancel_api) -> None:
    app, sessions, order_id, telegram = cancel_api
    with TestClient(app) as client:
        response = client.post(f"/api/orders/{order_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert telegram.updates == [(order_id, "❌ Клиент отменил заказ")]
    with sessions() as db:
        assert db.get(Order, order_id).status == "cancelled"


def test_customer_cannot_cancel_accepted(cancel_api) -> None:
    app, sessions, order_id, _ = cancel_api
    with sessions() as db:
        db.get(Order, order_id).status = "accepted"
        db.commit()
    with TestClient(app) as client:
        response = client.post(f"/api/orders/{order_id}/cancel")
    assert response.status_code == 400
