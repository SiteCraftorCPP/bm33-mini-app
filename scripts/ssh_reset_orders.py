#!/usr/bin/env python3
"""Restore stock for accepted orders, wipe orders table, reset id sequence on VPS."""
import base64
import re
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]

remote_py = """
import asyncio
import sys
sys.path.insert(0, "/opt/bm33-mini-app/backend")
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.config import get_settings
from app.integrations.google_sheets import GoogleSheets
from app.models import Order
from app.catalog.service import sync_catalog
from app.integrations.google_sheets import SheetsError
from app.orders.stock import restore_accepted_order_stock

async def main():
    settings = get_settings()
    sheets = GoogleSheets(settings)
    engine = create_engine(settings.database_url)
    with Session(engine) as db:
        order_ids = [row[0] for row in db.execute(select(Order.id)).all()]
        for order_id in order_ids:
            order = db.get(Order, order_id)
            if order is None:
                continue
            print("ORDER", order_id, order.status)
            if order.status == "accepted":
                try:
                    await restore_accepted_order_stock(db, sheets, order_id)
                    db.commit()
                except SheetsError as exc:
                    print("RESTORE_SKIP", order_id, exc)
        imported = await sheets.fetch_catalog(force=True)
        sync_catalog(db, imported)
        db.execute(text("DELETE FROM order_items"))
        db.execute(text("DELETE FROM orders"))
        try:
            db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('orders', 'order_items')"))
        except Exception:
            pass
        db.commit()
    print("RESET_OK")

asyncio.run(main())
"""

text = (ROOT / "pas bm33 mini app.txt").read_text(encoding="utf-8")
host = re.search(r"хост:\s*([0-9.]+)\s*/\s*(\S+)", text, re.I)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host.group(1), username="root", password=host.group(2), timeout=30)
b64 = base64.b64encode(remote_py.encode()).decode()
cmd = (
    "set -a && source /etc/ches-hockey/env && set +a && "
    f"echo {b64} | base64 -d | /opt/bm33-mini-app/.venv/bin/python"
)
_, stdout, stderr = client.exec_command(cmd, timeout=180)
stdout.channel.recv_exit_status()
print(stdout.read().decode())
err = stderr.read().decode()
if err.strip():
    print(err)
client.close()
