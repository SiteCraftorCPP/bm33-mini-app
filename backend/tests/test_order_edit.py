import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.integrations.google_sheets import SheetsError, StockUpdate
from app.models import Order, OrderItem, Product, Variant
from app.orders.edit import OrderEditError, change_order_item_quantity, remove_order_item
from app.orders.stock import apply_stock_delta, fulfill_accepted_order


class FakeSheets:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.updates: list[StockUpdate] = []

    async def update_stocks(self, updates):
        if self.fail:
            raise SheetsError("write failed")
        self.updates.extend(updates)


@pytest.fixture
def edit_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        product = Product(id="p1", name="Stick", category="Клюшки", active=True)
        product.variants.append(
            Variant(
                id="v1",
                sheet_gid="1",
                sheet_row=2,
                stock_column=4,
                side="L",
                option1_value="70",
                stock=10,
                price=1000,
            )
        )
        db.add(product)
        order = Order(
            telegram_user_id=1,
            customer_name="a",
            phone="1",
            status="new",
            total=3000,
        )
        order.items.append(
            OrderItem(
                variant_id="v1",
                product_name="Stick",
                variant_label="70 / L",
                quantity=3,
                unit_price=1000,
            )
        )
        db.add(order)
        db.commit()
        order_id = order.id
        item_id = order.items[0].id
    yield Session, order_id, item_id, FakeSheets()


@pytest.mark.asyncio
async def test_increase_quantity_recomputes_total(edit_db) -> None:
    Session, order_id, item_id, sheets = edit_db
    with Session() as db:
        order = await change_order_item_quantity(
            db, sheets, order_id=order_id, item_id=item_id, delta=1
        )
        assert order.total == 4000
        assert order.items[0].quantity == 4
    assert sheets.updates == []


@pytest.mark.asyncio
async def test_cannot_edit_cancelled(edit_db) -> None:
    Session, order_id, item_id, sheets = edit_db
    with Session() as db:
        db.get(Order, order_id).status = "cancelled"
        db.commit()
    with Session() as db:
        with pytest.raises(OrderEditError):
            await change_order_item_quantity(
                db, sheets, order_id=order_id, item_id=item_id, delta=1
            )


@pytest.mark.asyncio
async def test_remove_last_item_fails(edit_db) -> None:
    Session, order_id, item_id, sheets = edit_db
    with Session() as db:
        with pytest.raises(OrderEditError):
            await remove_order_item(db, sheets, order_id=order_id, item_id=item_id)


@pytest.mark.asyncio
async def test_decrease_after_accept_returns_to_sheet(edit_db) -> None:
    Session, order_id, item_id, sheets = edit_db
    with Session() as db:
        order = db.get(Order, order_id)
        order.status = "accepted"
        variant = db.get(Variant, "v1")
        variant.stock = 7
        db.commit()

    with Session() as db:
        order = await change_order_item_quantity(
            db, sheets, order_id=order_id, item_id=item_id, delta=-1
        )
        assert order.items[0].quantity == 2
        assert db.get(Variant, "v1").stock == 8

    assert len(sheets.updates) == 1
    assert sheets.updates[0].expected_stock == 7
    assert sheets.updates[0].new_stock == 8


@pytest.mark.asyncio
async def test_remove_after_accept_returns_all_units(edit_db) -> None:
    Session, order_id, item_id, sheets = edit_db
    with Session() as db:
        product = Product(id="p2", name="Stick2", category="Клюшки", active=True)
        product.variants.append(
            Variant(
                id="v2",
                sheet_gid="1",
                sheet_row=3,
                stock_column=4,
                side="R",
                option1_value="77",
                stock=5,
                price=1000,
            )
        )
        db.add(product)
        order = db.get(Order, order_id)
        order.status = "accepted"
        order.items.append(
            OrderItem(
                variant_id="v2",
                product_name="Stick2",
                variant_label="77 / R",
                quantity=2,
                unit_price=1000,
            )
        )
        db.get(Variant, "v1").stock = 7
        db.commit()
        second_id = order.items[1].id

    with Session() as db:
        await remove_order_item(db, sheets, order_id=order_id, item_id=item_id)

    assert any(u.new_stock == 10 for u in sheets.updates)


@pytest.mark.asyncio
async def test_edit_then_accept_deducts_adjusted_quantity(edit_db) -> None:
    Session, order_id, item_id, sheets = edit_db
    with Session() as db:
        await change_order_item_quantity(
            db, sheets, order_id=order_id, item_id=item_id, delta=-1
        )

    sheets.updates.clear()
    with Session() as db:
        await fulfill_accepted_order(db, sheets, order_id)
        db.commit()

    assert len(sheets.updates) == 1
    assert sheets.updates[0].expected_stock == 10
    assert sheets.updates[0].new_stock == 8
    with Session() as db:
        assert db.get(Variant, "v1").stock == 8


@pytest.mark.asyncio
async def test_apply_stock_delta_rejects_negative_stock(edit_db) -> None:
    Session, _, _, sheets = edit_db
    with Session() as db:
        variant = db.get(Variant, "v1")
        variant.stock = 0
        with pytest.raises(SheetsError):
            await apply_stock_delta(db, sheets, variant, -1)
