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
path = "/etc/ches-hockey/google-service-account.json"
creds = service_account.Credentials.from_service_account_file(
    path, scopes=["https://www.googleapis.com/auth/drive"]
)
creds.refresh(google.auth.transport.requests.Request())
fid = "1VOD-pu54UAc6HyXeUneOuXaJG9-Arv37"
headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
r = httpx.post(
    f"https://www.googleapis.com/drive/v3/files/{fid}/permissions",
    params={"supportsAllDrives": "true"},
    headers=headers,
    json={"type": "anyone", "role": "reader"},
    timeout=30,
)
print("perm", r.status_code, r.text[:300])
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
_, stdout, stderr = client.exec_command(cmd, timeout=60)
print(stdout.read().decode())
print(stderr.read().decode()[-800:])
client.close()
