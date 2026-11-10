#!/usr/bin/env python3
"""One-shot photo status on VPS. No sync, no cache wipe."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = r"""
from pathlib import Path
from sqlalchemy import select
from app.config import get_settings
from app.db import SessionLocal
from app.models import Product
from app.catalog.image_cache import read_cached

settings = get_settings()
img_dir = Path("/var/lib/ches-hockey/catalog-images")
bins = list(img_dir.glob("*.bin")) if img_dir.is_dir() else []
print("cache_files", len(bins))
with SessionLocal() as db:
    rows = db.scalars(select(Product).where(Product.active.is_(True))).all()
    with_url = 0
    with_cache = 0
    url_no_cache = []
    no_url = []
    for p in rows:
        stored = (p.image_url or "").strip()
        cached = read_cached(settings, p.id) is not None
        if stored:
            with_url += 1
        else:
            no_url.append(p.name)
        if cached:
            with_cache += 1
        elif stored:
            url_no_cache.append(p.name)
    print("active", len(rows), "with_url", with_url, "with_cache", with_cache)
    print("url_but_no_file", len(url_no_cache))
    for name in url_no_cache[:12]:
        print("NOFILE", name)
    print("no_url", len(no_url))
    for name in no_url[:8]:
        print("NOURL", name)
"""

b64 = base64.b64encode(PY.encode()).decode()
cmd = (
    "set -a; . /etc/ches-hockey/env; set +a; "
    "cd /opt/bm33-mini-app/backend; "
    f"../.venv/bin/python3 -c \"import base64; exec(base64.b64decode('{b64}'))\"; "
    "systemctl is-active ches-hockey-api; "
    "curl -sS --max-time 5 http://127.0.0.1:8000/api/health"
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=20)
_, stdout, stderr = client.exec_command(cmd, timeout=40)
stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print(err[-500:])
client.close()
