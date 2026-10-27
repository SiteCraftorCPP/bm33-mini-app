from app.bot.order_messages import format_order_text, order_action_markup
from app.models import Order, OrderItem


def test_format_order_text_uses_dashes_not_bullets() -> None:
    order = Order(
        id=1,
        telegram_user_id=1,
        customer_name="тест",
        phone="+7",
        total=7500,
        status="new",
    )
    order.items.append(
        OrderItem(
            variant_id="v1",
            product_name="Bauer Fuse",
            variant_label="20 / 28 / R",
            quantity=1,
            unit_price=7500,
        )
    )
    text = format_order_text(order)
    assert "•" not in text
    assert "Bauer Fuse - 20 / 28 / R x 1" in text
    assert "—" not in text


def test_order_markup_hides_buttons_after_accept() -> None:
    assert order_action_markup(1, "accepted", "https://x.ru") is None
    assert order_action_markup(1, "cancelled", "https://x.ru") is None
    contacted = order_action_markup(1, "contacted", "https://x.ru")
    assert contacted is not None
    assert len(contacted.inline_keyboard) == 2
    new = order_action_markup(1, "new", "https://x.ru")
    assert new is not None
    assert len(new.inline_keyboard) == 2
    assert "Отменить" in new.inline_keyboard[1][0].text
