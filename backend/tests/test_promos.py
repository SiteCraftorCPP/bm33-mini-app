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
from app.models import Product, PromoCode, Variant


class FakeTelegram:
    async def notify_order(self, order_id: int) -> None:
        return None


@pytest.fixture
def promo_api():
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
                sheet_gid="1",
                sheet_row=3,
                stock_column=4,
                option1_name="Флекс",
                option1_value="70",
                side="L",
                stock=5,
                price=10_000,
            )
        )
        db.add(product)
        db.add(
            PromoCode(
                code="SAVE10",
                kind="percent",
                value=10,
                max_uses=2,
                used_count=0,
                active=True,
            )
        )
        db.add(
            PromoCode(
                code="OFF500",
                kind="fixed",
                value=500,
                max_uses=None,
                used_count=0,
                active=True,
            )
        )
        db.add(
            PromoCode(
                code="DEAD",
                kind="fixed",
                value=100,
                max_uses=1,
                used_count=1,
                active=True,
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(router)
    app.state.sheets = type("S", (), {"can_write": False})()
    app.state.telegram = FakeTelegram()
    app.state.logger = logging.getLogger("test")
    app.state.settings = type("Settings", (), {"admin_id_set": {396526427}, "demo_mode": False})()

    def test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[current_user] = lambda: TelegramIdentity(id=42, username="player")
    return app, sessions


def order_payload(**extra) -> dict:
    return {
        "items": [{"variantId": "variant-1", "quantity": 1}],
        "customerName": "Иван",
        "phone": "+79990000000",
        "city": "Москва",
        "comment": "",
        **extra,
    }


def test_validate_percent_promo(promo_api) -> None:
    app, _ = promo_api
    with TestClient(app) as client:
        response = client.post("/api/promos/validate", json={"code": "save10", "subtotal": 10_000})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "SAVE10"
    assert body["discount"] == 1000
    assert body["total"] == 9000


def test_validate_rejects_exhausted(promo_api) -> None:
    app, _ = promo_api
    with TestClient(app) as client:
        response = client.post("/api/promos/validate", json={"code": "DEAD", "subtotal": 5000})
    assert response.status_code == 400


def test_order_applies_promo_and_increments_usage(promo_api) -> None:
    app, sessions = promo_api
    with TestClient(app) as client:
        response = client.post("/api/orders", json=order_payload(promoCode="OFF500"))
    assert response.status_code == 201
    assert response.json()["total"] == 9500
    with sessions() as db:
        promo = db.get(PromoCode, "OFF500")
        assert promo.used_count == 1


def test_order_rejects_invalid_promo(promo_api) -> None:
    app, _ = promo_api
    with TestClient(app) as client:
        response = client.post("/api/orders", json=order_payload(promoCode="NOPE"))
    assert response.status_code == 400


def test_admin_promo_crud(promo_api) -> None:
    app, _ = promo_api
    app.dependency_overrides[current_user] = lambda: TelegramIdentity(
        id=396526427,
        username="admin",
        is_demo=False,
    )
    with TestClient(app) as client:
        listed = client.get("/api/admin/promos")
        assert listed.status_code == 200
        assert len(listed.json()["promos"]) >= 3

        created = client.post(
            "/api/admin/promos",
            json={"code": "NEW20", "kind": "percent", "value": 20, "maxUses": 5, "note": "test"},
        )
        assert created.status_code == 201
        assert created.json()["code"] == "NEW20"

        patched = client.patch("/api/admin/promos/NEW20", json={"active": False})
        assert patched.status_code == 200
        assert patched.json()["active"] is False

        deleted = client.delete("/api/admin/promos/NEW20")
        assert deleted.status_code == 204
