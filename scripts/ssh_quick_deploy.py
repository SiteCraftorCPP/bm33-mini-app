#!/usr/bin/env python3
"""Fast deploy: local web build + SFTP dist + git pull backend + restart."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host_m = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
if not host_m:
    raise SystemExit("host not found in pas file")

print("1/4 local web build...")
subprocess.run(
    ["npm", "run", "build"],
    cwd=ROOT / "web",
    check=True,
    shell=True,
)

if not (DIST / "index.html").is_file():
    raise SystemExit("web/dist missing after build")

print("2/4 connect...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host_m.group(1), username="root", password=host_m.group(2), timeout=20)


def run(cmd: str, timeout: int = 120) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = (stdout.read() + stderr.read()).decode(errors="replace")
    return code, out


print("3/4 git pull backend on VPS...")
code, out = run(
    "git config --global --add safe.directory /opt/bm33-mini-app && "
    "cd /opt/bm33-mini-app && git fetch origin && git reset --hard origin/main && "
    "cd backend && ../.venv/bin/pip install -q -r requirements.txt",
    timeout=180,
)
print(out[-1500:] if out else "")
if code != 0:
    client.close()
    raise SystemExit(code)

print("3/4 upload web/dist via SFTP...")
sftp = client.open_sftp()


def upload_dir(local: Path, remote: str) -> None:
    try:
        sftp.mkdir(remote)
    except OSError:
        pass
    for entry in local.iterdir():
        r = f"{remote}/{entry.name}"
        if entry.is_dir():
            upload_dir(entry, r)
        else:
            sftp.put(str(entry), r)


upload_dir(DIST, "/opt/bm33-mini-app/web/dist")

sftp.close()

print("4/4 restart API...")
code, out = run(
    "systemctl reload nginx; "
    "systemctl restart ches-hockey-api; "
    "sleep 3; systemctl is-active ches-hockey-api; "
    "curl -sS --max-time 5 http://127.0.0.1:8000/api/health",
    timeout=30,
)
print(out.strip())
client.close()
print("done")
raise SystemExit(code)
