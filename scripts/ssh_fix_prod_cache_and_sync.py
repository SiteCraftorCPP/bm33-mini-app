#!/usr/bin/env python3
"""Apply nginx cache fix + catalog sync on VPS."""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host_m = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
if not host_m:
    raise SystemExit("no host")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host_m.group(1), username="root", password=host_m.group(2), timeout=30)
sftp = client.open_sftp()

remote_conf = "/etc/nginx/sites-available/ches-hockey"
local_conf = ROOT / "deploy" / "nginx-ches-hockey.conf"
sftp.put(str(local_conf), remote_conf)

cmds = """
nginx -t && systemctl reload nginx
sudo -u www-data bash -lc 'set -a && source /etc/ches-hockey/env && set +a && cd /opt/bm33-mini-app && PYTHONPATH=backend /opt/bm33-mini-app/.venv/bin/python - <<'"'"'PY'"'"'
import asyncio
import sys
sys.path.insert(0, "/opt/bm33-mini-app/backend")
from app.config import get_settings
from app.integrations.google_sheets import GoogleSheets
from app.catalog.importer import stick_catalog_warnings
from app.db import SessionLocal
from app.catalog.service import sync_catalog, catalog_payload

async def main():
    settings = get_settings()
    sheets = GoogleSheets(settings)
    imported = await sheets.fetch_catalog(force=True)
    warnings = stick_catalog_warnings(imported)
    with SessionLocal() as db:
        sync_catalog(db, imported)
        payload = catalog_payload(db)
    sticks = [p for p in payload["products"] if p["category"] == "Клюшки"]
    print("SYNC_OK products", len(payload["products"]), "sticks", len(sticks))
    print("WARNINGS", len(warnings))
    for w in warnings[:20]:
        print(" -", w)

asyncio.run(main())
PY'
systemctl restart ches-hockey-api
sleep 10
curl -sS -I https://ches-hockey.ru/index.html | grep -i cache || true
curl -sS --retry 5 --retry-delay 2 http://127.0.0.1:8000/api/health
"""

def run(cmd: str) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=300)
    code = stdout.channel.recv_exit_status()
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
    if code != 0:
        print(out)
        sys.exit(code)
    return out

print(run(cmds))
sftp.close()
client.close()
print("Done.")
