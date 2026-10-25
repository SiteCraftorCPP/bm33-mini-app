from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./ches_hockey.sqlite3"
    frontend_url: str = "http://localhost:5173"
    public_webapp_url: str = "http://localhost:5173"
    demo_mode: bool = True

    bot_token: str = ""
    admin_ids: str = ""
    support_chat_id: str = ""
    manager_telegram_username: str = ""
    run_bot: bool = False

    google_sheet_id: str = "1Jvgo--zRkIQsdl5X1JWGeGsRQybH1r2XO84955qrtPY"
    google_service_account_file: str = ""
    sheets_sync_interval_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[2] / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admin_id_set(self) -> set[int]:
        return {
            int(value.strip())
            for value in self.admin_ids.replace(";", ",").split(",")
            if value.strip().lstrip("-").isdigit()
        }

    @property
    def support_chat_id_int(self) -> int | None:
        value = self.support_chat_id.strip()
        return int(value) if value.lstrip("-").isdigit() else None

    @property
    def manager_telegram_url(self) -> str:
        username = self.manager_telegram_username.strip().lstrip("@")
        return f"https://t.me/{username}" if username else ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
