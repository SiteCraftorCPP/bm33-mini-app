from app.catalog.importer import normalize_image_url, parse_sheet, SHEETS


def test_normalize_google_drive_file_link() -> None:
    url = normalize_image_url("https://drive.google.com/file/d/abc123XYZ/view?usp=sharing")
    assert url == "https://drive.google.com/uc?export=download&id=abc123XYZ"


def test_parse_product_image_from_extra_column() -> None:
    csv_text = """Название,Флекс,Загиб,Наличие,Цена,Фото
Bauer Fuse L,70,92,2,7500,https://drive.google.com/file/d/photo1/view
"""
    products = parse_sheet(csv_text, SHEETS[0])
    assert "id=photo1" in products[0].image_url
    assert "export=download" in products[0].image_url
