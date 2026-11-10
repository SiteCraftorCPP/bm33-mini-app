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
from app.catalog.importer import parse_sheet, SHEETS, normalize_image_url
from app.config import Settings
from app.integrations.google_sheets import GoogleSheets

async def main():
    gs = GoogleSheets(Settings())
    # authorized fetch only left+right
    imported = await gs.fetch_catalog(force=True)
    left = [p for p in imported if p.category == "Клюшки" and p.variants and p.variants[0].side == "L"]
    right = [p for p in imported if p.category == "Клюшки" and p.variants and p.variants[0].side == "R"]
    for side, items in ("L", left), ("R", right):
        for p in items:
            if "recharge" in p.name.lower() or "recharg" in p.name.lower():
                print(side, p.name, "|", p.image_url or "(empty)")

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
print(stderr.read().decode()[-1500:])
client.close()
