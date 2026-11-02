"""Input helpers for the procurement MVP."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_history(path: Path) -> list[float]:
    """Read historical prices from CSV/JSON/XLSX using a small stable contract."""
    suffix = path.suffix.lower()
    values: list[Any] = []
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            values = data
        elif isinstance(data, dict):
            values = data.get("prices", [])
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                values.append(row.get("price", row.get("historical_price")))
    elif suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)
            headers = [str(v).strip().lower() if v is not None else "" for v in next(rows)]
            index = headers.index("price") if "price" in headers else headers.index("historical_price")
            values = [row[index] for row in rows if len(row) > index]
        finally:
            workbook.close()
    else:
        raise ValueError(f"Unsupported history format: {suffix}")
    result: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number >= 0:
            result.append(number)
    return result
