#!/usr/bin/env python3
import ast
import re
from pathlib import Path

import httpx
import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
import base64
py_src = """
import sqlite3
c=sqlite3.connect("/var/lib/ches-hockey/ches_hockey.sqlite3")
rows=c.execute(
    "SELECT id,name,image_url FROM products WHERE image_url LIKE '%drive%' LIMIT 3"
).fetchall()
for r in rows:
    print(r)
r=c.execute(
    "SELECT id,name,image_url FROM products WHERE id='product-27ed8e49c5683af90d739375'"
).fetchone()
print("RECHARGE", r)
""".strip()
b64 = base64.b64encode(py_src.encode()).decode()
_, stdout, stderr = client.exec_command(f"python3 -c \"import base64; exec(base64.b64decode('{b64}'))\"", timeout=30)
row_line = stdout.read().decode().strip()
err = stderr.read().decode().strip()
client.close()
print("remote:", row_line or err)
if not row_line:
    raise SystemExit(1)
row = ast.literal_eval(row_line)
stored = (row[2] or "").strip()
print("Stored URL:", stored)

headers = {"User-Agent": "Mozilla/5.0 (compatible; ChesHockey/1.0)"}
file_id = None
m = re.search(r"[?&]id=([^&]+)", stored)
if m and "drive.google" in stored.casefold():
    file_id = m.group(1)
urls = [
    f"https://drive.google.com/uc?export=download&id={file_id}",
    f"https://drive.google.com/uc?export=view&id={file_id}",
] if file_id else ([stored] if stored else [])

for url in urls:
    try:
        with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as c:
            r = c.get(url)
            print(url[:90], "->", r.status_code, r.headers.get("content-type"), len(r.content))
            if len(r.content) < 200:
                print(r.content[:200])
    except Exception as exc:
        print(url[:90], "-> ERR", exc)

# also test from VPS
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
for url in urls[:1]:
    _, stdout, _ = client.exec_command(
        f"curl -sS -o /tmp/img.bin -w '%{{http_code}} %{{content_type}} %{{size_download}}' "
        f"-A 'Mozilla/5.0 (compatible; ChesHockey/1.0)' -L {url!r}",
        timeout=60,
    )
    print("VPS curl:", stdout.read().decode())
client.close()
