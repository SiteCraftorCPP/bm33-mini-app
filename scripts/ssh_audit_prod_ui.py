#!/usr/bin/env python3
"""Deep audit: prod UI assets, API, git revision."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host_m = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
domain_m = re.search(r"домен:\s*(\S+)", text, re.I)
if not host_m or not domain_m:
    raise SystemExit("pas incomplete")

domain = domain_m.group(1).strip()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host_m.group(1), username="root", password=host_m.group(2), timeout=30)


def run(cmd: str, timeout: int = 120) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    stdout.channel.recv_exit_status()
    return (stdout.read() + stderr.read()).decode("utf-8", errors="replace")


failures: list[str] = []

print("=== GIT ===")
print(run("cd /opt/bm33-mini-app && git log -1 --oneline"))

print("\n=== DIST ASSETS ===")
print(run("ls -la /opt/bm33-mini-app/web/dist/logo-header.png /opt/bm33-mini-app/web/dist/baner.jpg"))
js_path = run("ls /opt/bm33-mini-app/web/dist/assets/index-*.js 2>/dev/null | head -1").strip()
print("js:", js_path)

print("\n=== index.html ===")
print(run("cat /opt/bm33-mini-app/web/dist/index.html"))

needles = [
    ("logo-header", "logo-header"),
    ("Хват label", "Хват"),
    ("old СТОРОНА", "СТОРОНА"),
    ("Chesalin title", "Chesalin Hockey"),
    ("old CHES STORE", "CHES HOCKEY STORE"),
    ("promos API", "admin/promos"),
]
print("\n=== JS CONTENT ===")
for label, needle in needles:
    hit = run(f"grep -F '{needle}' '{js_path}' >/dev/null && echo YES || echo NO").strip()
    print(f"{label}: {hit}")
    if needle == "logo-header" and hit != "YES":
        failures.append("JS missing logo-header")
    if needle == "Хват" and hit != "YES":
        failures.append("JS missing Хват")
    if needle == "СТОРОНА" and hit == "YES":
        failures.append("JS still has СТОРОНА")
    if needle == "CHES HOCKEY STORE" and hit == "YES":
        failures.append("JS still has old brand")

print("\n=== HTTPS STATIC ===")
for path in ["/", "/logo-header.png", "/baner.jpg"]:
    code = run(f"curl -sS -o /dev/null -w '%{{http_code}}' https://{domain}{path}").strip()
    print(path, code)
    if code != "200":
        failures.append(f"{path} HTTP {code}")

print("\n=== API ===")
print(run(f"curl -sS https://{domain}/api/health"))
promo = run(
    f"curl -sS -o /dev/null -w '%{{http_code}}' "
    f"-X POST https://{domain}/api/promos/validate "
    f"-H 'Content-Type: application/json' "
    f"-H 'X-Demo-User-Id: 100001' "
    f"-d '{{\"code\":\"X\",\"subtotal\":1000}}'"
).strip()
print("POST /api/promos/validate:", promo)
if promo == "404":
    failures.append("promo API 404")

print("\n=== ENV WEBAPP URL ===")
print(run("grep PUBLIC_WEBAPP_URL /etc/ches-hockey/env"))

print("\n=== RUN CATALOG SYNC (import + warnings) ===")
sync_py = r"""
import asyncio, json, sys
sys.path.insert(0, '/opt/bm33-mini-app/backend')
from app.config import get_settings
from app.integrations.google_sheets import GoogleSheets
from app.catalog.importer import stick_catalog_warnings
from app.db import SessionLocal
from app.catalog.service import sync_catalog

async def main():
    s = get_settings()
    sheets = GoogleSheets(s)
    imported = await sheets.fetch_catalog(force=True)
    warnings = stick_catalog_warnings(imported)
    with SessionLocal() as db:
        sync_catalog(db, imported)
    sticks = [p for p in imported if p.category == 'Клюшки']
    print('IMPORT_PRODUCTS', len(imported))
    print('STICK_BLOCKS', len(sticks))
    print('WARNINGS_COUNT', len(warnings))
    for w in warnings[:15]:
        print('WARN', w)
    if len(warnings) > 15:
        print('WARN_MORE', len(warnings) - 15)

asyncio.run(main())
"""
import base64

b64 = base64.b64encode(sync_py.encode()).decode()
print(run(f"echo {b64} | base64 -d | /opt/bm33-mini-app/backend/.venv/bin/python"))

client.close()

print("\n=== SUMMARY ===")
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("All UI/API audit checks passed.")
