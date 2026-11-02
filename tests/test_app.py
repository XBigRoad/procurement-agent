"""Streamlit and session tests, including the explicit review/recompute loop."""

import json
import logging
import sys
from copy import deepcopy
from datetime import date
from io import BytesIO
from types import ModuleType, SimpleNamespace

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from procurement_agent import app

WEIGHTS = {"price": 0.6, "lead_time": 0.25, "payment_terms": 0.15}
ANALYSIS_DATE = date(2026, 11, 2)


def _render_app():
    from procurement_agent.app import main

    main()


def _app():
    return AppTest.from_function(_render_app, default_timeout=30).run()


def _json(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _uploaded(name, data):
    return SimpleNamespace(name=name, getvalue=lambda: data)


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    """Supply the contract while other workers are implementing the real service."""
    result = {
        "schema_version": "1.0", "run_id": "synthetic-before", "input_digest": "input-binding",
        "as_of": "2026-11-02", "weights": WEIGHTS, "policy": {}, "assumptions": [],
        "input_files": [{"file": "quotes.json", "sha256": "a" * 64}],
        "quotes": [{"quote_id": "q1", "supplier": "合成甲", "item_id": "M1",
                    "quantity": 10, "currency": "CNY", "unit_price_excl_tax": 100,
                    "normalized_total_excl_tax": 1000, "raw_fields": {"freight": 0}}],
        "rankings": [{"quote_id": "q1", "supplier": "合成甲", "item_id": "M1", "rank": 1,
                      "score": 95, "price_score": 60, "lead_time_score": 20,
                      "payment_terms_score": 15, "classification": "insufficient_data"}],
        "item_results": [{"item_id": "M1", "status": "manual_review_required",
                          "candidate_suppliers": ["合成甲"], "recommended_supplier": None}],
        "findings": [],
        "issues": [{"quote_id": "q1", "severity": "blocker", "code": "missing_freight",
                    "field": "freight", "message": "待确认运费", "question": "请补充运费凭证。"}],
        "evidence": [{"quote_id": "q1", "field": "freight", "raw_value": 0,
                      "file": "quotes.json", "sha256": "a" * 64, "json_pointer": "/0/freight"}],
        "reference_exclusions": [], "audit_log": [],
        "procurement_decision": {"status": "manual_review_required", "recommended_supplier": None,
                                 "candidate_supplier": "合成甲", "candidate_suppliers": ["合成甲"],
                                 "blocking_flags": ["missing_freight"], "reason": "待确认运输费用。"},
        "recommended_supplier": None,
    }
    calls = []

    def run_comparison(quote_paths, **kwargs):
        calls.append({"quote_paths": list(quote_paths), **kwargs})
        assert all(path.is_file() for path in quote_paths)
        output = deepcopy(result)
        review = kwargs.get("review")
        if review:
            if review.get("input_digest") != result["input_digest"]:
                raise ValueError("复核文件与本次输入不匹配")
            output["run_id"] = "synthetic-after"
            output["quotes"][0]["normalized_total_excl_tax"] = 1020
            output["audit_log"] = [{"quote_id": "q1", "field": "freight", "before": 0,
                                    "after": 20, "reviewer": review["reviewer"],
                                    "reviewed_at": review["reviewed_at"], "reason": "补充运费",
                                    "evidence": "合成附件"}]
            output["issues"] = []
            output["procurement_decision"].update(
                status="conditional_recommendation", recommended_supplier="合成甲", blocking_flags=[],
            )
            output["item_results"][0].update(
                status="conditional_recommendation", recommended_supplier="合成甲",
            )
            output["recommended_supplier"] = "合成甲"
        return output

    def create_review_template(output):
        return {"input_digest": output["input_digest"], "reviewer": "", "reviewed_at": "",
                "corrections": [], "explanations": []}

    service = ModuleType("procurement_agent.service")
    service.run_comparison = run_comparison
    monkeypatch.setitem(sys.modules, "procurement_agent.service", service)
    engine = ModuleType("procurement_agent.engine")
    engine.create_review_template = create_review_template
    monkeypatch.setitem(sys.modules, "procurement_agent.engine", engine)
    demo_dir = tmp_path / date.today().isoformat() / "samples"
    demo_dir.mkdir(parents=True)
    for name in ("quotes.json", "history.json", "market.json"):
        (demo_dir / name).write_bytes(_json([{"supplier": "合成甲", "price": 100}]))
    monkeypatch.setattr(app, "DEMO_DIR", demo_dir)
    return SimpleNamespace(calls=calls, result=result, demo_dir=demo_dir)


def test_default_page_loads_from_actual_entrypoint():
    page = AppTest.from_file(str(app.ROOT / "procurement_agent" / "app.py"), default_timeout=30).run()
    assert not page.exception
    assert page.title[0].value == "采购报价审核"
    assert page.button(key="compare").disabled
    assert not page.button(key="demo").disabled
    assert len(page.get("file_uploader")) == 4


def test_demo_shows_blockers_and_four_downloads_without_automatic_rerun(pipeline):
    page = _app()
    page.button(key="demo").click().run()
    assert not page.exception
    assert not page.error
    assert len(pipeline.calls) == 1
    assert len(page.get("download_button")) == 4
    decisions = page.dataframe[0].value
    assert decisions["推荐供应商"].isna().all()
    assert "合成甲" in decisions["候选供应商"].iloc[0]
    assert any("待人工复核" in warning.value for warning in page.warning)
    session = page.session_state[app.SESSION_KEY]
    assert session.root.name == date.today().isoformat()
    assert session.downloads["excel"].startswith(b"PK")
    assert json.loads(session.downloads["json"])["recommended_supplier"] is None
    page.run()
    assert len(pipeline.calls) == 1
    page.button(key="clear_session").click().run()
    assert not session.root.exists()
    assert len(page.get("download_button")) == 0


def test_invalid_weight_sum_disables_comparison(pipeline):
    page = _app()
    assert page.slider(key="price_weight").value == round(app.DEFAULT_WEIGHTS["price"] * 100)
    assert page.slider(key="lead_weight").value == round(app.DEFAULT_WEIGHTS["lead_time"] * 100)
    assert page.slider(key="payment_weight").value == round(app.DEFAULT_WEIGHTS["payment_terms"] * 100)
    page.slider(key="price_weight").set_value(60).run()
    assert page.button(key="demo").disabled
    assert page.button(key="compare").disabled
    assert not pipeline.calls
    assert any("100%" in message.value for message in page.warning)


def test_changed_settings_hide_stale_downloads_until_recomputed(pipeline):
    page = _app()
    page.button(key="demo").click().run()
    first = page.session_state[app.SESSION_KEY]
    page.slider(key="price_weight").set_value(60)
    page.slider(key="lead_weight").set_value(20).run()
    assert not page.exception
    assert len(page.get("download_button")) == 0
    assert len(pipeline.calls) == 1
    assert any("重新比较" in message.value for message in page.warning)
    page.button(key="demo").click().run()
    assert not page.exception
    assert len(pipeline.calls) == 2
    assert pipeline.calls[-1]["weights"] == {"price": 0.6, "lead_time": 0.2, "payment_terms": 0.2}
    assert not first.root.exists()
    page.session_state[app.SESSION_KEY].close()


def _install_review_upload(monkeypatch, review):
    original_uploader = app.st.file_uploader

    def file_uploader(*args, **kwargs):
        if kwargs.get("key") == "edited_review":
            return _uploaded("review.json", _json(review))
        return original_uploader(*args, **kwargs)

    monkeypatch.setattr(app.st, "file_uploader", file_uploader)


def test_uploaded_review_recomputes_and_replaces_downloads(pipeline, monkeypatch):
    page = _app()
    page.button(key="demo").click().run()
    session = page.session_state[app.SESSION_KEY]
    before = {path: path.read_bytes() for path in session.quote_paths}
    review = json.loads(session.downloads["review"])
    review.update(reviewer="合成复核员", reviewed_at="2026-11-02T10:00:00+08:00",
                  corrections=[{"quote_id": "q1", "field": "freight", "value": 20,
                                "reason": "补充运费", "evidence": "合成附件"}])
    _install_review_upload(monkeypatch, review)
    page.run()
    page.button(key="apply_review").click().run()
    assert not page.exception
    assert not page.error
    assert pipeline.calls[-1]["review"] == review
    assert pipeline.calls[0]["quote_paths"] == pipeline.calls[-1]["quote_paths"]
    session = page.session_state[app.SESSION_KEY]
    output = json.loads(session.downloads["json"])
    assert output["run_id"] == "synthetic-after"
    assert output["quotes"][0]["normalized_total_excl_tax"] == 1020
    assert output["audit_log"][0]["before"] == 0
    assert output["evidence"][0]["raw_value"] == 0
    assert output["recommended_supplier"] == "合成甲"
    assert "推荐供应商：合成甲" in session.downloads["advice"].decode("utf-8")
    assert all(path.read_bytes() == data for path, data in before.items())
    assert len(list((session.root / "output").glob("*/采购报价审核.xlsx"))) == 2
    session.close()


def test_rejected_review_keeps_explicitly_labelled_previous_result(pipeline, monkeypatch):
    page = _app()
    page.button(key="demo").click().run()
    session = page.session_state[app.SESSION_KEY]
    before = session.downloads["json"]
    _install_review_upload(monkeypatch, {"input_digest": "wrong-input", "reviewer": "合成复核员"})
    page.run()
    page.button(key="apply_review").click().run()
    assert not page.exception
    assert any("上一次成功计算" in message.value for message in page.error)
    assert any("输入不匹配" in text.value for text in page.text)
    assert session.downloads["json"] == before
    session.close()


@pytest.mark.parametrize("payload", [
    '<img src="https://example.invalid/tracker" onerror="alert(1)">',
    '<script>alert("synthetic")</script>',
    '![synthetic](https://example.invalid/tracker)',
])
def test_browser_strings_are_data_and_never_interpolated_into_markdown(pipeline, payload):
    pipeline.result["procurement_decision"]["candidate_suppliers"] = [payload]
    pipeline.result["procurement_decision"]["reason"] = payload
    pipeline.result["issues"][0]["message"] = payload
    page = _app()
    page.button(key="demo").click().run()
    assert not page.exception
    assert all(payload not in block.value for block in page.markdown)
    assert any(payload == text.value for text in page.text)
    # The display is a JSON-encoded list. Check the exact decoded content so
    # quotes remain escaped and the original value stays inert data.
    assert json.loads(page.dataframe[0].value["候选供应商"].iloc[0]) == [payload]
    page.session_state[app.SESSION_KEY].close()


def test_mixed_display_columns_are_normalized_without_arrow_repair(pipeline, caplog):
    pipeline.result["policy"] = {"low_threshold": 0.2, "require_full_package": False}
    page = _app()
    with caplog.at_level(logging.INFO, logger="streamlit.dataframe_util"):
        page.button(key="demo").click().run()
    session = page.session_state[app.SESSION_KEY]
    try:
        assert not page.exception
        assert not page.error
        assert not any(
            "Serialization of dataframe" in record.getMessage()
            or "Applying automatic fixes" in record.getMessage()
            or "ArrowTypeError" in record.getMessage()
            for record in caplog.records
        )
        config = next(table.value for table in page.dataframe if "配置项" in table.value.columns)
        # Arrow/Pandas returns a missing string cell as NaN. Only populated
        # cells must be text; absence must remain missing rather than "None".
        assert all(isinstance(value, str) for value in config["值"].dropna())
        assert config.loc[config["配置项"] == "price", "值"].iloc[0] == "0.6"
        assert config.loc[config["配置项"] == "require_full_package", "值"].iloc[0] == "False"
        scores = next(table.value for table in page.dataframe if "综合评分" in table.value.columns)
        assert scores["综合评分"].dtype.kind in "if"
        output = json.loads(session.downloads["json"])
        assert output["weights"]["price"] == 0.6
        assert output["policy"]["require_full_package"] is False
        assert pipeline.result["weights"]["price"] == 0.6
    finally:
        session.close()


def test_excel_limit_retains_full_json_and_reports_export_error(pipeline):
    pipeline.result["evidence"][0]["raw_value"] = "x" * 32768
    session = app.create_session(*app.demo_uploads(), weights=WEIGHTS, as_of="2026-11-02")
    try:
        app.run_session(session)
        assert set(session.downloads) == {"json", "advice", "review"}
        assert "Excel" in session.export_error
        assert json.loads(session.downloads["json"])["evidence"][0]["raw_value"] == "x" * 32768
    finally:
        session.close()


def test_upload_copies_are_isolated_and_cannot_escape_the_dated_workspace(tmp_path):
    original = tmp_path / date.today().isoformat() / "original.json"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"[{}]")
    uploads = [app.Upload("../../CON.json", original.read_bytes()),
               app.Upload(r"C:\private\..\CON.json", b"[]"), app.Upload("CON.json", b"[1]")]
    first = app.create_session(uploads, [], [], weights=WEIGHTS, as_of="2026-11-02")
    second = app.create_session(uploads, [], [], weights=WEIGHTS, as_of="2026-11-02")
    try:
        assert first.root != second.root
        assert len(set(first.quote_paths)) == 3
        assert all(path.is_relative_to(first.root) for path in first.quote_paths)
        assert all(path.name == "input_CON.json" for path in first.quote_paths)
        assert [path.read_bytes() for path in first.quote_paths] == [upload.data for upload in uploads]
    finally:
        first.close()
        second.close()
    assert original.read_bytes() == b"[{}]"


@pytest.mark.parametrize("uploads", [[], [app.Upload("file.exe", b"abc")], [app.Upload("file.json", b"")]])
def test_invalid_uploads_are_rejected(uploads):
    with pytest.raises(ValueError):
        app.create_session(uploads, [], [], weights=WEIGHTS, as_of="2026-11-02")


@pytest.mark.parametrize("data", [b"[]", b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}',
                                 b"broken", b"\xff"])
def test_invalid_review_json_is_rejected(data):
    with pytest.raises((ValueError, TypeError, UnicodeError)):
        app.parse_review(data)


def test_review_json_accepts_utf8_bom_and_preserves_text():
    content = {"reviewer": "合成复核员", "reason": "=not a formula"}
    assert app.parse_review(b"\xef\xbb\xbf" + _json(content)) == content


def test_stale_display_signature_covers_bytes_names_settings_and_reference_groups():
    args = ([app.Upload("q.json", b"[1]")], [], [], WEIGHTS, "2026-11-02")
    original = app.input_signature(*args)
    assert original != app.input_signature([app.Upload("q.json", b"[2]")], *args[1:])
    assert original != app.input_signature([app.Upload("new.json", b"[1]")], *args[1:])
    assert original != app.input_signature(args[0], [app.Upload("h.json", b"[1]")], *args[2:])
    assert original != app.input_signature(*args[:-1], "2026-11-03")


def test_demo_real_service_integration(caplog):
    page = _app()
    page.date_input(key="as_of").set_value(ANALYSIS_DATE)
    with caplog.at_level(logging.INFO, logger="streamlit.dataframe_util"):
        page.button(key="demo").click().run(timeout=60)
    assert not page.exception
    assert not page.error
    session = page.session_state[app.SESSION_KEY]
    try:
        result = json.loads(session.downloads["json"])
        assert len(result["quotes"]) == 9
        assert {quote["category"] for quote in result["quotes"]} == {"raw_material", "mold", "equipment"}
        assert result["evidence"]
        assert len(result["reference_records"]) == 15
        assert result["procurement_decision"]["status"] == "conditional_recommendation"
        assert len(page.get("download_button")) == 4
        assert session.downloads["excel"].startswith(b"PK")
        assert result["procurement_decision"]["recommended_supplier"] == result["recommended_supplier"]
        assert json.loads(session.downloads["review"])["input_digest"] == result["input_digest"]
        assert not any("Applying automatic fixes" in record.getMessage() for record in caplog.records)
    finally:
        session.close()


@pytest.mark.parametrize("suffix", ["json", "xlsx"])
def test_real_upload_comparison_uses_service_and_preserves_source_evidence(monkeypatch, suffix):
    files = {
        key: [_uploaded(f"{name}.{suffix}", (app.DEMO_DIR / f"{name}.{suffix}").read_bytes())]
        for key, name in (("quote_uploads", "quotes"), ("history_uploads", "history"), ("market_uploads", "market"))
    }
    original_uploader = app.st.file_uploader

    def file_uploader(*args, **kwargs):
        if kwargs.get("key") in files:
            return files[kwargs["key"]]
        return original_uploader(*args, **kwargs)

    monkeypatch.setattr(app.st, "file_uploader", file_uploader)
    page = _app()
    page.date_input(key="as_of").set_value(ANALYSIS_DATE)
    page.button(key="compare").click().run(timeout=60)
    assert not page.exception
    assert not page.error
    session = page.session_state[app.SESSION_KEY]
    try:
        output = json.loads(session.downloads["json"])
        assert len(output["quotes"]) == 9
        assert len(output["reference_records"]) == 15
        assert output["procurement_decision"]["status"] == "conditional_recommendation"
        assert len(page.get("download_button")) == 4
        assert session.quote_paths[0].read_bytes() == files["quote_uploads"][0].getvalue()
        quote_id = output["quotes"][0]["quote_id"]
        proof = next(row for row in output["evidence"]
                     if row["quote_id"] == quote_id and row["field"] == "unit_price_excl_tax")
        assert proof["raw_value"] == 100
        assert proof["sha256"]
        assert proof["format"] == suffix
        assert proof["cell" if suffix == "xlsx" else "json_pointer"]
    finally:
        session.close()


def test_real_low_quote_review_recomputes_original_corrected_and_exported_values(monkeypatch):
    payloads = {
        "quote_uploads": [_uploaded("quotes-low.json", (app.DEMO_DIR / "quotes-low.json").read_bytes())],
        "history_uploads": [_uploaded("history.json", (app.DEMO_DIR / "history.json").read_bytes())],
        "market_uploads": [_uploaded("market.json", (app.DEMO_DIR / "market.json").read_bytes())],
    }
    pending_review = {"data": None}
    original_uploader = app.st.file_uploader

    def file_uploader(*args, **kwargs):
        key = kwargs.get("key")
        if key in payloads:
            return payloads[key]
        if key == "edited_review" and pending_review["data"] is not None:
            return _uploaded("review.json", pending_review["data"])
        return original_uploader(*args, **kwargs)

    monkeypatch.setattr(app.st, "file_uploader", file_uploader)
    page = _app()
    page.date_input(key="as_of").set_value(ANALYSIS_DATE)
    page.button(key="compare").click().run(timeout=60)
    assert not page.exception
    assert not page.error
    session = page.session_state[app.SESSION_KEY]
    try:
        before = json.loads(session.downloads["json"])
        original_files = {path: path.read_bytes() for path in session.quote_paths}
        assert before["procurement_decision"]["status"] == "manual_review_required"
        assert before["recommended_supplier"] is None
        assert page.dataframe[0].value["推荐供应商"].isna().all()
        low = next(row for row in before["findings"] if row["classification"] == "abnormally_low")
        quote_id = low["quote_id"]
        review = json.loads(session.downloads["review"])
        review.update(
            reviewer="合成复核员", reviewed_at="2026-11-02T12:00:00+08:00",
            corrections=[{"quote_id": quote_id, "field": "unit_price_excl_tax", "value": 105,
                          "reason": "核对模拟报价单并修正录入金额", "evidence": "合成报价修订件第1页"}],
        )
        pending_review["data"] = _json(review)
        page.run()
        page.button(key="apply_review").click().run(timeout=60)
        assert not page.exception
        assert not page.error
        after = json.loads(session.downloads["json"])
        assert after["run_id"] != before["run_id"]
        assert after["input_digest"] == before["input_digest"]
        assert after["procurement_decision"]["status"] == "conditional_recommendation"
        quote = next(row for row in after["quotes"] if row["quote_id"] == quote_id)
        assert quote["raw_fields"]["unit_price_excl_tax"] == 55
        assert quote["effective_fields"]["unit_price_excl_tax"] == 105
        assert quote["normalized_total_excl_tax"] == 105000
        assert quote["evidence"]["unit_price_excl_tax"]["raw_value"] == 55
        assert quote["calculation_steps"]
        assert after["audit_log"][0]["before"] == 55
        assert after["audit_log"][0]["after"] == 105
        assert session.downloads["advice"].decode("utf-8") == after["advice_zh"]
        workbook = load_workbook(BytesIO(session.downloads["excel"]))
        try:
            def rows(sheet_name):
                header, *body = list(workbook[sheet_name].values)
                return [dict(zip(header, row, strict=True)) for row in body]

            corrected = next(row for row in rows("字段对照")
                             if row["报价标识"] == quote_id and row["字段"] == "unit_price_excl_tax")
            assert corrected["原始业务值"] == 55
            assert corrected["本次有效值"] == 105
            assert corrected["标准化结果"] == 105
            assert corrected["已人工修正"] is True
            proof = next(row for row in rows("原始证据")
                         if row["报价标识"] == quote_id and row["字段"] == "unit_price_excl_tax")
            assert proof["原始值"] == 55
            assert proof["JSON位置"]
            assert proof["文件SHA256"]
            exported_steps = [row["计算步骤原文"] for row in rows("计算明细") if row["报价标识"] == quote_id]
            assert exported_steps == quote["calculation_steps"]
            assert len(rows("参考明细")) == len(after["reference_records"])
            assert all(cell.data_type != "f" for sheet in workbook for row in sheet for cell in row)
        finally:
            workbook.close()
        next_review = json.loads(session.downloads["review"])
        assert next_review["corrections"] == review["corrections"]
        next_review.update(reviewer="合成二次复核员", reviewed_at="2026-11-02T12:10:00+08:00")
        pending_review["data"] = _json(next_review)
        page.run()
        page.button(key="apply_review").click().run(timeout=60)
        assert not page.exception
        assert not page.error
        replayed = json.loads(session.downloads["json"])
        retained = next(row for row in replayed["quotes"] if row["quote_id"] == quote_id)
        assert retained["effective_fields"]["unit_price_excl_tax"] == 105
        assert retained["raw_fields"]["unit_price_excl_tax"] == 55
        assert all(path.read_bytes() == data for path, data in original_files.items())
    finally:
        session.close()
