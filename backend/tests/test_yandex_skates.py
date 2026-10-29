from app.catalog.importer import SHEETS, catalog_image_fetch_urls, parse_sheet
from app.catalog.service import sync_catalog
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Product


def test_catalog_image_fetch_urls_resolves_yandex(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str, **kwargs):
            class ApiResponse:
                status_code = 200

                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return {"href": "https://cdn.example/photo.jpg"}

            class ImgResponse:
                status_code = 200
                headers = {"content-type": "image/jpeg"}
                content = b"\xff\xd8\xff" + b"\x00" * 600

                def raise_for_status(self) -> None:
                    return None

            if "cloud-api.yandex.net" in url:
                return ApiResponse()
            return ImgResponse()

    monkeypatch.setattr("app.catalog.importer.httpx.Client", FakeClient)
    urls = catalog_image_fetch_urls("https://disk.yandex.ru/i/abc123")
    assert urls == ["https://cdn.example/photo.jpg"]


def test_skates_sheet_merges_sizes_into_one_product() -> None:
    csv_text = """Арт.,Размер,Фит,Наличие,Цена,Фото
Размер 4.5 Fit 3,"4,5",3,0,28500,https://disk.yandex.ru/i/test1
Размер 5.0 Fit 2,"5,0",2,6,28500,https://disk.yandex.ru/i/test1
"""
    products = parse_sheet(csv_text, SHEETS[3])
    assert len(products) == 1
    assert products[0].name == "Коньки Shadow"
    assert len(products[0].variants) == 2

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        sync_catalog(db, products)
        product = db.get(Product, products[0].id)
        assert product is not None
        assert "disk.yandex.ru" in product.image_url
