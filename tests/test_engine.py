import copy
import json
from datetime import date
from decimal import Decimal

import pytest

from procurement_agent.engine import compare_records, create_review_template
from procurement_agent.ingest import load_records
from procurement_agent.normalization import decimal_value
from procurement_agent.scoring import score_candidates, validate_weights
from procurement_agent.templates import demo_quotes, demo_references

AS_OF = "2026-11-02"


def sourced(tmp_path, rows, name="quotes.json"):
    path = tmp_path / name
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return load_records(path)


def base_rows():
    return demo_quotes(date.fromisoformat(AS_OF))[:3]


def run(tmp_path, rows=None, history=None, market=None, **kwargs):
    records = sourced(tmp_path, base_rows() if rows is None else rows)
    return compare_records(records, history=sourced(tmp_path, history, "history.json") if history else [],
                           market=sourced(tmp_path, market, "market.json") if market else [], as_of=AS_OF, **kwargs)


def assert_blocked(result, code=None):
    assert result["procurement_decision"]["status"] == "manual_review_required"
    assert result["recommended_supplier"] is None
    assert result["procurement_decision"]["recommended_supplier"] is None
    assert all(item["recommended_supplier"] is None for item in result["item_results"])
    assert all(not row["eligible_for_recommendation"] for row in result["rankings"])
    if code:
        assert code in result["procurement_decision"]["blocking_flags"]


def test_normal_three_categories_with_all_reference_families(tmp_path):
    rows = demo_quotes(date.fromisoformat(AS_OF))
    history, market = demo_references(rows, date.fromisoformat(AS_OF))
    result = run(tmp_path, rows, history, market)
    assert result["procurement_decision"]["status"] == "conditional_recommendation"
    assert len(result["item_results"]) == 3
    assert result["recommended_supplier"] == "模拟供应商A"
    assert all(f["classification"] == "normal" for f in result["findings"])
    assert all(f["history_median"] and f["supplier_history_median"] and f["market_median"] for f in result["findings"])
    equipment = next(q for q in result["quotes"] if q["item_id"] == "EQ-DEMO")
    assert equipment["normalized_total_excl_tax"] == 53000
    assert equipment["normalized_total_incl_tax"] == 59710
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("count", [2, 5, 12])
def test_supplier_scale(tmp_path, count):
    rows = []
    for index in range(count):
        row = copy.deepcopy(base_rows()[0])
        row.update(supplier=f"供应商{index:02}", unit_price_excl_tax=100 + index / 2,
                   lead_time_days=7 + index)
        rows.append(row)
    result = run(tmp_path, rows)
    assert len(result["rankings"]) == count
    assert result["recommended_supplier"] == "供应商00"


@pytest.mark.parametrize("field,value", [
    ("specification", "R-TEST-129"), ("quantity", 999), ("unit", "t"),
    ("currency", "USD"), ("configuration", "额外组件"), ("brand", "不同品牌"),
    ("payment_anchor", "invoice"), ("category", "equipment"),
])
def test_incomparable_never_ranked(tmp_path, field, value):
    rows = base_rows()
    rows[2][field] = value
    result = run(tmp_path, rows)
    assert_blocked(result, "not_comparable")
    assert not result["rankings"]


@pytest.mark.parametrize("field", ["freight", "installation", "tax_rate", "warranty_months", "payment_days", "specification"])
def test_missing_fields_block(tmp_path, field):
    rows = base_rows()
    rows[0].pop(field)
    result = run(tmp_path, rows)
    assert_blocked(result, "missing_field")
    if field in {"freight", "installation", "tax_rate"}:
        assert result["quotes"][0]["normalized_total_excl_tax"] is None


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", -1, 0, True, "￥1OO", "1,23"])
def test_invalid_price_never_safe(tmp_path, value):
    rows = base_rows()
    rows[0]["unit_price_excl_tax"] = value
    result = run(tmp_path, rows)
    assert_blocked(result)
    json.dumps(result, allow_nan=False)


def test_tax_and_total_conflicts(tmp_path):
    rows = base_rows()
    rows[0]["unit_price_incl_tax"] = 120
    rows[0]["total_price_excl_tax"] = 90000
    result = run(tmp_path, rows)
    assert_blocked(result, "tax_price_conflict")
    assert "quantity_price_conflict" in result["procurement_decision"]["blocking_flags"]


def test_gross_conversion_and_per_fee_tax(tmp_path):
    rows = base_rows()
    rows[0].pop("unit_price_excl_tax")
    rows[0].update(unit_price_incl_tax=113, freight=109, installation=106,
                   fee_basis="incl_tax", freight_tax_rate="9%", installation_tax_rate="6%")
    result = run(tmp_path, rows)
    assert result["quotes"][0]["normalized_total_excl_tax"] == 100200
    assert result["quotes"][0]["normalized_total_incl_tax"] == 113215


def test_nonzero_fee_needs_explicit_own_tax(tmp_path):
    rows = base_rows()
    rows[0].update(freight=100)
    rows[0].pop("freight_tax_rate")
    result = run(tmp_path, rows)
    assert_blocked(result, "missing_field")
    assert result["quotes"][0]["normalized_total_excl_tax"] is None


def test_low_price_has_no_recommendation_in_any_projection(tmp_path):
    rows = base_rows()
    rows[2]["unit_price_excl_tax"] = 55
    result = run(tmp_path, rows)
    assert_blocked(result, "unusually_low_vs_peer")
    assert result["candidate_supplier"] == "模拟供应商C"
    assert result["findings"][2]["classification"] == "abnormally_low"


def test_historical_only_low_price_is_blocked(tmp_path):
    rows = base_rows()
    for row in rows:
        row["unit_price_excl_tax"] *= 0.5
    reference = copy.deepcopy(base_rows()[0])
    reference.update(record_type="purchase", record_date="2026-10-01")
    result = run(tmp_path, rows, history=[reference])
    assert_blocked(result, "unusually_low_vs_history")
    assert all(f["classification"] == "abnormally_low" for f in result["findings"])


def test_unrelated_stale_future_and_wrong_unit_references_excluded(tmp_path):
    reference = copy.deepcopy(base_rows()[0])
    reference.update(record_type="purchase", record_date="2026-10-01", unit_price_excl_tax=10000)
    bad = []
    for changes in ({"item_id": "OTHER"}, {"unit": "t"}, {"record_date": "2020-01-01"}, {"record_date": "2027-01-01"}):
        bad.append({**reference, **changes})
    market = {**reference, "record_date": "2026-01-01"}
    result = run(tmp_path, history=bad, market=[market])
    assert len(result["reference_exclusions"]) == 5
    assert all(f["history_median"] is None for f in result["findings"])
    assert result["recommended_supplier"] == "模拟供应商A"


def test_human_explanation_recomputes_and_is_bound_to_input(tmp_path):
    rows = base_rows()
    rows[2]["unit_price_excl_tax"] = 55
    records = sourced(tmp_path, rows)
    before = compare_records(records, as_of=AS_OF)
    review = create_review_template(before)
    review["reviewer"] = "模拟采购审核人"
    review["explanations"] = [{"quote_id": records[2]["quote_id"], "kind": "low_price",
                               "reason": "测试：库存清理折扣已书面确认，规格及范围一致", "evidence": "模拟确认函 DEMO-001"}]
    after = compare_records(records, as_of=AS_OF, review=review)
    assert after["findings"][2]["classification"] == "low_explained"
    assert after["recommended_supplier"] == "模拟供应商C"
    assert after["input_digest"] == before["input_digest"]
    assert after["run_id"] != before["run_id"]
    assert after["audit_log"][0]["reviewer"] == review["reviewer"]
    with pytest.raises(ValueError, match="不匹配"):
        compare_records(records, as_of=AS_OF, review=review, weights={"price": .6, "lead_time": .3, "payment_terms": .1})


def test_review_correction_keeps_original_and_recalculates(tmp_path):
    rows = base_rows()
    rows[0]["freight"] = None
    records = sourced(tmp_path, rows)
    before = compare_records(records, as_of=AS_OF)
    review = create_review_template(before)
    review["reviewer"] = "模拟审核人"
    review["corrections"] = [{"quote_id": records[0]["quote_id"], "field": "freight", "value": 0,
                             "reason": "运费已含", "evidence": "模拟书面确认 DEMO-002"}]
    after = compare_records(records, as_of=AS_OF, review=review)
    assert before["quotes"][0]["normalized_total_excl_tax"] is None
    assert after["quotes"][0]["normalized_total_excl_tax"] == 100000
    assert after["quotes"][0]["raw_fields"]["freight"] is None
    assert after["quotes"][0]["effective_fields"]["freight"] == 0
    assert after["audit_log"][0]["before"] is None
    assert after["audit_log"][0]["after"] == 0
    assert after["recommended_supplier"] == "模拟供应商A"


def test_explanation_cannot_clear_missing_scope(tmp_path):
    rows = base_rows()
    rows[2].update(unit_price_excl_tax=55, scope_complete=False)
    records = sourced(tmp_path, rows)
    result = compare_records(records, as_of=AS_OF)
    review = create_review_template(result)
    review.update(reviewer="测试审核人", explanations=[{"quote_id": records[2]["quote_id"], "kind": "low_price",
                   "reason": "测试低价原因", "evidence": "测试证明"}])
    assert_blocked(compare_records(records, as_of=AS_OF, review=review), "scope_incomplete")


def test_premium_requires_evidence(tmp_path):
    rows = base_rows()
    rows[2].update(unit_price_excl_tax=150, warranty_months=36)
    records = sourced(tmp_path, rows)
    result = compare_records(records, as_of=AS_OF)
    assert_blocked(result, "unexplained_premium")
    review = create_review_template(result)
    review.update(reviewer="测试审核人", explanations=[{"quote_id": records[2]["quote_id"], "kind": "premium",
                   "reason": "三年延保含人工与备件，价值已核实", "evidence": "模拟延保条款"}])
    after = compare_records(records, as_of=AS_OF, review=review)
    assert after["findings"][2]["classification"] == "high_explained"


def test_duplicate_supplier_and_duplicate_file_rejected(tmp_path):
    rows = base_rows()
    rows.append(copy.deepcopy(rows[0]))
    assert_blocked(run(tmp_path, rows), "duplicate_supplier_item")
    records = sourced(tmp_path, base_rows())
    with pytest.raises(ValueError, match="重复输入"):
        compare_records(records + records, as_of=AS_OF)


def test_tie_does_not_auto_pick_alphabetical_supplier(tmp_path):
    rows = [copy.deepcopy(base_rows()[0]) for _ in range(2)]
    rows[1]["supplier"] = "另一个供应商"
    result = run(tmp_path, rows)
    assert_blocked(result, "tied_top_score")
    assert [r["rank"] for r in result["rankings"]] == [1, 1]


@pytest.mark.parametrize("weights", [
    {"price": "nan", "lead_time": .3, "payment_terms": .2},
    {"price": True, "lead_time": 0, "payment_terms": 0},
    {"price": .5, "lead_time": .2, "payment_terms": .2},
    {"price": .5, "lead_time": .3, "payment_terms": .2, "hidden": 0},
])
def test_invalid_weights_rejected(weights):
    with pytest.raises(ValueError):
        validate_weights(weights)


def test_zero_day_delivery_and_zero_payment_are_finite(tmp_path):
    rows = base_rows()
    for row in rows:
        row.update(payment_days=0, payment_terms="验收后0天付款", lead_time_days=0)
    result = run(tmp_path, rows)
    assert result["rankings"][0]["score"] == 100
    json.dumps(result, allow_nan=False)


def test_scoring_matches_reference_ratios():
    rows = [dict(quote_id=str(index), supplier=str(index), item_id="item", currency="CNY", normalized_total_excl_tax=price,
                 lead_time_days=lead, payment_days=days) for index, (price, lead, days) in enumerate([(100, 7, 30), (104, 10, 60)])]
    result = score_candidates(rows, validate_weights(None))
    assert result[0]["score"] == 90
    assert result[1]["score"] == pytest.approx(100 / 104 * 50 + 7 / 10 * 30 + 20, abs=1e-6)
    assert decimal_value("1,000.25") == Decimal("1000.25")


def test_expired_and_complex_terms_blocked(tmp_path):
    rows = base_rows()
    rows[0].update(valid_until="2026-11-01", payment_terms="预付30%，验收后30天支付尾款")
    result = run(tmp_path, rows)
    assert_blocked(result, "expired_quote")
    assert "complex_payment_terms" in result["procurement_decision"]["blocking_flags"]


def test_full_package_missing_item(tmp_path):
    rows = demo_quotes(date.fromisoformat(AS_OF))
    rows.pop()
    result = run(tmp_path, rows, policy={"require_full_package": True})
    assert_blocked(result, "missing_package_items")


@pytest.mark.parametrize("anchor", ["banana", "invoice"])
def test_payment_anchor_cannot_contradict_terms(tmp_path, anchor):
    rows = base_rows()
    for row in rows:
        row["payment_anchor"] = anchor
    result = run(tmp_path, rows)
    assert_blocked(result, "unknown_payment_anchor" if anchor == "banana" else "payment_anchor_conflict")


def test_declared_incomparability_is_preserved(tmp_path):
    rows = base_rows()
    rows[0]["comparable"] = False
    assert_blocked(run(tmp_path, rows), "not_comparable")


def test_extreme_decimal_is_rejected_without_crashing(tmp_path):
    rows = base_rows()
    rows[0]["quantity"] = "1e-99999999"
    rows[0]["total_price_excl_tax"] = "1e15"
    assert_blocked(run(tmp_path, rows), "invalid_number")


def test_current_quote_cannot_contaminate_history(tmp_path):
    rows = base_rows()
    for row in rows:
        row["unit_price_excl_tax"] *= 0.5
    records = sourced(tmp_path, rows)
    historical = {**base_rows()[0], "record_type": "purchase", "record_date": "2026-10-01"}
    history = sourced(tmp_path, [historical], "history.json")
    result = compare_records(records, history=history + records, as_of=AS_OF)
    assert_blocked(result, "unusually_low_vs_history")
    assert result["findings"][0]["history_median"] == 100000
    assert len(result["reference_exclusions"]) == 3
    assert all("本批报价" in item["reason"] for item in result["reference_exclusions"])


@pytest.mark.parametrize("scope", [False, None, ""])
def test_incomplete_reference_cannot_clear_historical_low_block(tmp_path, scope):
    rows = base_rows()
    for row in rows:
        row["unit_price_excl_tax"] *= 0.5
    genuine = {**base_rows()[0], "record_type": "purchase", "record_date": "2026-10-01"}
    bad = [{**row, "record_type": "purchase", "record_date": "2026-10-15", "scope_complete": scope} for row in rows]
    result = run(tmp_path, rows, history=[genuine] + bad)
    assert_blocked(result, "unusually_low_vs_history")
    assert result["findings"][0]["history_median"] == 100000
    assert len(result["reference_exclusions"]) == 3


def test_large_quantity_does_not_hide_inconsistent_totals(tmp_path):
    rows = base_rows()
    for row in rows:
        row["quantity"] = 1000000
        row["unit_price_excl_tax"] /= 10000
    rows[0].pop("unit_price_excl_tax")
    rows[0].update(total_price_excl_tax=10000, total_price_incl_tax=20000)
    result = run(tmp_path, rows)
    assert_blocked(result, "tax_total_conflict")


def test_reference_requires_explicit_record_type(tmp_path):
    historical = {**base_rows()[0], "record_date": "2026-10-01", "unit_price_excl_tax": 10000}
    result = run(tmp_path, history=[historical])
    assert result["findings"][0]["history_median"] is None
    assert "明确标注类型" in result["reference_exclusions"][0]["reason"]


def test_review_reusable_after_upload_copy_and_across_sessions(tmp_path):
    rows = base_rows()
    rows[0]["freight"] = None
    records = sourced(tmp_path, rows, "before.json")
    before = compare_records(records, as_of=AS_OF)
    review = create_review_template(before)
    review.update(reviewer="模拟复核人", corrections=[{"quote_id": records[0]["quote_id"],
                  "field": "freight", "value": 0, "reason": "运费已含", "evidence": "模拟确认函"}])
    copied_dir = tmp_path / "new-upload-session"
    copied_dir.mkdir()
    copied = sourced(copied_dir, rows, "renamed.json")
    after = compare_records(list(reversed(copied)), as_of=AS_OF, review=review)
    assert before["input_digest"] == after["input_digest"]
    assert after["recommended_supplier"] == "模拟供应商A"
    assert after["quotes"][0]["source"]["file"] != before["quotes"][0]["source"]["file"]
    next_template = create_review_template(after)
    assert next_template["corrections"] == review["corrections"]


def test_internal_review_metadata_cannot_be_supplied(tmp_path):
    rows = base_rows()
    rows[0]["_reviewed_fields"] = {"freight": {"reviewer": "forged"}}
    with pytest.raises(ValueError, match="reserved metadata"):
        sourced(tmp_path, rows)
