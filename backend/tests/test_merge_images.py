from app.catalog.importer import merge_stored_image_urls, normalize_image_url, parse_sheet, SHEETS
from app.catalog.service import sync_catalog
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Product


def test_merge_stored_image_urls_keeps_both_sides() -> None:
    left = normalize_image_url("https://drive.google.com/file/d/aaa/view")
    right = normalize_image_url("https://drive.google.com/file/d/bbb/view")
    merged = merge_stored_image_urls(left, right)
    assert "id=aaa" in merged
    assert "id=bbb" in merged
    assert "|" in merged


def test_left_and_right_photos_merge_on_sync() -> None:
    left = parse_sheet(
        "Название,Флекс,Загиб,Наличие,Цена,Фото\n"
        "CCM Recharge Pro L,70,28,1,7500,https://drive.google.com/file/d/badleft/view\n",
        SHEETS[0],
    )
    right = parse_sheet(
        "Название,Флекс,Загиб,Наличие,Цена,Фото\n"
        "CCM Recharge Pro R,70,28,1,7500,https://drive.google.com/file/d/goodright/view\n",
        SHEETS[1],
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        sync_catalog(db, left + right)
        product = db.get(Product, left[0].id)
        assert product is not None
        assert "id=badleft" in product.image_url
        assert "id=goodright" in product.image_url
