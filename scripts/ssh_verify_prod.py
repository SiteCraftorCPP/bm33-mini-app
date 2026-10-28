#!/usr/bin/env python3
"""Post-deploy smoke checks on VPS."""
import json
import re
import urllib.request
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
domain = re.search(r"домен:\s*(\S+)", text, re.I)
if not host or not domain:
    raise SystemExit("pas file incomplete")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)


def run(cmd: str) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    stdout.channel.recv_exit_status()
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace")


checks: list[tuple[str, bool, str]] = []

api_health = run("curl -sS http://127.0.0.1:8000/api/health")
checks.append(("api_health", '"ok"' in api_health or "ok" in api_health.lower(), api_health.strip()[:200]))

env = run("grep -E '^(SUPPORT_CHAT_ID|RUN_BOT|DEMO_MODE)=' /etc/ches-hockey/env")
checks.append(("support_chat", "SUPPORT_CHAT_ID=-1004378468284" in env, env.strip()))

perms = run(
    "namei -l /etc/ches-hockey/google-service-account.json 2>/dev/null | tail -1; "
    "sudo -u www-data test -r /etc/ches-hockey/google-service-account.json && echo SA_READ_OK"
)
checks.append(("sa_readable", "SA_READ_OK" in perms, perms.strip()[:200]))

grep_stock = run("grep -l fulfill_accepted_order /opt/bm33-mini-app/backend/app/bot/runtime.py 2>/dev/null && echo CODE_OK")
checks.append(("stock_on_accept_code", "CODE_OK" in grep_stock, grep_stock.strip()))

client.close()

site = f"https://{domain.group(1).strip()}"
try:
    with urllib.request.urlopen(f"{site}/api/health", timeout=20) as resp:
        public = resp.read().decode()
    checks.append(("public_https_health", resp.status == 200, public[:120]))
except Exception as exc:
    checks.append(("public_https_health", False, str(exc)))

failed = [name for name, ok, _ in checks if not ok]
for name, ok, detail in checks:
    mark = "OK" if ok else "FAIL"
    print(f"[{mark}] {name}: {detail}")

if failed:
    raise SystemExit(f"Failed: {', '.join(failed)}")
print("All smoke checks passed.")
