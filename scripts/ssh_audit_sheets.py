#!/usr/bin/env python3
"""Fetch live Sheets on VPS and run stick_catalog_warnings + image stats."""
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

py = r"""
import asyncio
from app.catalog.importer import stick_catalog_warnings
from app.catalog.service import _merged_products
from app.config import Settings
from app.integrations.google_sheets import GoogleSheets

async def main():
    gs = GoogleSheets(Settings())
    imported = await gs.fetch_catalog(force=True)
    sticks = [p for p in imported if p.category == "Клюшки"]
    merged = _merged_products(imported)
    merged_sticks = [m for m in merged if m[2] == "Клюшки"]
    no_img = [m[1] for m in merged_sticks if not (m[4] or "").strip()]
    multi = [m[1] for m in merged_sticks if "|" in (m[4] or "")]
    warnings = stick_catalog_warnings(imported)
    print("IMPORTED_STICK_BLOCKS", len(sticks))
    print("MERGED_STICK_CARDS", len(merged_sticks))
    print("NO_IMAGE", len(no_img))
    if no_img[:12]:
        print("NO_IMAGE_SAMPLE", no_img[:12])
    print("MULTI_URL", len(multi))
    print("WARNINGS", len(warnings))
    for w in warnings[:40]:
        print("W:", w)
    if len(warnings) > 40:
        print("W: ...", len(warnings) - 40, "more")

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
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
client.close()
print(out)
if err.strip():
    print("STDERR:", err[-2000:])
