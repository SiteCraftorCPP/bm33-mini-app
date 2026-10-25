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
from app.catalog.importer import demo_catalog


class FakeSheets:
    can_write = True

    async def fetch_catalog(self, *, force: bool = False):
        return demo_catalog()


@pytest.fixture
def admin_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    app = FastAPI()
    app.include_router(router)
    app.state.sheets = FakeSheets()
    app.state.telegram = type("T", (), {"notify_restock": lambda *a, **k: None})()
    app.state.logger = logging.getLogger("test")
    app.state.settings = type("Settings", (), {"admin_id_set": {396526427}, "demo_mode": False})()

    def test_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[current_user] = lambda: TelegramIdentity(
        id=396526427, username="admin", is_demo=False
    )
    return app, sessions


def test_admin_catalog_sync_ok(admin_api) -> None:
    app, _ = admin_api
    with TestClient(app) as client:
        response = client.post("/api/admin/catalog/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["products"] >= 1


def test_admin_catalog_sync_forbidden(admin_api) -> None:
    app, _ = admin_api
    app.state.settings = type("Settings", (), {"admin_id_set": {1}, "demo_mode": False})()
    with TestClient(app) as client:
        response = client.post("/api/admin/catalog/sync")
    assert response.status_code == 403
