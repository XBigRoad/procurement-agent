"""Report projections must preserve the decision gate and original evidence."""

import json
from copy import deepcopy
from datetime import date

import pytest
from openpyxl import load_workbook

from procurement_agent.reports import (
    CLASSIFICATION_NAMES,
    build_advice,
    decision_rows,
    evidence_records,
    report_tables,
    write_excel,
)


@pytest.fixture
def result():
    proof = {
        "quote_id": "q1", "supplier": "合成供应商甲", "field": "unit_price_excl_tax",
        "file": "报价.xlsx", "sha256": "a" * 64, "format": "xlsx", "sheet": "报价",
        "row": 2, "column": 3, "cell": "C2", "raw_value": 80,
    }
    return {
        "schema_version": "1.0", "run_id": "synthetic-run", "input_digest": "d" * 64,
        "generated_at": "2026-11-02T12:00:00+08:00", "as_of": "2026-11-02",
        "weights": {"price": 0.5, "lead_time": 0.3, "payment_terms": 0.2},
        "policy": {"low_threshold": 0.2}, "assumptions": ["运费按每行一次计入。"],
        "input_files": [{"file": "报价.xlsx", "sha256": "a" * 64, "format": "xlsx"}],
        "quotes": [{
            "quote_id": "q1", "supplier": "合成供应商甲", "item_id": "RESIN-01",
            "item_name": "合成树脂", "category": "raw_material", "specification": "128",
            "configuration": "合成配置", "quantity": 10, "unit": "kg", "currency": "CNY",
            "unit_price_excl_tax": 80, "unit_price_incl_tax": 90.4, "tax_rate": 0.13,
            "fees_excl_tax": {"freight": 20}, "normalized_total_excl_tax": 820,
            "normalized_total_incl_tax": 926.6, "lead_time_days": 7, "payment_days": 30,
            "payment_terms": "验收后30天", "warranty_months": 12, "scope_complete": True,
            "raw_fields": {"unit_price_excl_tax": 80}, "evidence": {"unit_price_excl_tax": proof},
        }],
        "rankings": [{
            "quote_id": "q1", "supplier": "合成供应商甲", "item_id": "RESIN-01", "rank": 1,
            "score": 88.75, "price_score": 45.25, "lead_time_score": 23.5,
            "payment_terms_score": 20, "normalized_total_excl_tax": 820, "currency": "CNY",
            "classification": "abnormally_low", "eligible_for_recommendation": False,
            "blockers": ["low_price"],
        }],
        "item_results": [{"item_id": "RESIN-01", "status": "manual_review_required",
                          "candidate_suppliers": ["合成供应商甲"], "recommended_supplier": None}],
        "findings": [{
            "quote_id": "q1", "supplier": "合成供应商甲", "item_id": "RESIN-01",
            "classification": "abnormally_low", "status": "review_required",
            "reasons": ["报价低于有效历史参考"], "flags": ["low_price"],
            "peer_median": 1000, "peer_delta": -0.18,
            "history_median": 1100, "history_delta": -0.254545,
            "supplier_history_median": 1050, "supplier_history_delta": -0.219048,
            "market_median": 1080, "market_delta": -0.240741,
            "reference_ids": {"peer": ["q1", "q2"], "history": ["h1"],
                              "supplier_history": ["sh1"], "market": ["m1"]},
        }],
        "issues": [{"quote_id": "q1", "item_id": "RESIN-01", "supplier": "合成供应商甲",
                    "severity": "blocker", "code": "low_price", "field": "price",
                    "message": "低价证据尚未确认", "question": "请提供盖章的完整报价说明。"}],
        "evidence": [proof],
        "reference_exclusions": [{"reference_id": "old-market", "reason": "市场参考已过期"}],
        "audit_log": [{"quote_id": "q1", "reviewer": "合成审核员", "reviewed_at": "2026-11-02",
                       "field": "freight", "before": None, "after": 20,
                       "reason": "补充运输费", "evidence": "合成附件A第1页"}],
        "procurement_decision": {
            "status": "manual_review_required", "recommended_supplier": None,
            "candidate_supplier": "合成供应商甲", "candidate_suppliers": ["合成供应商甲"],
            "blocking_flags": ["low_price"], "reason": "低价证据尚未确认。",
        },
        "recommended_supplier": None,
    }


def _output(tmp_path):
    return tmp_path / date.today().isoformat() / "审核.xlsx"


def test_blocked_rank_is_only_a_candidate(result):
    # Deliberately inconsistent mirrors prove the batch decision is authoritative.
    result["recommended_supplier"] = "错误的顶层镜像"
    result["item_results"][0]["recommended_supplier"] = "错误的分项镜像"
    rows = decision_rows(result)
    assert all(row["推荐供应商"] is None for row in rows)
    advice = build_advice(result)
    assert "候选供应商：合成供应商甲" in advice
    assert "推荐供应商：暂不形成推荐" in advice
    assert "错误的顶层镜像" not in advice
    assert "错误的分项镜像" not in advice


def test_explicit_recommendation_does_not_follow_rank(result):
    result["procurement_decision"].update(
        status="conditional_recommendation", recommended_supplier="具名推荐供应商乙",
        blocking_flags=[],
    )
    assert decision_rows(result)[0]["推荐供应商"] == "具名推荐供应商乙"
    assert "推荐供应商：具名推荐供应商乙" in build_advice(result)
    result["procurement_decision"]["recommended_supplier"] = None
    assert decision_rows(result)[0]["推荐供应商"] is None


def test_multiple_item_winners_remain_separate(result):
    result["procurement_decision"].update(status="conditional_recommendation", blocking_flags=[])
    result["item_results"] = [
        {"item_id": "M1", "status": "conditional_recommendation", "recommended_supplier": "甲"},
        {"item_id": "M2", "status": "conditional_recommendation", "recommended_supplier": "乙"},
    ]
    assert [row["推荐供应商"] for row in decision_rows(result)] == [None, "甲", "乙"]


def test_advice_sections_values_and_five_classifications(result):
    result["findings"] = [dict(result["findings"][0], classification=value)
                          for value in CLASSIFICATION_NAMES]
    advice = build_advice(result)
    for section in ("结论", "事实", "计算", "假设", "风险", "建议", "待确认问题", "证据"):
        assert f"【{section}】" in advice
    for display in CLASSIFICATION_NAMES.values():
        assert display in advice
    assert "88.75" in advice and "45.25" in advice
    assert "盖章的完整报价说明" in advice
    assert "市场参考已过期" in advice
    assert "d" * 64 in advice and "a" * 64 in advice


def test_exports_are_pure_projections(result, tmp_path):
    original = deepcopy(result)
    write_excel(result, _output(tmp_path))
    build_advice(result)
    report_tables(result)
    assert result == original


def test_workbook_structure_style_numbers_and_blocked_decision(result, tmp_path):
    target = _output(tmp_path)
    write_excel(result, target)
    with target.open("rb") as stream:
        workbook = load_workbook(stream)
        assert workbook.sheetnames == [
            "采购建议", "供应商评分", "报价明细", "字段对照", "计算明细", "风险与确认",
            "价格参考", "参考明细", "参考排除", "原始证据", "人工复核", "规则配置", "输入文件",
        ]
        for sheet in workbook:
            assert sheet.freeze_panes == "A2"
            assert sheet.auto_filter.ref == sheet.dimensions
            assert all(14 <= column.width <= 48 for column in sheet.column_dimensions.values())
            for row in sheet:
                for cell in row:
                    assert cell.font.name == "Microsoft YaHei"
                    assert cell.fill.patternType is None
                    assert cell.data_type != "f"
        scores = workbook["供应商评分"]
        headers = [cell.value for cell in scores[1]]
        assert scores.cell(2, headers.index("综合评分") + 1).value == 88.75
        assert scores.cell(2, headers.index("价格加权得分") + 1).value == 45.25
        quotes = workbook["报价明细"]
        headers = [cell.value for cell in quotes[1]]
        tax = quotes.cell(2, headers.index("税率") + 1)
        assert tax.value == 0.13 and tax.number_format == "0.00%"
        for row in workbook["采购建议"].iter_rows(values_only=True):
            if row[0] == "推荐供应商":
                assert row[2] is None
        workbook.close()


@pytest.mark.parametrize("payload", ["=1+2", "+SUM(A1:A2)", "-1+2", "@SUM(A1)",
                                    '=HYPERLINK("https://example.invalid", "x")', "#N/A"])
def test_excel_preserves_formula_like_strings_as_literal_text(result, tmp_path, payload):
    result["evidence"][0]["raw_value"] = payload
    result["evidence"][0]["formula"] = payload
    result["quotes"][0]["supplier"] = payload
    write_excel(result, _output(tmp_path))
    workbook = load_workbook(_output(tmp_path), data_only=False)
    sheet = workbook["原始证据"]
    headers = [cell.value for cell in sheet[1]]
    for name in ("原始值", "原始公式文本"):
        cell = sheet.cell(2, headers.index(name) + 1)
        assert cell.value == payload
        assert cell.data_type == "s"
        assert cell.hyperlink is None
    assert all(cell.data_type != "f" for sheet in workbook for row in sheet for cell in row)
    workbook.close()


def test_original_evidence_reference_matches_and_review_audit(result):
    result["quotes"][0]["unit_price_excl_tax"] = 99
    tables = report_tables(result)
    headers, rows = tables["原始证据"]
    assert rows[0][headers.index("原始值")] == 80
    assert rows[0][headers.index("原始单元格")] == "C2"
    headers, rows = tables["价格参考"]
    assert rows[0][headers.index("公司采购历史引用标识")] == ["h1"]
    assert rows[0][headers.index("同供应商历史引用标识")] == ["sh1"]
    assert rows[0][headers.index("市场参考引用标识")] == ["m1"]
    headers, rows = tables["人工复核"]
    assert rows[0][headers.index("修改前")] is None
    assert rows[0][headers.index("修改后")] == 20
    assert rows[0][headers.index("证据引用")] == "合成附件A第1页"


def test_evidence_can_be_projected_from_quote_mapping(result):
    result.pop("evidence")
    records = evidence_records(result)
    assert records[0]["field"] == "unit_price_excl_tax"
    assert records[0]["raw_value"] == 80
    assert records[0]["cell"] == "C2"


def test_corrected_fields_and_calculation_steps_remain_traceable_in_excel(result, tmp_path):
    quote = result["quotes"][0]
    quote["unit_price_excl_tax"] = 99
    quote["effective_fields"] = {"unit_price_excl_tax": 99, "freight": 20}
    quote["reviewed_fields"] = {
        "unit_price_excl_tax": {
            "before": 80, "after": 99, "reviewer": "合成复核员",
            "reviewed_at": "2026-11-02T12:00:00+08:00", "reason": "核实单价",
            "evidence": "合成附件第1页",
        },
    }
    quote["calculation_steps"] = ["未税总成本 = 99 × 10 + 20", "此步骤直接引用引擎"]
    result["reference_records"] = [{
        "quote_id": "h1", "supplier": "合成历史供应商", "item_id": "RESIN-01",
        "reference_role": "history", "record_type": "purchase", "record_date": "2026-10-02",
        "normalized_total_excl_tax": 1100, "matched_quote_ids": ["q1"],
        "source": {"file": "历史.json", "sha256": "b" * 64},
        "raw_fields": {"price": 1100}, "calculation_steps": ["历史价格换算步骤"],
    }]
    original = deepcopy(result)
    target = _output(tmp_path)
    write_excel(result, target)
    workbook = load_workbook(target)
    try:
        def records(sheet_name):
            header, *rows = list(workbook[sheet_name].values)
            return [dict(zip(header, row, strict=True)) for row in rows]

        fields = {row["字段"]: row for row in records("字段对照")}
        price = fields["unit_price_excl_tax"]
        assert price["原始业务值"] == 80
        assert price["本次有效值"] == 99
        assert price["标准化结果"] == 99
        assert price["已人工修正"] is True
        assert price["复核人"] == "合成复核员"
        assert price["证据引用"] == "合成附件第1页"
        assert fields["freight"]["原始已提供"] is False
        assert fields["freight"]["原始业务值"] is None
        assert fields["freight"]["本次有效值"] == 20
        assert records("原始证据")[0]["原始值"] == 80
        steps = records("计算明细")
        assert [row["计算步骤原文"] for row in steps] == [
            *quote["calculation_steps"], "历史价格换算步骤",
        ]
        reference = records("参考明细")[0]
        assert reference["报价标识"] == "h1"
        assert reference["统一口径未税总额"] == 1100
        assert json.loads(reference["匹配报价标识"]) == ["q1"]
        assert json.loads(reference["来源元数据"])["sha256"] == "b" * 64
        assert result == original
    finally:
        workbook.close()


@pytest.mark.parametrize("payload", ["x" * 32768, "contains\x00control"])
def test_excel_rejects_unrepresentable_evidence_instead_of_truncating(result, tmp_path, payload):
    result["evidence"][0]["raw_value"] = payload
    with pytest.raises(ValueError, match="Excel.*无法完整保存"):
        write_excel(result, _output(tmp_path))
    assert not _output(tmp_path).exists()
    assert json.loads(json.dumps(result))["evidence"][0]["raw_value"] == payload


def test_empty_result_has_safe_decision_and_export(tmp_path):
    assert decision_rows({})[0]["推荐供应商"] is None
    write_excel({}, _output(tmp_path))
    workbook = load_workbook(_output(tmp_path))
    assert workbook["原始证据"].max_row == 1
    assert "待人工复核" in build_advice({})
    workbook.close()
