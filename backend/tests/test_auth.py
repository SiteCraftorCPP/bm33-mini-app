import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.api.auth import validate_init_data


def signed_init_data(token: str, user_id: int, auth_date: int | None = None) -> str:
    values = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH-test",
        "user": json.dumps({"id": user_id, "first_name": "Иван", "username": "ivan"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_telegram_init_data() -> None:
    identity = validate_init_data(signed_init_data("123:test-token", 42), "123:test-token")

    assert identity.id == 42
    assert identity.username == "ivan"


def test_tampered_telegram_init_data_is_rejected() -> None:
    data = signed_init_data("123:test-token", 42).replace("ivan", "hacker")

    with pytest.raises(ValueError, match="подпись"):
        validate_init_data(data, "123:test-token")


def test_expired_telegram_init_data_is_rejected() -> None:
    data = signed_init_data("123:test-token", 42, auth_date=int(time.time()) - 100_000)

    with pytest.raises(ValueError, match="устарели"):
        validate_init_data(data, "123:test-token")
