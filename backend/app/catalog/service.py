from __future__ import annotations

import re

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.catalog.importer import (
    ImportedProduct,
    ImportedVariant,
    canonical_product_name,
    merge_stored_image_urls,
    stable_product_id,
)
from app.models import Product, Variant
from app.orders.stock import pending_quantities


CATEGORY_ORDER = (
    "Клюшки",
    "Вратарские",
    "Коньки",
    "Термобельё",
    "Перчатки",
    "Защита и одежда",
    "Баулы и рюкзаки",
)


def _prefer_merged_stick_name(existing: str, incoming: str, category: str) -> str:
    left = canonical_product_name(existing, category)
    right = canonical_product_name(incoming, category)
    if category == "Клюшки":
        if re.search(r"\spro\s*$", right, flags=re.IGNORECASE) and not re.search(
            r"\spro\s*$", left, flags=re.IGNORECASE
        ):
            return right
    return right if len(right) > len(left) else left


def _merged_products(
    imported: list[ImportedProduct],
) -> list[tuple[str, str, str, int, str, list[ImportedVariant]]]:
    grouped: dict[tuple[str, str], tuple[str, int, str, list[ImportedVariant]]] = {}
    for product in imported:
        name = canonical_product_name(product.name, product.category)
        product_id = stable_product_id(product.category, product.name)
        key = (product.category, product_id)
        if key not in grouped:
            grouped[key] = (name, product.sort_order, product.image_url, [])
        else:
            prev_name, sort_order, image_url, variants = grouped[key]
            name = _prefer_merged_stick_name(prev_name, product.name, product.category)
            image_url = merge_stored_image_urls(image_url, product.image_url)
            grouped[key] = (name, sort_order, image_url, variants)
        grouped[key][3].extend(product.variants)

    merged = []
    for (category, product_id), (name, sort_order, image_url, variants) in grouped.items():
        merged.append((product_id, name, category, sort_order, image_url, variants))
    return sorted(merged, key=lambda item: item[3])


def sync_catalog(db: Session, imported: list[ImportedProduct]) -> list[str]:
    restocked: list[str] = []
    seen_variants: set[str] = set()

    db.execute(update(Product).values(active=False))
    for product_id, name, category, sort_order, image_url, source_variants in _merged_products(imported):
        product = db.get(Product, product_id)
        if product is None:
            product = Product(id=product_id, name=name, category=category)
            db.add(product)
        product.name = name
        product.category = category
        product.sort_order = sort_order
        product.active = True
        product.image_url = image_url

        for source_variant in source_variants:
            seen_variants.add(source_variant.id)
            variant = db.get(Variant, source_variant.id)
            if variant is None:
                variant = Variant(id=source_variant.id, product_id=product_id)
                db.add(variant)
                old_stock = 0
            else:
                old_stock = variant.stock
            variant.product_id = product_id
            variant.sheet_gid = source_variant.sheet_gid
            variant.sheet_row = source_variant.sheet_row
            variant.stock_column = source_variant.stock_column
            variant.option1_name = source_variant.option1_name
            variant.option1_value = source_variant.option1_value
            variant.option2_name = source_variant.option2_name
            variant.option2_value = source_variant.option2_value
            variant.side = source_variant.side
            variant.stock = source_variant.stock
            variant.price = source_variant.price
            if old_stock == 0 and source_variant.stock > 0:
                restocked.append(variant.id)

    if seen_variants:
        db.execute(delete(Variant).where(Variant.id.not_in(seen_variants)))
    db.commit()
    return restocked


def public_image_url(product_id: str, stored: str) -> str:
    if not (stored or "").strip():
        return ""
    return f"/api/catalog/image/{product_id}"


def catalog_payload(db: Session) -> dict:
    reserved = pending_quantities(db)
    products = db.scalars(
        select(Product)
        .where(Product.active.is_(True))
        .options(selectinload(Product.variants))
        .order_by(Product.sort_order, Product.name)
    ).all()

    category_counts = {category: 0 for category in CATEGORY_ORDER}
    payload_products = []
    for product in products:
        category_counts[product.category] = category_counts.get(product.category, 0) + 1
        variant_stocks = [
            max(variant.stock - reserved.get(variant.id, 0), 0) for variant in product.variants
        ]
        available = sum(variant_stocks)
        prices = [variant.price for variant in product.variants if variant.price > 0]
        payload_products.append(
            {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "description": product.description,
                "imageUrl": public_image_url(product.id, product.image_url),
                "stock": available,
                "minPrice": min(prices) if prices else 0,
                "variants": [
                    {
                        "id": variant.id,
                        "option1Name": variant.option1_name,
                        "option1Value": variant.option1_value,
                        "option2Name": variant.option2_name,
                        "option2Value": variant.option2_value,
                        "side": variant.side,
                        "label": variant.label,
                        "stock": max(variant.stock - reserved.get(variant.id, 0), 0),
                        "price": variant.price,
                    }
                    for variant in product.variants
                ],
            }
        )

    return {
        "categories": [
            {"id": category, "name": category, "count": category_counts.get(category, 0)}
            for category in CATEGORY_ORDER
        ],
        "products": payload_products,
    }
