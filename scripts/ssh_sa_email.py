#!/usr/bin/env python3
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

py = r"""
import sqlite3
c=sqlite3.connect("/var/lib/ches-hockey/ches_hockey.sqlite3")
for name in ("Bauer Fuse", "CCM Tacks Recharge Pro"):
    r=c.execute("SELECT substr(image_url,1,120) FROM products WHERE name=?", (name,)).fetchone()
    print(name, r[0] if r else "missing")
import json
with open("/etc/ches-hockey/google-service-account.json") as f:
    print("SA_EMAIL", json.load(f)["client_email"])
"""
b64 = base64.b64encode(py.encode()).decode()
cmd = f"set -a && . /etc/ches-hockey/env && set +a && python3 -c \"import base64; exec(base64.b64decode('{b64}'))\""
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, stdout, _ = client.exec_command(cmd, timeout=30)
print(stdout.read().decode())
client.close()
