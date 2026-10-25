import pytest

from app.catalog.importer import SHEETS, parse_sheet
from app.config import Settings
from app.integrations.google_sheets import GoogleSheets, SheetsError, StockUpdate


class FakeWorksheet:
    def __init__(self, values):
        self.values = values

    def get_all_values(self):
        return self.values


class FakeSpreadsheet:
    def __init__(self, target_values):
        self.target_values = target_values
        self.batch_body = None

    def worksheet(self, title):
        if title == "Клюшки левые":
            return FakeWorksheet(self.target_values)
        return FakeWorksheet([])

    def values_batch_update(self, body):
        self.batch_body = body


def sheet_with_shifted_variant():
    return [
        ["ЛЕВЫЕ", "", "", "", ""],
        ["Название", "Флекс", "Загиб", "Наличие", "Цена"],
        ["", "", "", "", ""],
        ["Bauer Fuse L", "70", "92", "2", "7500"],
    ]


def test_stock_write_resolves_current_row_by_semantic_id() -> None:
    values = sheet_with_shifted_variant()
    variant = parse_sheet(
        "\n".join(",".join(row) for row in values),
        SHEETS[0],
    )[0].variants[0]
    spreadsheet = FakeSpreadsheet(values)
    sheets = GoogleSheets(Settings(_env_file=None))
    sheets._spreadsheet = spreadsheet

    sheets._update_stocks_sync([StockUpdate(variant.id, expected_stock=2, new_stock=1)])

    assert spreadsheet.batch_body["data"] == [
        {"range": "'Клюшки левые'!D4", "values": [[1]]}
    ]


def test_stock_write_rejects_stale_expected_stock() -> None:
    values = sheet_with_shifted_variant()
    variant = parse_sheet(
        "\n".join(",".join(row) for row in values),
        SHEETS[0],
    )[0].variants[0]
    spreadsheet = FakeSpreadsheet(values)
    sheets = GoogleSheets(Settings(_env_file=None))
    sheets._spreadsheet = spreadsheet

    with pytest.raises(SheetsError, match="изменился"):
        sheets._update_stocks_sync([StockUpdate(variant.id, expected_stock=3, new_stock=2)])

    assert spreadsheet.batch_body is None
