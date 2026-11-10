from __future__ import annotations

import re

_PHONE_DIGITS = re.compile(r"\D+")


class PhoneError(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    """Россия: 11 цифр, храним как +7XXXXXXXXXX."""
    digits = _PHONE_DIGITS.sub("", (raw or "").strip())
    if not digits:
        raise PhoneError("Укажите номер телефона")
    if len(digits) == 10:
        if digits[0] == "8":
            raise PhoneError("Не хватает цифр — укажите полный номер (+7 и 10 цифр)")
        if digits[0] == "9":
            digits = "7" + digits
        else:
            raise PhoneError("Нужен российский номер (+7 …)")
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) != 11 or digits[0] != "7" or digits[1] != "9":
        raise PhoneError("Нужен полный мобильный +7 9XX XXX XX XX")
    return f"+{digits}"


def format_phone_display(phone: str) -> str:
    try:
        normalized = normalize_phone(phone)
    except PhoneError:
        return phone.strip() or "—"
    digits = normalized[1:]
    return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
