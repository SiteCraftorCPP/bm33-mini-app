#!/usr/bin/env python3
"""Pull latest backend, sync catalog, warm image cache."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = """
import asyncio
from app.config import get_settings
from app.db import SessionLocal
from app.catalog.service import sync_catalog
from app.catalog.image_cache import warm_catalog_image_caches
from app.integrations.google_sheets import GoogleSheets

async def main():
    settings = get_settings()
    gs = GoogleSheets(settings)
    imported = await gs.fetch_catalog(force=True)
    with SessionLocal() as db:
        sync_catalog(db, imported)
        warm = warm_catalog_image_caches(db, settings)
        print("imported", len(imported))
        print("warm", warm)

asyncio.run(main())
"""

b64 = base64.b64encode(PY.encode()).decode()
cmd = (
    "set -e; cd /opt/bm33-mini-app && git fetch origin && git reset --hard origin/main; "
    "cd backend && ../.venv/bin/pip install -q -r requirements.txt; "
    "set -a; . /etc/ches-hockey/env; set +a; "
    f"../.venv/bin/python3 -c \"import base64; exec(base64.b64decode('{b64}'))\"; "
    "systemctl restart ches-hockey-api; sleep 5; systemctl is-active ches-hockey-api"
)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, stdout, stderr = client.exec_command(cmd, timeout=600)
code = stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
print(stderr.read().decode(errors="replace")[-2000:])
client.close()
raise SystemExit(code)
