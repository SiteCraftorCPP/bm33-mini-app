from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.catalog.importer import (
    ImportedProduct,
    ImportedVariant,
    canonical_product_name,
    stable_product_id,
)
from app.models import Product, Variant


CATEGORY_ORDER = (
    "Клюшки",
    "Вратарские",
    "Коньки",
    "Термобельё",
    "Перчатки",
    "Защита и одежда",
    "Баулы и рюкзаки",
)


def _merged_products(imported: list[ImportedProduct]) -> list[tuple[str, str, str, int, list[ImportedVariant]]]:
    grouped: dict[tuple[str, str], tuple[str, int, list[ImportedVariant]]] = {}
    for product in imported:
        name = canonical_product_name(product.name, product.category)
        product_id = stable_product_id(product.category, name)
        key = (product.category, product_id)
        if key not in grouped:
            grouped[key] = (name, product.sort_order, [])
        grouped[key][2].extend(product.variants)

    merged = []
    for (category, product_id), (name, sort_order, variants) in grouped.items():
        merged.append((product_id, name, category, sort_order, variants))
    return sorted(merged, key=lambda item: item[3])


def sync_catalog(db: Session, imported: list[ImportedProduct]) -> list[str]:
    restocked: list[str] = []
    seen_variants: set[str] = set()

    db.execute(update(Product).values(active=False))
    for product_id, name, category, sort_order, source_variants in _merged_products(imported):
        product = db.get(Product, product_id)
        if product is None:
            product = Product(id=product_id, name=name, category=category)
            db.add(product)
        product.name = name
        product.category = category
        product.sort_order = sort_order
        product.active = True

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


def catalog_payload(db: Session) -> dict:
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
        available = sum(variant.stock for variant in product.variants)
        prices = [variant.price for variant in product.variants if variant.price > 0]
        payload_products.append(
            {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "description": product.description,
                "imageUrl": product.image_url,
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
                        "stock": variant.stock,
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
