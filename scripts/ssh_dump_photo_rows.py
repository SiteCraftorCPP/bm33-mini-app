#!/usr/bin/env python3
"""Dump raw formula cells for products the parser thinks have no photo."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = r"""
from app.config import get_settings
from app.integrations.google_sheets import GoogleSheets
from app.catalog.importer import SHEETS

NEEDLES = ("Hzrdus", "Tracer", "Fuse L", "Перчатки Bauer", "Reakt 55", "Mach")
settings = get_settings()
gs = GoogleSheets(settings)
book = gs._spreadsheet_client()
for definition in SHEETS:
    ws = book.worksheet(definition.title)
    rows = ws.get(value_render_option="FORMULA")
    if not rows:
        continue
    header = rows[0]
    print("SHEET", definition.title, "cols", len(header), "photo_idx", definition.image_column)
    print("HEADER", [(i, (c or "")[:24]) for i, c in enumerate(header)])
    shown = 0
    for row in rows[1:]:
        name = str(row[0] if row else "")
        if not any(n.casefold() in name.casefold() for n in NEEDLES):
            continue
        cells = []
        for i, cell in enumerate(row):
            text = str(cell or "").replace("\n", " ")
            if text:
                cells.append(f"{i}:{text[:80]}")
        print("ROW", name[:50])
        print(" ", " | ".join(cells) if cells else "(empty)")
        shown += 1
        if shown >= 3:
            break
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
_, stdout, stderr = client.exec_command(cmd, timeout=90)
code = stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR", err[-1500:])
print("exit", code)
client.close()
