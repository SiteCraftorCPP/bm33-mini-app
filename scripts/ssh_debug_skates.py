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
import sqlite3
from app.config import Settings
from app.integrations.google_sheets import GoogleSheets
from app.catalog.importer import SHEETS, parse_sheet

async def main():
    gs = GoogleSheets(Settings())
    imported = await gs.fetch_catalog(force=True)
    skates = [p for p in imported if p.category == "Коньки"]
    print("PARSED_SKATE_PRODUCTS", len(skates))
    for p in skates[:8]:
        print("P", p.name, "| img:", (p.image_url or "")[:70], "| vars", len(p.variants))
    rech = [p for p in imported if "recharge" in p.name.lower()]
    for p in rech:
        print("RECH", p.name, "|", p.image_url or "EMPTY")

    c = sqlite3.connect("/var/lib/ches-hockey/ches_hockey.sqlite3")
    rows = c.execute(
        "SELECT name, substr(image_url,1,90) FROM products WHERE category='Коньки' LIMIT 8"
    ).fetchall()
    print("DB_SKATES")
    for r in rows:
        print(" ", r)

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
_, stdout, stderr = client.exec_command(cmd, timeout=120)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR", err[-2500:])
client.close()
