#!/usr/bin/env python3
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)

py = r"""
import gspread
from app.config import Settings
s = Settings()
gc = gspread.service_account(filename=s.google_service_account_file)
sh = gc.open_by_key(s.google_sheet_id)
for ws in sh.worksheets():
    for i, row in enumerate(ws.get_all_values(), 1):
        line = " ".join(row).lower()
        if "recharge" in line and ("yandex" in line or "disk." in line or "drive" in line):
            print(ws.title, i, [c for c in row if c][:6])
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
_, stdout, _ = client.exec_command(cmd, timeout=180)
print(stdout.read().decode() or "(no yandex recharge)")
client.close()
