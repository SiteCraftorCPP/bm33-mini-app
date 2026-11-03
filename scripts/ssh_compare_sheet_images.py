#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = """
import asyncio
from sqlalchemy import select
from app.config import get_settings
from app.db import SessionLocal
from app.models import Product
from app.integrations.google_sheets import GoogleSheets

NAMES = {
    'True Hzrdus 9X', 'Bauer Flylite', 'Перчатки Bauer Fuse', 'CCM Trigger 10 Pro',
    'Bauer Fuse', 'CCM Jetspeed FT9 pro',
}

async def main():
    gs = GoogleSheets(get_settings())
    imported = await gs.fetch_catalog(force=True)
    by = {p.name: p for p in imported}
    print('=== imported from sheets ===')
    for n in sorted(NAMES):
        p = by.get(n)
        if not p:
            for k,v in by.items():
                if n.split()[0] in k:
                    print('?', n, '-> maybe', k, (v.image_url or '')[:80])
            print('MISSING', n)
            continue
        print(n, '|', (p.image_url or 'EMPTY')[:100])
    with SessionLocal() as db:
        print('=== db ===')
        for p in db.scalars(select(Product)).all():
            if p.name in NAMES:
                print(p.name, '|', (p.image_url or 'EMPTY')[:100])

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
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, stdout, stderr = client.exec_command(cmd, timeout=300)
stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR", err[-2000:])
client.close()
