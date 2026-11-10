#!/usr/bin/env python3
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

py = r"""
import asyncio
from app.config import Settings
from app.db import SessionLocal
from app.catalog.service import sync_catalog
from app.integrations.google_sheets import GoogleSheets

async def main():
    gs = GoogleSheets(Settings())
    imported = await gs.fetch_catalog(force=True)
    with SessionLocal() as db:
        sync_catalog(db, imported)
    print("SYNC_OK", len(imported))

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
_, stdout, stderr = client.exec_command(cmd, timeout=180)
print(stdout.read().decode())
print(stderr.read().decode()[-1500:])
client.close()
