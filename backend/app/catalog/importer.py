from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SheetDefinition:
    gid: str
    title: str
    category: str
    name_column: int
    option1_column: int
    option1_name: str
    option2_column: int | None
    option2_name: str
    stock_column: int
    price_column: int
    side: str = ""
    split_mixed: bool = False


SHEETS: tuple[SheetDefinition, ...] = (
    SheetDefinition("367022394", "Клюшки левые", "Клюшки", 0, 1, "Флекс", 2, "Загиб", 3, 4, "L"),
    SheetDefinition("2084297659", "Клюшки правые", "Клюшки", 0, 1, "Флекс", 2, "Загиб", 3, 4, "R"),
    SheetDefinition("740178786", "Вратарские", "Вратарские", 0, 1, "Размер", 2, "Загиб", 3, 4),
    SheetDefinition("1252639504", "Коньки Shadow", "Коньки", 0, 1, "Размер", 2, "Fit", 3, 4),
    SheetDefinition("431205108", "Термобелье", "Термобельё", 0, 1, "Размер", None, "", 2, 3),
    SheetDefinition(
        "1187117524",
        "Перчатки, защита,одежда",
        "Защита и одежда",
        0,
        1,
        "Размер",
        2,
        "Цвет",
        3,
        4,
        split_mixed=True,
    ),
    SheetDefinition("1446201361", "Баулы и рюкзаки", "Баулы и рюкзаки", 0, 1, "Размер", None, "", 2, 3),
)


@dataclass
class ImportedVariant:
    id: str
    sheet_gid: str
    sheet_row: int
    stock_column: int
    option1_name: str
    option1_value: str
    option2_name: str
    option2_value: str
    side: str
    stock: int
    price: int

    @property
    def label(self) -> str:
        return " / ".join(
            value for value in (self.option1_value, self.option2_value, self.side) if value
        ) or "Стандарт"


@dataclass
class ImportedProduct:
    id: str
    name: str
    category: str
    sort_order: int
    variants: list[ImportedVariant] = field(default_factory=list)


class CatalogDataError(ValueError):
    pass


def _identity_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    normalized = normalized.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", normalized).strip()


def canonical_product_name(name: str, category: str) -> str:
    cleaned = unicodedata.normalize("NFKC", name or "").strip()
    if category in {"Клюшки", "Вратарские"}:
        cleaned = re.sub(r"\s+\((?:левая|правая)\)\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+[LR](?=\s*(?:\(|$))", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def _product_side(name: str, default_side: str) -> str:
    if default_side:
        return default_side.upper()
    normalized = unicodedata.normalize("NFKC", name or "")
    if re.search(r"\(\s*левая\s*\)", normalized, flags=re.IGNORECASE):
        return "L"
    if re.search(r"\(\s*правая\s*\)", normalized, flags=re.IGNORECASE):
        return "R"
    match = re.search(r"\s([LR])(?=\s*(?:\(|$))", normalized, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _canonical_option(value: str, option_name: str) -> str:
    normalized = _identity_text(value)
    if re.fullmatch(r"\d+[,.]\d+", normalized):
        normalized = normalized.replace(",", ".").rstrip("0").rstrip(".")
    if _identity_text(option_name) == "загиб":
        normalized = re.sub(r"^[pр]\s*", "", normalized)
    return normalized


def _semantic_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(_identity_text(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def stable_product_id(category: str, name: str) -> str:
    return _semantic_id("product", category, canonical_product_name(name, category))


def stable_variant_id(
    *,
    category: str,
    product_name: str,
    option1_name: str,
    option1_value: str,
    option2_name: str,
    option2_value: str,
    side: str,
) -> str:
    return _semantic_id(
        "variant",
        category,
        canonical_product_name(product_name, category),
        option1_name,
        _canonical_option(option1_value, option1_name),
        option2_name,
        _canonical_option(option2_value, option2_name),
        side.upper(),
    )


def _number(value: str) -> int | None:
    cleaned = re.sub(r"[^\d,.-]", "", value or "").replace(",", ".")
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _category(definition: SheetDefinition, name: str) -> str:
    if definition.split_mixed and name.casefold().startswith("перчат"):
        return "Перчатки"
    return definition.category


def parse_sheet(csv_text: str, definition: SheetDefinition, sort_offset: int = 0) -> list[ImportedProduct]:
    rows = list(csv.reader(io.StringIO(csv_text.lstrip("\ufeff"))))
    products: list[ImportedProduct] = []
    current: ImportedProduct | None = None
    previous_name = ""
    seen_variants: dict[str, int] = {}

    for row_number, row in enumerate(rows, start=1):
        raw_name = _cell(row, definition.name_column)
        stock = _number(_cell(row, definition.stock_column))
        price = _number(_cell(row, definition.price_column))

        if raw_name.casefold() in {"название", "арт."} or stock is None or price is None:
            if raw_name and stock is None:
                previous_name = ""
                current = None
            continue

        if raw_name:
            previous_name = raw_name
            category = _category(definition, raw_name)
            current = ImportedProduct(
                id=stable_product_id(category, raw_name),
                name=raw_name,
                category=category,
                sort_order=sort_offset + len(products),
            )
            products.append(current)
        elif not previous_name or current is None:
            continue

        option1_value = _cell(row, definition.option1_column)
        option2_value = _cell(row, definition.option2_column)
        side = _product_side(previous_name, definition.side)
        variant_id = stable_variant_id(
            category=current.category,
            product_name=previous_name,
            option1_name=definition.option1_name,
            option1_value=option1_value,
            option2_name=definition.option2_name,
            option2_value=option2_value,
            side=side,
        )
        if variant_id in seen_variants:
            raise CatalogDataError(
                f"Дублирующийся вариант «{previous_name} / {option1_value} / "
                f"{option2_value} / {side}» в строках "
                f"{seen_variants[variant_id]} и {row_number} вкладки «{definition.title}»"
            )
        seen_variants[variant_id] = row_number

        current.variants.append(
            ImportedVariant(
                id=variant_id,
                sheet_gid=definition.gid,
                sheet_row=row_number,
                stock_column=definition.stock_column + 1,
                option1_name=definition.option1_name,
                option1_value=option1_value,
                option2_name=definition.option2_name,
                option2_value=option2_value,
                side=side,
                stock=max(stock, 0),
                price=max(price, 0),
            )
        )

    return [product for product in products if product.variants]


def demo_catalog() -> list[ImportedProduct]:
    samples = (
        ("demo-stick", "Bauer Fuse", "Клюшки", "Флекс", "70", "Загиб", "P92", "L", 12, 7500),
        ("demo-goalie", "Bauer Flylite", "Вратарские", "Размер", "27", "Загиб", "P31", "L", 2, 10500),
        ("demo-skates", "Bauer Shadow", "Коньки", "Размер", "8.0", "Fit", "2", "", 3, 30000),
        ("demo-base", "Термобельё CCM SR", "Термобельё", "Размер", "L", "", "", "", 14, 4500),
        ("demo-gloves", "Перчатки CCM FT8 Pro", "Перчатки", "Размер", "13", "Цвет", "Тёмно-синие", "", 4, 6500),
        ("demo-protect", "Нагрудник Bauer Hyperlite", "Защита и одежда", "Размер", "L", "", "", "", 4, 9000),
        ("demo-bag", "Баул Winloot", "Баулы и рюкзаки", "Размер", "SR", "", "", "", 3, 9500),
    )
    result: list[ImportedProduct] = []
    for order, sample in enumerate(samples):
        product_id, name, category, opt1n, opt1v, opt2n, opt2v, side, stock, price = sample
        stable_id = stable_product_id(category, name)
        result.append(
            ImportedProduct(
                id=stable_id,
                name=name,
                category=category,
                sort_order=order,
                variants=[
                    ImportedVariant(
                        id=stable_variant_id(
                            category=category,
                            product_name=name,
                            option1_name=opt1n,
                            option1_value=opt1v,
                            option2_name=opt2n,
                            option2_value=opt2v,
                            side=side,
                        ),
                        sheet_gid="demo",
                        sheet_row=order + 1,
                        stock_column=4,
                        option1_name=opt1n,
                        option1_value=opt1v,
                        option2_name=opt2n,
                        option2_value=opt2v,
                        side=side,
                        stock=stock,
                        price=price,
                    )
                ],
            )
        )
    return result
