from io import BytesIO
from pathlib import Path

from PIL import Image

from app.catalog.image_cache import crop_product_card_image, write_cached
from app.config import Settings


def test_crop_product_card_image_same_output_size() -> None:
    narrow = Image.new("RGB", (723, 1280), color=(200, 40, 40))
    wide = Image.new("RGB", (806, 1280), color=(40, 40, 200))
    for im in (narrow, wide):
        buf = BytesIO()
        im.save(buf, format="JPEG")
        body, mime = crop_product_card_image(buf.getvalue(), "image/jpeg")
        assert mime == "image/jpeg"
        assert Image.open(BytesIO(body)).size == (806, 1007)


def test_write_cached_applies_crop(tmp_path: Path) -> None:
    settings = Settings(catalog_image_dir=str(tmp_path), demo_mode=True)
    im = Image.new("RGB", (500, 900), color=(10, 120, 10))
    buf = BytesIO()
    im.save(buf, format="JPEG")
    write_cached(settings, "p1", buf.getvalue(), "image/jpeg")
    from app.catalog.image_cache import read_cached

    data, _ = read_cached(settings, "p1")
    assert Image.open(BytesIO(data)).size == (806, 1007)
