"""Reproducible local acceptance with synthetic files and an explicit demo review."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from procurement_agent.engine import create_review_template
from procurement_agent.reports import write_excel
from procurement_agent.service import run_comparison
from procurement_agent.templates import write_templates


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "output" / date.today().isoformat()
    fixtures = output / "acceptance-inputs"
    write_templates(fixtures, as_of=date(2026, 11, 2))
    source_paths = list(fixtures.glob("*.json")) + list(fixtures.glob("*.xlsx"))
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    normal = run_comparison([fixtures / "quotes.xlsx"], history_paths=[fixtures / "history.xlsx"],
                            market_paths=[fixtures / "market.xlsx"], as_of="2026-11-02")
    assert normal["procurement_decision"]["status"] == "conditional_recommendation"
    assert len(normal["quotes"]) == 9 and len(normal["item_results"]) == 3
    assert all(row["classification"] == "normal" for row in normal["findings"])
    proof = next(row for row in normal["evidence"] if row["field"] == "unit_price_excl_tax")
    original = load_workbook(proof["file"], data_only=False)
    assert original[proof["sheet"]][proof["cell"]].value == proof["raw_value"]
    assert hashlib.sha256(Path(proof["file"]).read_bytes()).hexdigest() == proof["sha256"]
    original.close()

    low_path = fixtures / "quotes-low.json"
    before = run_comparison([low_path], as_of="2026-11-02")
    assert before["procurement_decision"]["status"] == "manual_review_required"
    assert before["recommended_supplier"] is None
    low = next(row for row in before["findings"] if row["classification"] == "abnormally_low")
    review = create_review_template(before)
    review["reviewer"] = "自动验收-模拟复核人"
    review["explanations"] = [{"quote_id": low["quote_id"], "kind": "low_price",
                               "reason": "仅用于自动验收的模拟库存折扣，非真实采购确认",
                               "evidence": "SYNTHETIC-DEMO-CONFIRMATION-001"}]
    reviewed = run_comparison([low_path], as_of="2026-11-02", review=review)
    assert reviewed["procurement_decision"]["status"] == "conditional_recommendation"
    assert next(row for row in reviewed["findings"] if row["quote_id"] == low["quote_id"])["classification"] == "low_explained"
    assert reviewed["audit_log"]
    (output / "acceptance-reviewed-input.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    result_names = []
    for name, result in (("acceptance-normal", normal), ("acceptance-blocked", before), ("acceptance-reviewed", reviewed)):
        (output / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        (output / f"{name}.md").write_text(result["advice_zh"], encoding="utf-8")
        workbook_path = output / f"{name}.xlsx"
        write_excel(result, workbook_path)
        workbook = load_workbook(workbook_path, data_only=False)
        required = {"采购建议", "供应商评分", "报价明细", "风险与确认", "原始证据", "人工复核", "规则配置"}
        assert required <= set(workbook.sheetnames)
        for sheet in workbook:
            assert sheet.freeze_panes
            for row in sheet:
                for cell in row:
                    if cell.value is not None:
                        assert cell.font.name in {"Microsoft YaHei", "微软雅黑"}
                        assert cell.fill.patternType is None
                        assert cell.data_type != "f"
        result_names.append({"file": workbook_path.name, "sheets": len(workbook.sheetnames),
                             "status": result["procurement_decision"]["status"]})
        workbook.close()
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == value for path, value in hashes.items())
    summary = {"status": "passed", "scenarios": result_names, "original_hashes_preserved": True,
               "actual_excel_cell_evidence_verified": True, "synthetic_data_only": True}
    (output / "acceptance-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
