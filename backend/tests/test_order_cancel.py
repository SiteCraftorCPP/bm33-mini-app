from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Order, OrderItem, Product, Variant
from app.orders.stock import pending_quantities


def test_cancelled_order_does_not_reserve_stock() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = Product(id="p1", name="Bauer Fuse", category="Клюшки", active=True)
        product.variants.append(
            Variant(id="v1", sheet_gid="demo", sheet_row=1, stock_column=1, stock=5, price=7500)
        )
        db.add(product)
        order = Order(
            telegram_user_id=1,
            customer_name="t",
            phone="1",
            total=7500,
            status="new",
        )
        order.items.append(
            OrderItem(
                variant_id="v1",
                product_name="Bauer Fuse",
                variant_label="20 / 28 / R",
                quantity=2,
                unit_price=7500,
            )
        )
        db.add(order)
        db.commit()

        assert sum(pending_quantities(db).values()) == 2
        order.status = "cancelled"
        db.commit()
        assert sum(pending_quantities(db).values()) == 0
