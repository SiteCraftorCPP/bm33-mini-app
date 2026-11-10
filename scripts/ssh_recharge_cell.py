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
from googleapiclient.discovery import build
from app.config import Settings
s = Settings()
creds = service_account.Credentials.from_service_account_file(
    s.google_service_account_file,
    scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
sheet_id = s.google_sheet_id
resp = svc.spreadsheets().get(
    spreadsheetId=sheet_id,
    ranges=["367022394!F226"],
    includeGridData=True,
    fields="sheets(data(rowData(values(userEnteredValue,formattedValue,effectiveValue))))",
).execute()
import json
print(json.dumps(resp, ensure_ascii=False)[:2000])
"""
b64 = base64.b64encode(py.encode()).decode()
cmd = (
    f"set -a && . /etc/ches-hockey/env && set +a && "
    f"cd /opt/bm33-mini-app/backend && ../.venv/bin/python3 -c "
    f"\"import base64; exec(base64.b64decode('{b64}'))\" 2>&1"
)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
_, stdout, _ = client.exec_command(cmd, timeout=120)
print(stdout.read().decode()[:3000])
client.close()
