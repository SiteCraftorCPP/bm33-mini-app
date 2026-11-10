#!/usr/bin/env python3
"""Compare live sheet photo cells vs DB vs cache. Does not write."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = r"""
import asyncio
import re
from app.config import get_settings
from app.db import SessionLocal
from app.models import Product
from app.catalog.image_cache import read_cached
from app.catalog.importer import SHEETS
from app.catalog.service import _merged_products
from app.integrations.google_sheets import GoogleSheets
from sqlalchemy import select

URL_RE = re.compile(r"https?://|drive\.google|disk\.yandex|yadi\.sk|HYPERLINK|IMAGE\s*\(", re.I)

async def main():
    settings = get_settings()
    gs = GoogleSheets(settings)
    imported = await gs.fetch_catalog(force=True)
    merged = _merged_products(imported)
    print("merged", len(merged))
    with SessionLocal() as db:
        db_rows = list(db.scalars(select(Product).where(Product.active.is_(True))).all())
        by_name = {p.name: p for p in db_rows}
        sheet_empty = 0
        gap = 0
        for pid, name, cat, _so, image, _vars in merged:
            sheet_has = bool((image or "").strip())
            dbp = by_name.get(name)
            db_url = ((dbp.image_url if dbp else "") or "").strip()
            cached = bool(dbp and read_cached(settings, dbp.id))
            if not sheet_has:
                sheet_empty += 1
                print(f"SHEET_EMPTY {cat} | {name}")
            elif not cached:
                gap += 1
                print(f"NO_CACHE {cat} | {name} | db={'yes' if db_url else 'EMPTY'} | {image[:80]}")
        print("sheet_empty", sheet_empty, "no_cache", gap, "db_active", len(db_rows))

    book = gs._spreadsheet_client()
    print("--- formula urls not in photo column ---")
    samples = 0
    for definition in SHEETS:
        ws = book.worksheet(definition.title)
        rows = ws.get(value_render_option="FORMULA")
        for row in rows:
            hits = []
            for i, cell in enumerate(row):
                text = str(cell or "")
                if URL_RE.search(text):
                    hits.append((i, text[:100]))
            if not hits:
                continue
            photo = definition.image_column
            outside = [h for h in hits if h[0] != photo]
            in_photo = [h for h in hits if h[0] == photo]
            name = str(row[0])[:36] if row else ""
            if outside and samples < 20:
                print(definition.title, name, "photo_col", photo, "outside", outside, "in_photo", bool(in_photo))
                samples += 1
            elif in_photo and "HYPERLINK" in in_photo[0][1].upper() and samples < 20:
                print("FORMULA_IN_PHOTO", definition.title, name, in_photo[0][1][:120])
                samples += 1
    print("samples", samples)

asyncio.run(main())
"""

b64 = base64.b64encode(PY.encode()).decode()
cmd = (
    "set -a; . /etc/ches-hockey/env; set +a; "
    "cd /opt/bm33-mini-app/backend; "
    f"../.venv/bin/python3 -c \"import base64; exec(base64.b64decode('{b64}'))\""
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=20)
_, stdout, stderr = client.exec_command(cmd, timeout=180)
code = stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR", err[-2500:])
print("exit", code)
client.close()
