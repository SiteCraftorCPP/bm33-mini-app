from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.catalog.importer import SHEETS, parse_sheet
from app.catalog.service import catalog_payload, sync_catalog
from app.db import Base
from app.models import Variant


def test_stick_rows_continue_product_and_keep_zero_stock() -> None:
    csv_text = """ЛЕВЫЕ,,,,
Название,Флекс,Загиб,Наличие,Цена
Bauer Fuse L,70,92,2,7500
,77,28,0,7500
"""
    products = parse_sheet(csv_text, SHEETS[0])

    assert len(products) == 1
    assert products[0].name == "Bauer Fuse L"
    assert [variant.stock for variant in products[0].variants] == [2, 0]
    assert products[0].variants[1].side == "L"
    assert products[0].variants[1].sheet_row == 4


def test_mixed_sheet_splits_gloves_from_protection() -> None:
    csv_text = """,Размер,Цвет,Наличие,Цена
Перчатки CCM,13,Синие,2,6500
Нагрудник Bauer,L,,3,9000
"""
    products = parse_sheet(csv_text, SHEETS[5])

    assert [product.category for product in products] == ["Перчатки", "Защита и одежда"]


def test_left_and_right_sticks_merge_into_one_product() -> None:
    left = parse_sheet(
        "Название,Флекс,Загиб,Наличие,Цена\nBauer Fuse L,70,92,2,7500\n",
        SHEETS[0],
    )
    right = parse_sheet(
        "Название,Флекс,Загиб,Наличие,Цена\nBauer Fuse R,70,92,3,7500\n",
        SHEETS[1],
        10,
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        sync_catalog(db, left + right)
        payload = catalog_payload(db)
        sticks = [product for product in payload["products"] if product["category"] == "Клюшки"]
        sides = {variant["side"] for variant in sticks[0]["variants"]}
        variants = db.scalars(select(Variant)).all()

    assert len(sticks) == 1
    assert sticks[0]["name"] == "Bauer Fuse"
    assert sides == {"L", "R"}
    assert len(variants) == 2


def test_variant_identity_survives_inserted_rows() -> None:
    original = parse_sheet(
        "Название,Флекс,Загиб,Наличие,Цена\nBauer Fuse L,70,92,2,7500\n",
        SHEETS[0],
    )
    shifted = parse_sheet(
        "ЛЕВЫЕ,,,,\nНазвание,Флекс,Загиб,Наличие,Цена\n\nBauer Fuse L,70,92,5,7500\n",
        SHEETS[0],
    )

    assert original[0].id == shifted[0].id
    assert original[0].variants[0].id == shifted[0].variants[0].id
    assert original[0].variants[0].sheet_row == 2
    assert shifted[0].variants[0].sheet_row == 4


def test_sync_updates_current_row_and_removes_deleted_variation() -> None:
    first = parse_sheet(
        "Название,Флекс,Загиб,Наличие,Цена\n"
        "Bauer Fuse L,70,92,2,7500\n"
        ",77,28,1,7500\n",
        SHEETS[0],
    )
    changed = parse_sheet(
        "ЛЕВЫЕ,,,,\n"
        "Название,Флекс,Загиб,Наличие,Цена\n"
        "Bauer Fuse L,70,92,4,7500\n"
        ",87,28,3,7500\n",
        SHEETS[0],
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        sync_catalog(db, first)
        stable_id = first[0].variants[0].id
        removed_id = first[0].variants[1].id
        sync_catalog(db, changed)
        stable = db.get(Variant, stable_id)

        assert stable is not None
        assert stable.sheet_row == 3
        assert stable.stock == 4
        assert db.get(Variant, removed_id) is None
        assert db.get(Variant, changed[0].variants[1].id) is not None


def test_goalie_side_is_part_of_variant_identity() -> None:
    products = parse_sheet(
        "Название,Размер,Загиб,Наличие,Цена\n"
        "Bauer Flylite L (левая),27,31,2,10500\n"
        "Bauer Flylite R (правая),27,31,1,10500\n",
        SHEETS[2],
    )

    assert products[0].id == products[1].id
    assert products[0].variants[0].id != products[1].variants[0].id
    assert {products[0].variants[0].side, products[1].variants[0].side} == {"L", "R"}
