#!/usr/bin/env python3
import base64
import re
from pathlib import Path

import httpx
import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

py_src = """
import sqlite3
c=sqlite3.connect("/var/lib/ches-hockey/ches_hockey.sqlite3")
for r in c.execute(
    "SELECT name, image_url FROM products WHERE name IN ('Bauer Fuse','CCM Tacks Recharge Pro')"
).fetchall():
    print(r[0], "|", r[1])
""".strip()
b64 = base64.b64encode(py_src.encode()).decode()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, stdout, _ = client.exec_command(f"python3 -c \"import base64; exec(base64.b64decode('{b64}'))\"", timeout=30)
print(stdout.read().decode())
client.close()

headers = {"User-Agent": "Mozilla/5.0 (compatible; ChesHockey/1.0)"}
