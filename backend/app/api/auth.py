from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, Request

from app.config import get_settings


@dataclass(frozen=True)
class TelegramIdentity:
    id: int
    username: str = ""
    first_name: str = ""
    is_demo: bool = False


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86_400) -> TelegramIdentity:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    supplied_hash = values.pop("hash", "")
    if not supplied_hash:
        raise ValueError("hash отсутствует")

    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash):
        raise ValueError("подпись Telegram не совпала")

    auth_date = int(values.get("auth_date", "0"))
    if not auth_date or time.time() - auth_date > max_age_seconds:
        raise ValueError("данные Telegram устарели")

    user = json.loads(values.get("user", "{}"))
    if not isinstance(user.get("id"), int):
        raise ValueError("пользователь Telegram отсутствует")
    return TelegramIdentity(
        id=user["id"],
        username=str(user.get("username", "")),
        first_name=str(user.get("first_name", "")),
    )


def current_user(
    x_telegram_init_data: str = Header(default=""),
    x_demo_user_id: str = Header(default=""),
) -> TelegramIdentity:
    settings = get_settings()
    if x_telegram_init_data and settings.bot_token:
        try:
            return validate_init_data(x_telegram_init_data, settings.bot_token)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=401, detail=f"Неверные данные Telegram: {exc}") from exc

    if settings.demo_mode:
        demo_id = int(x_demo_user_id) if x_demo_user_id.isdigit() else 100001
        return TelegramIdentity(id=demo_id, username="demo", first_name="Игрок", is_demo=True)
    raise HTTPException(status_code=401, detail="Откройте магазин внутри Telegram")


def require_admin(
    request: Request,
    user: TelegramIdentity = Depends(current_user),
) -> TelegramIdentity:
    settings = request.app.state.settings
    if user.id not in settings.admin_id_set:
        raise HTTPException(status_code=403, detail="Только для администратора")
    return user
