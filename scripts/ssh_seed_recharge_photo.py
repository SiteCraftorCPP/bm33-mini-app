#!/usr/bin/env python3
"""Fix Recharge photo: update sheet URLs + warm server cache."""
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PHOTO_URL = (
    "https://media.purehockey.com/q_auto,f_auto,fl_lossy,c_lpad,b_auto,w_800,h_800/"
    "products/71516/41/197148"
)

py = f"""
import asyncio
import gspread
from app.config import Settings
from app.db import SessionLocal
from app.catalog.service import sync_catalog
from app.catalog.image_cache import warm_catalog_image_caches_async
from app.integrations.google_sheets import GoogleSheets

PHOTO = {PHOTO_URL!r}

async def main():
    s = Settings()
    gc = gspread.service_account(filename=s.google_service_account_file)
    sh = gc.open_by_key(s.google_sheet_id)
    left = sh.get_worksheet_by_id(367022394)
    right = sh.get_worksheet_by_id(2084297659)
    left.update_cell(226, 6, PHOTO)
    right.update_cell(119, 6, PHOTO)
    print("SHEET_UPDATED", PHOTO[:60])
    gs = GoogleSheets(s)
    imported = await gs.fetch_catalog(force=True)
    with SessionLocal() as db:
        sync_catalog(db, imported)
    stats = await warm_catalog_image_caches_async(s)
    print("CACHE", stats)

asyncio.run(main())
"""
b64 = base64.b64encode(py.encode()).decode()
cmd = (
    f"set -a && . /etc/ches-hockey/env && set +a && "
    f"cd /opt/bm33-mini-app/backend && ../.venv/bin/python3 -c "
    f"\"import base64; exec(base64.b64decode('{b64}'))\""
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, o, e = client.exec_command(cmd, timeout=300)
print(o.read().decode())
err = e.read().decode()
if err:
    print("ERR", err[-2500:])
client.close()
