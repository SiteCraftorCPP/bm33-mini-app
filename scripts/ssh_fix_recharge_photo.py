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
from pathlib import Path
from app.config import Settings
from app.catalog.image_cache import (
    catalog_image_dir,
    cache_paths,
    fetch_image_bytes,
    refresh_product_image_cache,
    write_cached,
)
from app.catalog.importer import extract_drive_file_id
from google.oauth2 import service_account
import google.auth.transport.requests
import httpx

async def main():
    s = Settings()
    c = sqlite3.connect("/var/lib/ches-hockey/ches_hockey.sqlite3")
    row = c.execute(
        "SELECT id, name, image_url FROM products WHERE name LIKE '%Recharge%'"
    ).fetchone()
    print("PRODUCT", row)
    if not row:
        return
    pid, name, url = row
    data_path, meta_path = cache_paths(s, pid)
    print("CACHE", data_path.exists(), data_path, "size", data_path.stat().st_size if data_path.exists() else 0)
    fetched = fetch_image_bytes(url or "", s)
    print("FETCH", "OK" if fetched else "FAIL", len(fetched[0]) if fetched else 0)
    if fetched:
        write_cached(s, pid, fetched[0], fetched[1])
        print("WROTE_CACHE")
    else:
        ok = refresh_product_image_cache(s, pid, url or "")
        print("REFRESH", ok)
    fid = extract_drive_file_id(url or "")
    if fid and s.google_service_account_file:
        creds = service_account.Credentials.from_service_account_file(
            s.google_service_account_file,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        creds.refresh(google.auth.transport.requests.Request())
        h = {"Authorization": f"Bearer {creds.token}"}
        r = httpx.get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "q": f"name contains 'Recharge' and mimeType contains 'image'",
                "fields": "files(id,name,mimeType)",
                "pageSize": 10,
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
            headers=h,
            timeout=30,
        )
        print("DRIVE_SEARCH", r.status_code, r.text[:500])

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
_, o, e = client.exec_command(cmd, timeout=180)
print(o.read().decode())
print(e.read().decode()[-2000:])
client.close()
