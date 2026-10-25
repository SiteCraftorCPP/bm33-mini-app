from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router


def test_public_config_exposes_manager_url() -> None:
    app = FastAPI()
    app.include_router(router)
    app.state.settings = type(
        "S",
        (),
        {"manager_telegram_url": "https://t.me/Makar2903"},
    )()
    with TestClient(app) as client:
        response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {"managerTelegramUrl": "https://t.me/Makar2903"}
