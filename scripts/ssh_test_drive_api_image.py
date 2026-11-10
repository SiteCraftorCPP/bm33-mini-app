#!/usr/bin/env python3
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

py = r"""
from google.oauth2 import service_account
import google.auth.transport.requests
import httpx
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = service_account.Credentials.from_service_account_file(
    "/etc/ches-hockey/google-service-account.json", scopes=SCOPES
)
creds.refresh(google.auth.transport.requests.Request())
fid = "1VOD-pu54UAc6HyXeUneOuXaJG9-Arv37"
headers = {"Authorization": f"Bearer {creds.token}"}
meta = httpx.get(
    f"https://www.googleapis.com/drive/v3/files/{fid}",
    params={"fields": "name,mimeType"},
    headers=headers,
    timeout=30,
)
print("meta", meta.status_code, meta.text[:200])
r = httpx.get(
    f"https://www.googleapis.com/drive/v3/files/{fid}",
    params={"alt": "media"},
    headers=headers,
    timeout=60,
    follow_redirects=True,
)
print("media", r.status_code, r.headers.get("content-type"), len(r.content), r.content[:8])
"""

b64 = base64.b64encode(py.encode()).decode()
cmd = (
    "cd /opt/bm33-mini-app && .venv/bin/python3 -c "
    f"\"import base64; exec(base64.b64decode('{b64}'))\""
)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, stdout, stderr = client.exec_command(cmd, timeout=120)
print(stdout.read().decode())
print(stderr.read().decode()[-800:])
client.close()
