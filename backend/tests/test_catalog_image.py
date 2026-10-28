from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import router
from app.db import Base, get_db
from app.models import Product


def test_catalog_image_proxy(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        db.add(
            Product(
                id="stick-1",
                name="Bauer Fuse",
                category="Клюшки",
                active=True,
                image_url="https://drive.google.com/uc?export=view&id=abc",
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(router)

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "image/jpeg"}
        content = b"\xff\xd8\xff"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str):
            assert "abc" in url
            return FakeResponse()

    monkeypatch.setattr("app.api.routes.httpx.Client", FakeClient)

    with TestClient(app) as client:
        catalog = client.get("/api/catalog")
        assert catalog.status_code == 200
        product = catalog.json()["products"][0]
        assert product["imageUrl"] == "/api/catalog/image/stick-1"

        image = client.get("/api/catalog/image/stick-1")
        assert image.status_code == 200
        assert image.headers["content-type"].startswith("image/")
        assert image.content[:3] == b"\xff\xd8\xff"
