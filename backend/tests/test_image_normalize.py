from io import BytesIO
from pathlib import Path

from PIL import Image

from app.catalog.image_cache import normalize_product_image, write_cached
from app.config import Settings


def test_normalize_product_image_letterboxes_to_4x3() -> None:
    tall = Image.new("RGB", (400, 1200), color=(200, 40, 40))
    buf = BytesIO()
    tall.save(buf, format="JPEG")
    body, mime = normalize_product_image(buf.getvalue(), "image/jpeg")
    assert mime == "image/jpeg"
    out = Image.open(BytesIO(body))
    assert out.size == (1200, 900)


def test_write_cached_normalizes(tmp_path: Path) -> None:
    settings = Settings(catalog_image_dir=str(tmp_path), demo_mode=True)
    wide = Image.new("RGB", (1600, 400), color=(40, 40, 200))
    buf = BytesIO()
    wide.save(buf, format="JPEG")
    write_cached(settings, "p-wide", buf.getvalue(), "image/jpeg")
    from app.catalog.image_cache import read_cached

    cached, mime = read_cached(settings, "p-wide")
    assert mime == "image/jpeg"
    assert Image.open(BytesIO(cached)).size == (1200, 900)
