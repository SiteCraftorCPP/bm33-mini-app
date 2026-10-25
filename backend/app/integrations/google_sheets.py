from __future__ import annotations

import asyncio
import csv
import io
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.catalog.importer import CatalogDataError, SHEETS, ImportedProduct, ImportedVariant, parse_sheet
from app.config import Settings


class SheetsError(RuntimeError):
    pass


@dataclass(frozen=True)
class StockUpdate:
    variant_id: str
    expected_stock: int
    new_stock: int
    sheet_gid: str = ""
    sheet_row: int = 0
    stock_column: int = 0


_CATALOG_CACHE_TTL_SECONDS = 50


class GoogleSheets:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._spreadsheet = None
        self._write_lock = threading.Lock()
        self._catalog_cache: list[ImportedProduct] | None = None
        self._catalog_cache_at: float = 0.0

    @property
    def can_write(self) -> bool:
        path = self.settings.google_service_account_file.strip()
        if not path:
            return False
        try:
            return os.path.isfile(path) and os.access(path, os.R_OK)
        except OSError:
            return False

    def invalidate_catalog_cache(self) -> None:
        self._catalog_cache = None
        self._catalog_cache_at = 0.0

    async def fetch_catalog(self, *, force: bool = False) -> list[ImportedProduct]:
        if self.can_write:
            try:
                return await asyncio.to_thread(self._fetch_catalog_authorized_sync, force)
            except CatalogDataError as exc:
                raise SheetsError(str(exc)) from exc
            except SheetsError:
                raise
            except Exception as exc:
                raise SheetsError(f"Не удалось прочитать Google Sheets через service account: {exc}") from exc

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            requests = [
                client.get(
                    f"https://docs.google.com/spreadsheets/d/{self.settings.google_sheet_id}/export",
                    params={"format": "csv", "gid": definition.gid},
                )
                for definition in SHEETS
            ]
            responses = await asyncio.gather(*requests)

        products: list[ImportedProduct] = []
        sort_offset = 0
        for definition, response in zip(SHEETS, responses, strict=True):
            if response.status_code != 200:
                raise SheetsError(f"Не удалось прочитать «{definition.title}»: HTTP {response.status_code}")
            try:
                parsed = parse_sheet(response.text, definition, sort_offset)
            except CatalogDataError as exc:
                raise SheetsError(str(exc)) from exc
            products.extend(parsed)
            sort_offset += len(parsed)
        if not products:
            raise SheetsError("Google Sheets вернул пустой каталог")
        return products

    async def update_stocks(self, updates: list[StockUpdate]) -> None:
        """Write stock cells. Uses DB row coordinates when provided (no full-sheet read)."""
        if not updates:
            return
        if not self.can_write:
            if self.settings.demo_mode:
                return
            raise SheetsError("Не настроен GOOGLE_SERVICE_ACCOUNT_FILE")
        try:
            await asyncio.to_thread(self._update_stocks_sync, updates)
        except SheetsError:
            raise
        except Exception as exc:
            raise SheetsError(f"Не удалось обновить остатки: {exc}") from exc
        finally:
            self.invalidate_catalog_cache()

    def _spreadsheet_client(self):
        import gspread

        if self._spreadsheet is None:
            client = gspread.service_account(filename=self.settings.google_service_account_file)
            self._spreadsheet = client.open_by_key(self.settings.google_sheet_id)
        return self._spreadsheet

    def _worksheet_csv(self, worksheet) -> str:
        output = io.StringIO(newline="")
        csv.writer(output).writerows(worksheet.get_all_values())
        return output.getvalue()

    def _call_with_backoff(self, action, *, attempts: int = 5):
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return action()
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if "429" not in message and "quota" not in message and "rate" not in message:
                    raise
                time.sleep(min(2 ** attempt, 32))
        if last_error:
            raise last_error
        raise SheetsError("Не удалось выполнить запрос к Google Sheets")

    def _fetch_catalog_authorized_sync(self, force: bool = False) -> list[ImportedProduct]:
        now = time.monotonic()
        if (
            not force
            and self._catalog_cache is not None
            and now - self._catalog_cache_at < _CATALOG_CACHE_TTL_SECONDS
        ):
            return self._catalog_cache

        with self._write_lock:
            spreadsheet = self._spreadsheet_client()
            products: list[ImportedProduct] = []
            sort_offset = 0
            for definition in SHEETS:
                worksheet = self._call_with_backoff(lambda d=definition: spreadsheet.worksheet(d.title))
                parsed = parse_sheet(
                    self._call_with_backoff(lambda w=worksheet: self._worksheet_csv(w)),
                    definition,
                    sort_offset,
                )
                products.extend(parsed)
                sort_offset += len(parsed)
            if not products:
                raise SheetsError("Google Sheets вернул пустой каталог")
            self._catalog_cache = products
            self._catalog_cache_at = time.monotonic()
            return products

    def _update_stocks_sync(self, updates: list[StockUpdate]) -> None:
        with self._write_lock:
            spreadsheet = self._spreadsheet_client()
            definitions = {definition.gid: definition for definition in SHEETS}

            if all(update.sheet_row and update.stock_column and update.sheet_gid for update in updates):
                self._update_stocks_targeted(spreadsheet, definitions, updates)
                return

            variants: dict[str, ImportedVariant] = {}
            for definition in SHEETS:
                worksheet = self._call_with_backoff(lambda d=definition: spreadsheet.worksheet(d.title))
                products = parse_sheet(
                    self._call_with_backoff(lambda w=worksheet: self._worksheet_csv(w)),
                    definition,
                )
                for product in products:
                    for variant in product.variants:
                        if variant.id in variants:
                            raise SheetsError(
                                f"В таблице найдено несколько строк для варианта {variant.label}"
                            )
                        variants[variant.id] = variant

            missing = [update.variant_id for update in updates if update.variant_id not in variants]
            if missing:
                raise SheetsError(
                    "Вариант был перемещён, переименован или удалён. Обновите корзину и повторите заказ."
                )

            batch_data = []
            for update in updates:
                variant = variants[update.variant_id]
                if variant.stock != update.expected_stock:
                    raise SheetsError(
                        f"Остаток варианта {variant.label} изменился: "
                        f"было {update.expected_stock}, сейчас {variant.stock}. Повторите заказ."
                    )
                title = definitions[variant.sheet_gid].title.replace("'", "''")
                batch_data.append(
                    {
                        "range": (
                            f"'{title}'!"
                            f"{_column_name(variant.stock_column)}{variant.sheet_row}"
                        ),
                        "values": [[max(update.new_stock, 0)]],
                    }
                )

            self._call_with_backoff(
                lambda: spreadsheet.values_batch_update(
                    {
                        "valueInputOption": "USER_ENTERED",
                        "data": batch_data,
                    }
                )
            )

    def _update_stocks_targeted(
        self,
        spreadsheet,
        definitions: dict[str, object],
        updates: list[StockUpdate],
    ) -> None:
        ranges = []
        for update in updates:
            definition = definitions.get(update.sheet_gid)
            if definition is None:
                raise SheetsError("Лист таблицы для варианта не найден")
            title = definition.title.replace("'", "''")
            ranges.append(
                f"'{title}'!{_column_name(update.stock_column)}{update.sheet_row}"
            )

        response = self._call_with_backoff(lambda: spreadsheet.values_batch_get(ranges))
        value_ranges = response.get("valueRanges", [])
        if len(value_ranges) != len(updates):
            raise SheetsError("Не удалось проверить остатки в таблице")

        batch_data = []
        for update, value_range in zip(updates, value_ranges, strict=True):
            values = value_range.get("values", [[0]])
            current = _cell_int(values[0][0] if values and values[0] else 0)
            if current != update.expected_stock:
                raise SheetsError(
                    f"Остаток в таблице изменился (ожидали {update.expected_stock}, сейчас {current}). "
                    "Обновите каталог и повторите заказ."
                )
            definition = definitions[update.sheet_gid]
            title = definition.title.replace("'", "''")
            batch_data.append(
                {
                    "range": (
                        f"'{title}'!"
                        f"{_column_name(update.stock_column)}{update.sheet_row}"
                    ),
                    "values": [[max(update.new_stock, 0)]],
                }
            )

        self._call_with_backoff(
            lambda: spreadsheet.values_batch_update(
                {
                    "valueInputOption": "USER_ENTERED",
                    "data": batch_data,
                }
            )
        )


def _cell_int(raw) -> int:
    if raw is None or raw == "":
        return 0
    try:
        return int(float(str(raw).replace(",", ".").strip()))
    except ValueError:
        return 0


def _column_name(column: int) -> str:
    result = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        result = chr(65 + remainder) + result
    return result

