#!/usr/bin/env python3
"""Pull backend and run one catalog sync on VPS."""
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
    gs = GoogleSheets(get_settings())
    imported = await gs.fetch_catalog(force=True)
    merged = _merged_products(imported)
    print("imported", len(imported), "merged", len(merged))
    print("warnings", gs.last_import_warnings[:5])
    with SessionLocal() as db:
        sync_catalog(db, imported)
        active = db.scalar(select(func.count()).select_from(Product).where(Product.active.is_(True)))
        goalie = db.scalar(
            select(func.count()).select_from(Product).where(
                Product.active.is_(True), Product.category == "Вратарские"
            )
        )
        print("db_active", active, "goalie", goalie)

asyncio.run(main())
'''

b64 = base64.b64encode(PY.encode()).decode()
cmd = (
    "set -e; cd /opt/bm33-mini-app && git fetch origin && git reset --hard origin/main; "
    "cd backend && ../.venv/bin/pip install -q -r requirements.txt; "
    "set -a; . /etc/ches-hockey/env; set +a; "
    f"../.venv/bin/python3 -c \"import base64; exec(base64.b64decode('{b64}'))\"; "
    "systemctl restart ches-hockey-api; sleep 4; systemctl is-active ches-hockey-api"
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=20)
_, stdout, stderr = client.exec_command(cmd, timeout=120)
code = stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
if stderr.read().decode().strip():
    print(stderr.read().decode()[-1000:])
print("exit", code)
client.close()
raise SystemExit(code)
