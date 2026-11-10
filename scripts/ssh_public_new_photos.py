#!/usr/bin/env python3
"""See if the new Drive links are public, without the service account."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

PY = r'''
import httpx
ids = {
    "Pulse": "1ZA36qyHuNFbxM5gv6yTgjnEblfAJQmzu",
    "Graffiti": "1m2rHROURYl5zyxa1LY4TKsgVwk23lfpK",
    "Glove": "1dJ1MH7_gXGTb2vk0nf846WPsbG33vVJQ",
}
headers = {"User-Agent": "Mozilla/5.0"}
with httpx.Client(timeout=25.0, follow_redirects=True, headers=headers) as client:
    for label, file_id in ids.items():
        url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
        response = client.get(url)
        ctype = response.headers.get("content-type", "")
        head = response.content[:40]
        print(label, response.status_code, ctype, "len", len(response.content), "head", head[:24], "final", str(response.url)[:80])
'''

b64 = base64.b64encode(PY.encode()).decode()
cmd = (
    "cd /opt/bm33-mini-app/backend; "
    f"../.venv/bin/python3 -c \"import base64; exec(base64.b64decode('{b64}'))\""
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=20)
_, stdout, stderr = client.exec_command(cmd, timeout=60)
stdout.channel.recv_exit_status()
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR", err[-800:])
client.close()
