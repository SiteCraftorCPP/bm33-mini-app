import pytest

from app.phone import PhoneError, format_phone_display, normalize_phone


def test_normalize_russian_mobile() -> None:
    assert normalize_phone("+7 (999) 123-45-67") == "+79991234567"
    assert normalize_phone("89991234567") == "+79991234567"
    assert normalize_phone("9991234567") == "+79991234567"


def test_rejects_short_number() -> None:
    with pytest.raises(PhoneError):
        normalize_phone("8927784060")


def test_format_display() -> None:
    assert format_phone_display("+79991234567") == "+7 999 123-45-67"
