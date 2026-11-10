from app.bot.order_messages import _client_contact_row, format_order_text, order_action_markup
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
    accepted = order_action_markup(
        1, "accepted", "https://x.ru", telegram_user_id=42, telegram_username=""
    )
    assert accepted is not None
    assert accepted.inline_keyboard[0][0].text == "💬 Написать клиенту"
    assert accepted.inline_keyboard[0][0].url == "tg://user?id=42"
    assert "Состав" in accepted.inline_keyboard[1][0].text
    assert order_action_markup(1, "cancelled", "https://x.ru") is None
    contacted = order_action_markup(
        1, "contacted", "https://x.ru", telegram_user_id=1, telegram_username="client"
    )
    assert contacted is not None
    assert len(contacted.inline_keyboard) == 4
    assert contacted.inline_keyboard[0][0].url == "https://t.me/client"
    new = order_action_markup(1, "new", "https://x.ru", telegram_user_id=5)
    assert new is not None
    assert len(new.inline_keyboard) == 4


def test_client_contact_row_username() -> None:
    row = _client_contact_row(1, "makar")
    assert row[0].url == "https://t.me/makar"
