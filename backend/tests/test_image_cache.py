from pathlib import Path

from app.catalog.image_cache import fetch_image_bytes, refresh_product_image_cache, write_cached
from app.config import Settings


def test_refresh_keeps_cache_when_fetch_fails(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(catalog_image_dir=str(tmp_path), demo_mode=True)
    write_cached(settings, "p1", b"\xff\xd8\xff" + b"\x00" * 600, "image/jpeg")
    monkeypatch.setattr(
        "app.catalog.image_cache.fetch_image_bytes",
        lambda stored, s: None,
    )
    assert refresh_product_image_cache(settings, "p1", "https://broken.example/x") is True


def test_fetch_image_bytes_yandex(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str, **kwargs):
            class Api:
                status_code = 200

                def raise_for_status(self):
                    return None

                def json(self):
                    return {"href": "https://cdn.example/photo.jpg"}

            class Img:
                status_code = 200
                headers = {"content-type": "image/jpeg"}
                content = b"\xff\xd8\xff" + b"\x00" * 800

                def raise_for_status(self):
                    return None

            if "cloud-api.yandex.net" in url:
                return Api()
            return Img()

    monkeypatch.setattr("app.catalog.image_cache.httpx.Client", FakeClient)
    settings = Settings(demo_mode=True)
    body, mime = fetch_image_bytes("https://disk.yandex.ru/i/abc", settings)
    assert mime == "image/jpeg"
    assert body[:3] == b"\xff\xd8\xff"
