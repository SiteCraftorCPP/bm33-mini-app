#!/usr/bin/env python3
"""Short check: Pulsee URLs, cache files, Drive status."""
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
from app.catalog.image_cache import read_cached, cache_paths

settings = get_settings()
names = ("Bauer Pulsee", "Bauer Pulsee Graffiti", "Bauer Fuse", "CCM Jetspeed FT9 pro")
img_dir = Path("/var/lib/ches-hockey/catalog-images")
bins = list(img_dir.glob("*.bin")) if img_dir.is_dir() else []
print("cache_files", len(bins))
with SessionLocal() as db:
    for p in db.scalars(select(Product).where(Product.active.is_(True))).all():
        if p.name not in names:
            continue
        cached = read_cached(settings, p.id)
        print("---", p.name)
        print("id", p.id)
        print("url", (p.image_url or "EMPTY")[:180])
        print("cached", bool(cached), "bytes", len(cached[0]) if cached else 0)
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
_, stdout, stderr = client.exec_command(cmd, timeout=40)
stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print(err[-800:])
client.close()
