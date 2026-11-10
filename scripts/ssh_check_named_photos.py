#!/usr/bin/env python3
"""Dump sheet rows and Drive fetch for Pulse / glove Fuse. No cache wipe."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = r'''
from sqlalchemy import select
from app.config import get_settings
from app.db import SessionLocal
from app.models import Product
from app.catalog.image_cache import read_cached, fetch_image_bytes
from app.catalog.importer import SHEETS, extract_drive_file_id
from app.integrations.google_sheets import GoogleSheets

NEEDLES = ("pulse", "pulsee", "graffiti", "fuse")
settings = get_settings()
gs = GoogleSheets(settings)
book = gs._spreadsheet_client()

print("=== SHEET ROWS ===")
for definition in SHEETS:
    ws = book.worksheet(definition.title)
    rows = ws.get(value_render_option="FORMULA")
    for row in rows[1:]:
        name = str(row[0] if row else "")
        low = name.casefold()
        if not any(n in low for n in NEEDLES):
            continue
        if "перчат" not in low and definition.category not in {"Клюшки", "Перчатки"} and "pulse" not in low and "graffiti" not in low:
            if definition.title not in {"Клюшки левые", "Клюшки правые", "Перчатки, защита,одежда"}:
                continue
        cells = []
        for i, cell in enumerate(row):
            text = str(cell or "").replace("\n", " ")
            if text:
                cells.append(f"{i}:{text[:110]}")
        print(definition.title, "|", name[:60])
        print(" ", " | ".join(cells))

print("=== DB ===")
with SessionLocal() as db:
    for p in db.scalars(select(Product).where(Product.active.is_(True))).all():
        low = p.name.casefold()
        if not any(n in low for n in ("pulse", "pulsee", "graffiti", "fuse")):
            continue
        cached = read_cached(settings, p.id)
        print(p.category, "|", p.name, "| cache", bool(cached), "|", (p.image_url or "EMPTY")[:140])
        stored = (p.image_url or "").strip()
        if not stored:
            continue
        file_id = extract_drive_file_id(stored.split("|")[0])
        got = fetch_image_bytes(stored, settings)
        print("  fetch", "OK" if got else "FAIL", "id", file_id, "bytes", len(got[0]) if got else 0)
'''

b64 = base64.b64encode(PY.encode()).decode()
cmd = (
    "set -a; . /etc/ches-hockey/env; set +a; "
    "cd /opt/bm33-mini-app/backend; "
    f"../.venv/bin/python3 -c \"import base64; exec(base64.b64decode('{b64}'))\""
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=20)
_, stdout, stderr = client.exec_command(cmd, timeout=120)
code = stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR", err[-2000:])
print("exit", code)
client.close()
