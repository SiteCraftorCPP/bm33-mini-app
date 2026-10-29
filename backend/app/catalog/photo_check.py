from __future__ import annotations

import httpx

from app.catalog.importer import ImportedProduct, catalog_image_fetch_urls
from app.catalog.service import _merged_products

_PROBE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChesHockey/1.0)"}
_MAX_WARNINGS = 40


def _looks_like_image(body: bytes, content_type: str) -> bool:
    if content_type.casefold().startswith("image/"):
        return True
    if len(body) >= 3 and body[:3] == b"\xff\xd8\xff":
        return True
    if len(body) >= 8 and body[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return True
    return False


def photo_fetch_problem(stored: str, client: httpx.Client) -> str | None:
    """None if photo loads; otherwise short reason in Russian."""
    if not (stored or "").strip():
        return "нет ссылки в колонке «Фото»"
    candidates = catalog_image_fetch_urls(stored)
    if not candidates:
        return "ссылка не распознана (нужен Google Drive или Яндекс.Диск)"
    last = "файл недоступен с сервера"
    for url in candidates:
        try:
            response = client.get(url, timeout=20.0, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError:
            last = "сервер не может скачать файл (закрытый Drive или битая ссылка Яндекса)"
            continue
        body = response.content
        content_type = response.headers.get("content-type", "")
        if not _looks_like_image(body, content_type):
            if b"accounts.google.com" in body[:8000] or b"Sign in" in body[:8000]:
                last = "Google Drive просит логин — откройте доступ «все по ссылке» или дайте ссылку Яндекс.Диска"
            else:
                last = "по ссылке приходит не картинка (проверьте в режиме инкognito)"
            continue
        if len(body) < 512:
            last = "файл слишком маленький или пустой"
            continue
        return None
    return last


def catalog_photo_warnings(imported: list[ImportedProduct]) -> list[str]:
    merged = _merged_products(imported)
    warnings: list[str] = []
    with httpx.Client(timeout=25.0, follow_redirects=True, headers=_PROBE_HEADERS) as client:
        for _pid, name, category, _sort, image_url, _variants in merged:
            problem = photo_fetch_problem(image_url, client)
            if problem:
                warnings.append(f"«{name}» ({category}): {problem}")
            if len(warnings) >= _MAX_WARNINGS:
                warnings.append("… показаны не все — исправляйте по списку и синхронизируйте снова")
                return warnings
    return warnings
