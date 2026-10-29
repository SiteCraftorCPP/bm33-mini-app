from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx

from app.catalog.importer import catalog_image_fetch_urls, extract_drive_file_id
from app.db import SessionLocal
from sqlalchemy import select

from app.config import Settings
from app.models import Product

_FETCH_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChesHockey/1.0)"}
_META_SUFFIX = ".meta"


def catalog_image_dir(settings: Settings) -> Path:
    custom = (getattr(settings, "catalog_image_dir", None) or "").strip()
    if custom:
        path = Path(custom)
    elif "ches-hockey" in settings.database_url:
        path = Path("/var/lib/ches-hockey/catalog-images")
    else:
        path = Path(__file__).resolve().parents[2] / "catalog-images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_product_id(product_id: str) -> str:
    cleaned = re.sub(r"[^\w.-]", "_", product_id)
    return cleaned[:120] or "product"


def cache_paths(settings: Settings, product_id: str) -> tuple[Path, Path]:
    base = catalog_image_dir(settings) / _safe_product_id(product_id)
    return base.with_suffix(".bin"), base.with_suffix(".bin" + _META_SUFFIX)


def read_cached(settings: Settings, product_id: str) -> tuple[bytes, str] | None:
    data_path, meta_path = cache_paths(settings, product_id)
    if not data_path.is_file() or data_path.stat().st_size < 512:
        return None
    mime = "image/jpeg"
    if meta_path.is_file():
        mime = meta_path.read_text(encoding="utf-8").strip() or mime
    return data_path.read_bytes(), mime


def write_cached(settings: Settings, product_id: str, body: bytes, content_type: str) -> None:
    data_path, meta_path = cache_paths(settings, product_id)
    data_path.write_bytes(body)
    meta_path.write_text(content_type.split(";")[0].strip() or "image/jpeg", encoding="utf-8")


def _guess_mime(body: bytes, content_type: str) -> str | None:
    if content_type.casefold().startswith("image/"):
        return content_type.split(";")[0].strip()
    if len(body) >= 3 and body[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(body) >= 8 and body[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    return None


def _drive_service_account_bytes(stored: str, settings: Settings, client: httpx.Client) -> tuple[bytes, str] | None:
    path = (settings.google_service_account_file or "").strip()
    if not path:
        return None
    for chunk in re.split(r"[|\n]+", stored):
        file_id = extract_drive_file_id(chunk.strip())
        if not file_id:
            continue
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests

            creds = service_account.Credentials.from_service_account_file(
                path,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            creds.refresh(google.auth.transport.requests.Request())
            response = client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"alt": "media", "supportsAllDrives": "true"},
                headers={"Authorization": f"Bearer {creds.token}"},
                timeout=60.0,
            )
            if response.status_code != 200 or len(response.content) < 512:
                continue
            mime = _guess_mime(response.content, response.headers.get("content-type", ""))
            if mime:
                return response.content, mime
        except Exception:
            continue
    return None


def fetch_image_bytes(stored: str, settings: Settings) -> tuple[bytes, str] | None:
    """Download product photo: Yandex / public URL / Drive via service account."""
    if not (stored or "").strip():
        return None
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=_FETCH_HEADERS) as client:
        sa_first = _drive_service_account_bytes(stored, settings, client)
        if sa_first:
            return sa_first
        for candidate in catalog_image_fetch_urls(stored):
            try:
                response = client.get(candidate)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            mime = _guess_mime(response.content, response.headers.get("content-type", ""))
            if mime and len(response.content) >= 512:
                return response.content, mime
        return _drive_service_account_bytes(stored, settings, client)


def refresh_product_image_cache(settings: Settings, product_id: str, stored: str) -> bool:
    """Try to download and cache; keep old cache on failure."""
    fetched = fetch_image_bytes(stored, settings)
    if fetched is None:
        return read_cached(settings, product_id) is not None
    body, mime = fetched
    write_cached(settings, product_id, body, mime)
    return True


def refresh_all_product_caches(settings: Settings, products: list[tuple[str, str]]) -> tuple[int, int]:
    """Returns (updated, still_missing)."""
    updated = 0
    missing = 0
    for product_id, image_url in products:
        if not (image_url or "").strip():
            missing += 1
            continue
        if refresh_product_image_cache(settings, product_id, image_url):
            updated += 1
        else:
            missing += 1
    return updated, missing


def warm_catalog_image_caches(db, settings: Settings) -> dict:
    rows = db.scalars(select(Product).where(Product.active.is_(True))).all()
    pairs = [(product.id, product.image_url) for product in rows if (product.image_url or "").strip()]
    updated, missing = refresh_all_product_caches(settings, pairs)
    return {"imageCacheUpdated": updated, "imageCacheMissing": missing}


async def warm_catalog_image_caches_async(settings: Settings) -> dict:
    def work() -> dict:
        with SessionLocal() as db:
            return warm_catalog_image_caches(db, settings)

    return await asyncio.to_thread(work)


def schedule_warm_catalog_images(settings: Settings) -> None:
    asyncio.create_task(warm_catalog_image_caches_async(settings))
