from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.bot.runtime import TelegramService
from app.catalog.importer import demo_catalog
from app.catalog.service import sync_catalog
from app.config import get_settings
from sqlalchemy import inspect, text

from app.db import Base, SessionLocal, engine
from app.integrations.google_sheets import GoogleSheets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ches-hockey")


def _ensure_sqlite_columns(db_engine) -> None:
    if not str(db_engine.url).startswith("sqlite"):
        return
    inspector = inspect(db_engine)
    if "orders" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("orders")}
    with db_engine.begin() as conn:
        if "promo_code" not in columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN promo_code VARCHAR(32) DEFAULT ''"))
        if "discount" not in columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN discount INTEGER DEFAULT 0"))


async def refresh_catalog(app: FastAPI) -> None:
    try:
        products = await app.state.sheets.fetch_catalog()
    except Exception:
        log.exception("Google Sheets sync failed")
        with SessionLocal() as db:
            if not app.state.has_catalog(db):
                sync_catalog(db, demo_catalog())
        return

    with SessionLocal() as db:
        restocked = sync_catalog(db, products)
        from app.catalog.image_cache import warm_catalog_image_caches

        warm_catalog_image_caches(db, app.state.settings)
    if restocked:
        await app.state.telegram.notify_restock(restocked)
    log.info("Catalog synchronized: %s products", len(products))


async def sync_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(max(app.state.settings.sheets_sync_interval_seconds, 15))
        await refresh_catalog(app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.models import Product

    Base.metadata.create_all(engine)
    _ensure_sqlite_columns(engine)
    app.state.settings = get_settings()
    app.state.logger = log
    app.state.sheets = GoogleSheets(app.state.settings)
    app.state.telegram = TelegramService(app.state.settings, app.state.sheets)
    app.state.has_catalog = lambda db: db.query(Product.id).first() is not None

    await refresh_catalog(app)
    await app.state.telegram.start()
    background = asyncio.create_task(sync_loop(app))
    try:
        yield
    finally:
        background.cancel()
        with suppress(asyncio.CancelledError):
            await background
        await app.state.telegram.stop()


settings = get_settings()
app = FastAPI(title="Ches Hockey API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root() -> dict:
    return {"name": "Ches Hockey API", "docs": "/docs"}
