import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Order, OrderItem, Product, Variant
from app.orders.edit import OrderEditError, change_order_item_quantity, remove_order_item


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
                sheet_gid="demo",
                sheet_row=1,
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
                variant_label="L",
                quantity=3,
                unit_price=1000,
            )
        )
        db.add(order)
        db.commit()
        order_id = order.id
        item_id = order.items[0].id
    yield Session, order_id, item_id


def test_increase_quantity_recomputes_total(edit_db) -> None:
    Session, order_id, item_id = edit_db
    with Session() as db:
        order = change_order_item_quantity(db, order_id=order_id, item_id=item_id, delta=1)
        assert order.total == 4000
        assert order.items[0].quantity == 4


def test_cannot_edit_accepted(edit_db) -> None:
    Session, order_id, item_id = edit_db
    with Session() as db:
        db.get(Order, order_id).status = "accepted"
        db.commit()
    with Session() as db:
        with pytest.raises(OrderEditError):
            change_order_item_quantity(db, order_id=order_id, item_id=item_id, delta=1)


def test_remove_last_item_fails(edit_db) -> None:
    Session, order_id, item_id = edit_db
    with Session() as db:
        with pytest.raises(OrderEditError):
            remove_order_item(db, order_id=order_id, item_id=item_id)
