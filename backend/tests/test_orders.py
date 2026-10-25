import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import TelegramIdentity, current_user
from app.api.routes import router
from app.db import Base, get_db
from app.integrations.google_sheets import SheetsError, StockUpdate
from app.models import Order, Product, Variant
from app.orders.stock import fulfill_accepted_order


class FakeTelegram:
    def __init__(self) -> None:
        self.orders: list[int] = []

    async def notify_order(self, order_id: int) -> None:
        self.orders.append(order_id)


class FakeSheets:
    can_write = False

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.updates: list[StockUpdate] = []

    async def update_stocks(self, updates):
        if self.fail:
            raise SheetsError("write failed")
        self.updates = updates


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        product = Product(id="product-1", name="Bauer Fuse", category="Клюшки", active=True)
        product.variants.append(
            Variant(
                id="variant-1",
                sheet_gid="367022394",
                sheet_row=3,
                stock_column=4,
                option1_name="Флекс",
                option1_value="70",
                option2_name="Загиб",
                option2_value="92",
                side="L",
                stock=2,
                price=7500,
            )
        )
        db.add(product)
        db.commit()

    app = FastAPI()
    app.include_router(router)
    app.state.sheets = FakeSheets()
    app.state.telegram = FakeTelegram()
    app.state.logger = logging.getLogger("test")
    app.state.settings = type("Settings", (), {"admin_id_set": set(), "demo_mode": True})()

    def test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[current_user] = lambda: TelegramIdentity(id=42, username="player")
    return app, sessions


def order_payload(quantity: int) -> dict:
    return {
        "items": [{"variantId": "variant-1", "quantity": quantity}],
        "customerName": "Иван Игрок",
        "phone": "+79990000000",
        "city": "Москва",
        "delivery": "СДЭК",
        "comment": "",
    }


def test_order_reserves_stock_without_sheet_write(api) -> None:
    app, sessions = api
    with TestClient(app) as client:
        response = client.post("/api/orders", json=order_payload(2))

    assert response.status_code == 201
    assert response.json()["total"] == 15000
    assert app.state.telegram.orders == [response.json()["id"]]
    assert app.state.sheets.updates == []
    with sessions() as db:
        assert db.get(Variant, "variant-1").stock == 2


@pytest.mark.asyncio
async def test_accept_fulfills_sheet_and_local_stock(api) -> None:
    app, sessions = api
    with TestClient(app) as client:
        response = client.post("/api/orders", json=order_payload(2))
    order_id = response.json()["id"]

    with sessions() as db:
        await fulfill_accepted_order(db, app.state.sheets, order_id)
        order = db.get(Order, order_id)
        order.status = "accepted"
        db.commit()

    assert len(app.state.sheets.updates) == 1
    update = app.state.sheets.updates[0]
    assert update.expected_stock == 2
    assert update.new_stock == 0
    with sessions() as db:
        assert db.get(Variant, "variant-1").stock == 0


def test_order_cannot_exceed_stock(api) -> None:
    app, sessions = api
    with TestClient(app) as client:
        response = client.post("/api/orders", json=order_payload(3))

    assert response.status_code == 409
    with sessions() as db:
        assert db.get(Variant, "variant-1").stock == 2


@pytest.mark.asyncio
async def test_sheet_failure_on_accept_keeps_local_stock(api) -> None:
    app, sessions = api
    with TestClient(app) as client:
        order_id = client.post("/api/orders", json=order_payload(1)).json()["id"]
    app.state.sheets = FakeSheets(fail=True)
    with pytest.raises(SheetsError):
        with sessions() as db:
            await fulfill_accepted_order(db, app.state.sheets, order_id)
    with sessions() as db:
        assert db.get(Variant, "variant-1").stock == 2


def test_browser_demo_order_does_not_write_real_sheet(api) -> None:
    app, _ = api
    app.dependency_overrides[current_user] = lambda: TelegramIdentity(
        id=100001,
        username="demo",
        is_demo=True,
    )
    with TestClient(app) as client:
        response = client.post("/api/orders", json=order_payload(1))

    assert response.status_code == 201
    assert app.state.sheets.updates == []
