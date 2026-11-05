#!/usr/bin/env python3
"""Catalog sync health: interval, last errors, sheet vs DB counts."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = r'''
import asyncio
from sqlalchemy import func, select
from app.config import get_settings
from app.db import SessionLocal
from app.models import Product
from app.integrations.google_sheets import GoogleSheets
from app.catalog.service import sync_catalog, _merged_products

async def main():
    settings = get_settings()
    print("SHEETS_SYNC_INTERVAL_SECONDS", settings.sheets_sync_interval_seconds)
    gs = GoogleSheets(settings)
    try:
        imported = await gs.fetch_catalog(force=True)
        merged = _merged_products(imported)
        print("fetch_ok imported_products", len(imported), "merged_cards", len(merged))
        goalie = [m for m in merged if m[2] == "Вратарские"]
        print("goalie_in_sheet", len(goalie))
        for _pid, name, _cat, _so, _img, vars in goalie[-8:]:
            print(" GOALIE", name, "variants", len(vars))
    except Exception as exc:
        print("fetch_FAILED", type(exc).__name__, str(exc)[:500])
        imported = None
    with SessionLocal() as db:
        active = db.scalar(select(func.count()).select_from(Product).where(Product.active.is_(True)))
        goalie_db = db.scalars(select(Product).where(Product.active.is_(True), Product.category == "Вратарские")).all()
        print("db_active", active, "db_goalie", len(goalie_db))
        for p in sorted(goalie_db, key=lambda x: x.name)[-10:]:
            print(" DB", p.name, p.id)
    if imported is not None:
        with SessionLocal() as db:
            sync_catalog(db, imported)
            active2 = db.scalar(select(func.count()).select_from(Product).where(Product.active.is_(True)))
            print("after_sync_active", active2)

asyncio.run(main())
'''

b64 = base64.b64encode(PY.encode()).decode()
cmd = (
    "set -a; . /etc/ches-hockey/env; set +a; "
    "cd /opt/bm33-mini-app/backend; "
    f"../.venv/bin/python3 -c \"import base64; exec(base64.b64decode('{b64}'))\"; "
    "echo '--- logs ---'; "
    "journalctl -u ches-hockey-api --since '6 hours ago' --no-pager 2>/dev/null | "
    "grep -iE 'sync|Catalog|Sheets|CatalogData|ERROR|failed' | tail -25"
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=20)
_, stdout, stderr = client.exec_command(cmd, timeout=120)
code = stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR", err[-1500:])
print("exit", code)
client.close()
