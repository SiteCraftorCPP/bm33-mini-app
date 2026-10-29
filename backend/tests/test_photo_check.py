from app.catalog.photo_check import catalog_photo_warnings, photo_fetch_problem


def test_photo_fetch_problem_detects_missing() -> None:
    import httpx

    with httpx.Client() as client:
        assert photo_fetch_problem("", client) == "нет ссылки в колонке «Фото»"


def test_catalog_photo_warnings_empty_when_no_images(monkeypatch) -> None:
    from app.catalog.importer import ImportedProduct

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url: str, **kwargs):
            class R:
                status_code = 200
                headers = {"content-type": "image/jpeg"}
                content = b"\xff\xd8\xff" + b"\x00" * 600

                def raise_for_status(self):
                    return None

            return R()

    monkeypatch.setattr("app.catalog.photo_check.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.catalog.photo_check._merged_products",
        lambda imported: [
            ("id1", "Test", "Клюшки", 0, "https://disk.yandex.ru/i/x", []),
        ],
    )
    monkeypatch.setattr(
        "app.catalog.photo_check.catalog_image_fetch_urls",
        lambda stored: ["https://cdn.example/x.jpg"],
    )
    warnings = catalog_photo_warnings([])
    assert warnings == []
