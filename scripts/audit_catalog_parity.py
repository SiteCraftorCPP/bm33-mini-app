#!/usr/bin/env python3
"""Compare Google Sheets import vs SQLite catalog (run on VPS with sourced env)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

def _backend_root() -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "backend",
        Path("/opt/bm33-mini-app/backend"),
    ]
    for path in candidates:
        if (path / "app").is_dir():
            return path
    raise SystemExit("backend package not found")


sys.path.insert(0, str(_backend_root()))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.catalog.importer import SHEETS
from app.catalog.service import catalog_payload, pending_quantities
from app.config import get_settings
from app.integrations.google_sheets import GoogleSheets
from app.models import Variant


async def main() -> int:
    settings = get_settings()
    sheets = GoogleSheets(settings)
    imported = await sheets.fetch_catalog(force=True)

    imp_by_id: dict[str, tuple] = {}
    for product in imported:
        for v in product.variants:
            imp_by_id[v.id] = (
                product.category,
                product.name,
                v.stock,
                v.price,
            )

    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        db_variants = {row.id: row for row in db.scalars(select(Variant)).all()}
        reserved = pending_quantities(db)
        api = catalog_payload(db)

    api_by_id: dict[str, tuple[int, int]] = {}
    for product in api["products"]:
        for v in product["variants"]:
            api_by_id[v["id"]] = (v["stock"], v["price"])

    missing_in_db = sorted(set(imp_by_id) - set(db_variants))
    extra_in_db = sorted(set(db_variants) - set(imp_by_id))
    mismatches: list[str] = []

    for vid, imp in imp_by_id.items():
        row = db_variants.get(vid)
        if row is None:
            continue
        if row.stock != imp[2] or row.price != imp[3]:
            mismatches.append(
                f"{vid}: db={row.stock}/{row.price} sheet={imp[2]}/{imp[3]} name={imp[1][:50]}"
            )
        api_stock, api_price = api_by_id.get(vid, (-1, -1))
        expected_api_stock = max(imp[2] - reserved.get(vid, 0), 0)
        if api_stock != expected_api_stock or api_price != imp[3]:
            mismatches.append(
                f"{vid}: api stock={api_stock} want={expected_api_stock} "
                f"(sheet={imp[2]} reserved={reserved.get(vid, 0)})"
            )

    print("SHEETS_TABS", len(SHEETS))
    print("IMPORT_VARIANTS", len(imp_by_id))
    print("DB_VARIANTS", len(db_variants))
    print("API_PRODUCTS", len(api["products"]))
    print("MISSING_IN_DB", len(missing_in_db))
    print("EXTRA_IN_DB", len(extra_in_db))
    print("FIELD_MISMATCHES", len(mismatches))
    print("PENDING_RESERVED_UNITS", sum(reserved.values()))

    for line in mismatches[:20]:
        print("MISMATCH", line)

    summary = {
        "ok": not missing_in_db and not extra_in_db and not mismatches,
        "import_variants": len(imp_by_id),
        "db_variants": len(db_variants),
        "missing_in_db": len(missing_in_db),
        "extra_in_db": len(extra_in_db),
        "mismatches": len(mismatches),
        "reserved_units": int(sum(reserved.values())),
    }
    print("JSON", json.dumps(summary, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
