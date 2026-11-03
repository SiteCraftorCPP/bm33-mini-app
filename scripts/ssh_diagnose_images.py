#!/usr/bin/env python3
"""Diagnose product image cache on VPS."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
if not host:
    raise SystemExit("host not found")

PY = """
from sqlalchemy import select
from app.config import get_settings
from app.db import SessionLocal
from app.models import Product
from app.catalog.image_cache import read_cached, fetch_image_bytes, warm_catalog_image_caches

settings = get_settings()
with SessionLocal() as db:
    rows = db.scalars(select(Product).where(Product.active.is_(True))).all()
    fetch_fail = []
    cached = 0
    for p in rows:
        stored = (p.image_url or "").strip()
        if not stored:
            fetch_fail.append((p.name, "empty_db_url"))
            continue
        if read_cached(settings, p.id):
            cached += 1
            continue
        if fetch_image_bytes(stored, settings) is None:
            fetch_fail.append((p.name, stored[:120]))
    print("active", len(rows), "cached", cached, "problems", len(fetch_fail))
    for name, info in fetch_fail:
        print("PROBLEM", name, "|", info)
    print("warm", warm_catalog_image_caches(db, settings))
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
_, stdout, stderr = client.exec_command(cmd, timeout=600)
code = stdout.channel.recv_exit_status()
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
print(out)
if err.strip():
    print("STDERR:", err[-3000:])
client.close()
raise SystemExit(code)
