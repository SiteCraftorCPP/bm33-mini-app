#!/usr/bin/env python3
"""Find why Telegram may load old UI: URLs, nginx roots, bot menu, dist fingerprints."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host_m = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
token_m = re.search(r"токен:\s*(\S+)", text, re.I)
domain_m = re.search(r"домен:\s*(\S+)", text, re.I)
if not host_m or not token_m or not domain_m:
    raise SystemExit("pas incomplete")

domain = domain_m.group(1).strip()
token = token_m.group(1)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host_m.group(1), username="root", password=host_m.group(2), timeout=30)


def run(cmd: str) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    stdout.channel.recv_exit_status()
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace")


print("=== NGINX ROOTS ===")
print(run("grep -r root /etc/nginx/sites-enabled/ 2>/dev/null"))

print("\n=== DIST FINGERPRINT ===")
print(run("grep -l brand-mark /opt/bm33-mini-app/web/dist/assets/*.js 2>/dev/null || echo NO_brand_mark_in_js"))
print(run("grep -l logo-header /opt/bm33-mini-app/web/dist/assets/*.js 2>/dev/null || echo NO_logo"))
print(run("grep baner /opt/bm33-mini-app/web/dist/assets/*.css 2>/dev/null | head -1 || echo NO_baner_css"))

print("\n=== LIVE HTML (apex + www) ===")
for host in [domain, f"www.{domain}"]:
    print(f"--- {host} ---")
    print(
        run(
            f"curl -sS -H 'Cache-Control: no-cache' 'https://{host}/' | "
            f"grep -E 'index-|title|brand-mark|logo-header' | head -5"
        )
    )

print("\n=== TELEGRAM MENU BUTTON ===")
try:
    url = f"https://api.telegram.org/bot{token}/getChatMenuButton"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as exc:
    print("getChatMenuButton failed:", exc)

print("\n=== BOT MINI APP INFO (getMe + setMenuButton check) ===")
try:
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=30) as resp:
        print(json.dumps(json.loads(resp.read().decode()), ensure_ascii=False, indent=2))
except Exception as exc:
    print(exc)

client.close()
