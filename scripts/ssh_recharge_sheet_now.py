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
for gid in (367022394, 2084297659):
    ws = sh.get_worksheet_by_id(gid)
    for i, row in enumerate(ws.get_all_values(), 1):
        if row and "recharge" in " ".join(row).lower():
            print("row", gid, i, row[:7])
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
_, o, _ = client.exec_command(cmd, timeout=120)
print(o.read().decode())
client.close()
