from app.bot.order_messages import (
    EDIT_PAGE_SIZE,
    format_order_edit_header,
    order_action_markup,
    order_edit_list_markup,
)
from app.models import Order, OrderItem


def _order_with_items(count: int) -> Order:
    order = Order(
        id=99,
        telegram_user_id=1,
        customer_name="t",
        phone="1",
        status="new",
        total=1000 * count,
    )
    for index in range(count):
        order.items.append(
            OrderItem(
                variant_id=f"v{index}",
                product_name=f"Product {index}",
                variant_label=f"opt {index}",
                quantity=1,
                unit_price=1000,
            )
        )
    return order


def test_edit_list_pagination() -> None:
    order = _order_with_items(EDIT_PAGE_SIZE + 3)
    page0 = order_edit_list_markup(order, page=0)
    page1 = order_edit_list_markup(order, page=1)
    assert len(page0.inline_keyboard) == EDIT_PAGE_SIZE + 2  # nav + done
    assert any("▶️" in (btn.text or "") for row in page0.inline_keyboard for btn in row)
    assert len(page1.inline_keyboard) == 3 + 2  # 3 items + nav + done
    text = format_order_edit_header(order, page=1)
    assert "Стр. 2/2" in text


def test_accepted_order_still_has_edit_button() -> None:
    markup = order_action_markup(1, "accepted", "https://x.ru")
    assert markup is not None
    assert markup.inline_keyboard[0][0].text == "✏️ Состав"
