"""Synthetic, editable templates; no company or real supplier data is embedded."""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path


def demo_quotes(as_of: date | None = None) -> list[dict]:
    today = as_of or date.today()
    rows = []
    categories = [
        ("raw_material", "RM-DEMO", "演示树脂", "R-TEST-128", "", "kg", 1000, 100, 0),
        ("mold", "MD-DEMO", "演示注塑模具", "M-TEST-2", "钢材P20；2型腔；设计寿命30万模次", "set", 1, 20000, 12),
        ("equipment", "EQ-DEMO", "演示检测设备", "E-TEST-01", "主机+软件+安装调试+培训", "unit", 1, 50000, 12),
    ]
    for category, item_id, name, spec, config, unit, quantity, price, warranty in categories:
        for index, supplier in enumerate(("模拟供应商A", "模拟供应商B", "模拟供应商C")):
            payment = (30, 60, 30)[index]
            rows.append({
                "supplier": supplier, "item_id": item_id, "item_name": name,
                "category": category, "specification": spec, "configuration": config,
                "quantity": quantity, "unit": unit, "currency": "CNY",
                "unit_price_excl_tax": round(price * (1 + index * 0.04), 4),
                "tax_rate": "13%", "freight": 1000 if category == "equipment" else 0,
                "installation": 2000 if category == "equipment" else 0,
                "fee_basis": "excl_tax", "freight_tax_rate": "9%", "installation_tax_rate": "6%",
                "lead_time_days": (7, 10, 12)[index], "payment_days": payment,
                "payment_terms": f"验收后{payment}天付款", "payment_anchor": "acceptance",
                "prepayment_percent": 0, "warranty_months": warranty, "scope_complete": True,
                "quote_date": today.isoformat(), "valid_until": (today + timedelta(days=30)).isoformat(),
                "notes": "纯模拟验收数据；价格不代表真实采购价或市场行情",
            })
    return rows


def demo_references(quotes: list[dict], as_of: date | None = None) -> tuple[list[dict], list[dict]]:
    today = as_of or date.today()
    history, market = [], []
    for quote in quotes:
        if quote["supplier"] == "模拟供应商A":
            purchase = copy.deepcopy(quote)
            purchase.update(record_type="purchase", record_date=(today - timedelta(days=30)).isoformat())
            purchase["unit_price_excl_tax"] *= 1.02
            history.append(purchase)
            reference = copy.deepcopy(purchase)
            reference.update(supplier="模拟市场来源", record_type="market", record_date=(today - timedelta(days=3)).isoformat())
            market.append(reference)
        prior_quote = copy.deepcopy(quote)
        prior_quote.update(record_type="quotation", record_date=(today - timedelta(days=20)).isoformat())
        prior_quote["unit_price_excl_tax"] *= 1.01
        history.append(prior_quote)
    return history, market


def _write_workbook(rows: list[dict], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "输入模板"
    fields = list(dict.fromkeys(field for row in rows for field in row))
    sheet.append(fields)
    for row in rows:
        sheet.append([row.get(field) for field in fields])
    for cells in sheet:
        for cell in cells:
            cell.font = Font(name="Microsoft YaHei", size=10, bold=cell.row == 1)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if isinstance(cell.value, str):
                cell.data_type = "s"
    for index, field in enumerate(fields, 1):
        sheet.column_dimensions[get_column_letter(index)].width = 34 if field in {"notes", "configuration"} else 24
    sheet.row_dimensions[1].height = 32
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = sheet.dimensions
    workbook.save(path)
    workbook.close()


def write_templates(directory: Path, *, as_of: date | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    quotes = demo_quotes(as_of)
    history, market = demo_references(quotes, as_of)
    for name, rows in (("quotes", quotes), ("history", history), ("market", market)):
        (directory / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_workbook(rows, directory / f"{name}.xlsx")
    risk = copy.deepcopy(quotes[:3])
    risk[2]["unit_price_excl_tax"] = 55
    (directory / "quotes-low.json").write_text(json.dumps(risk, ensure_ascii=False, indent=2), encoding="utf-8")
