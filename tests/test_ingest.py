"""Contract tests for evidence-preserving CSV, XLSX and JSON ingestion."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

from procurement_agent import ingest
from procurement_agent.ingest import load_records

FORMATS = ("csv", "xlsx", "json")
CANONICAL_FIELDS = (
    "supplier item_id item_name category specification configuration brand material "
    "grade quantity unit currency unit_price_excl_tax unit_price_incl_tax "
    "total_price_excl_tax total_price_incl_tax tax_rate freight installation "
    "packaging commissioning tooling fee_basis fee_tax_rate freight_tax_rate "
    "installation_tax_rate lead_time_days lead_time_weeks payment_days payment_terms "
    "payment_anchor prepayment_percent warranty_months scope_complete quote_date "
    "valid_until record_date record_type price price_basis notes source_url"
).split()
CHINESE_ALIASES = (
    ("供应商名称", "supplier"), ("物料编码", "item_id"), ("物料名称", "item_name"),
    ("规格型号", "specification"), ("数量", "quantity"), ("单位", "unit"),
    ("币种", "currency"), ("含税单价", "unit_price_incl_tax"),
    ("未税单价", "unit_price_excl_tax"), ("含税总价", "total_price_incl_tax"),
    ("未税总价", "total_price_excl_tax"), ("税率", "tax_rate"), ("运费", "freight"),
    ("安装费", "installation"), ("交期(天)", "lead_time_days"),
    ("账期(天)", "payment_days"), ("付款条件", "payment_terms"),
    ("质保(月)", "warranty_months"), ("报价范围完整", "scope_complete"),
)


def write_table(tmp_path, file_format, headers, rows, *, name="input", encoding="utf-8"):
    path = tmp_path / f"{name}.{file_format}"
    if file_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        path.write_bytes(buffer.getvalue().encode(encoding))
    elif file_format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "报价"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        workbook.close()
    else:
        # Emit pairs directly so tests can exercise duplicate JSON properties.
        objects = [
            "{" + ",".join(
                json.dumps(key, ensure_ascii=False) + ":" + json.dumps(value, ensure_ascii=False)
                for key, value in zip(headers, row)
            ) + "}"
            for row in rows
        ]
        path.write_text("[" + ",".join(objects) + "]", encoding="utf-8")
    return path


def write_json(tmp_path, payload, *, name="input", encoding="utf-8"):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding=encoding)
    return path


def replace_zip_member(path, member, transform):
    with ZipFile(path) as archive:
        members = [(info, archive.read(info.filename)) for info in archive.infolist()]
    with ZipFile(path, "w") as archive:
        for info, content in members:
            archive.writestr(info, transform(content) if info.filename == member else content)


def issue_codes(record):
    return {issue["code"] for issue in record["_input_issues"]}


@pytest.mark.parametrize("file_format", FORMATS)
def test_all_canonical_fields_and_their_original_evidence(tmp_path, file_format):
    values = [f"literal {index}" for index in range(len(CANONICAL_FIELDS))]
    path = write_table(tmp_path, file_format, CANONICAL_FIELDS, [values])
    record, = load_records(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert record["_source"]["sha256"] == digest
    assert record["_source"]["format"] == file_format
    assert record["_source"]["file"] == str(path.resolve())
    assert record["_input_issues"] == []
    assert set(record["_evidence"]) == set(CANONICAL_FIELDS)
    for index, (field, value) in enumerate(zip(CANONICAL_FIELDS, values), 1):
        assert record[field] == value
        evidence = record["_evidence"][field]
        assert evidence["raw_value"] == value
        assert evidence["raw_header"] == field
        assert evidence["sha256"] == digest
        assert evidence["file"] == str(path.resolve())
        assert evidence["format"] == file_format
        if file_format == "json":
            assert evidence["json_pointer"] == f"/0/{field}"
        else:
            assert evidence["row"] == 2
            assert evidence["column"] == index
    if file_format == "xlsx":
        assert record["_evidence"]["payment_days"]["cell"] == "AC2"


@pytest.mark.parametrize("file_format", FORMATS)
def test_chinese_aliases(tmp_path, file_format):
    path = write_table(
        tmp_path, file_format, [alias for alias, _ in CHINESE_ALIASES],
        [[f"原值{index}" for index in range(len(CHINESE_ALIASES))]],
    )
    record, = load_records(path)
    for index, (alias, canonical) in enumerate(CHINESE_ALIASES):
        assert record[canonical] == f"原值{index}"
        assert record["_evidence"][canonical]["raw_header"] == alias


@pytest.mark.parametrize("file_format", FORMATS)
def test_english_aliases_case_whitespace_and_fullwidth_punctuation(tmp_path, file_format):
    path = write_table(
        tmp_path, file_format, [" Supplier Name ", "SPEC", "交期（天）", "质保（月）", " Price "],
        [["  A  ", " X-001 ", " 7 ", "24", "00100.00"]],
    )
    record, = load_records(path)
    assert record["supplier"] == "  A  "
    assert record["specification"] == " X-001 "
    assert record["lead_time_days"] == " 7 "
    assert record["warranty_months"] == "24"
    assert record["price"] == "00100.00"
    assert "unit_price_excl_tax" not in record
    assert "unit_price_incl_tax" not in record
    assert "price_basis" not in record


@pytest.mark.parametrize("file_format", FORMATS)
@pytest.mark.parametrize(
    "headers",
    [
        ["supplier", "name"], ["供应商", "supplier"], ["name", "供应商名称"],
        ["规格", "specification"], ["price", "price"],
        ["supplier", "custom", "custom"], [" Supplier ", "SUPPLIER"],
    ],
)
def test_duplicate_headers_fail_before_overwriting_evidence(tmp_path, file_format, headers):
    path = write_table(tmp_path, file_format, headers, [["value"] * len(headers)])
    with pytest.raises(ValueError, match="[Dd]uplicate") as error:
        load_records(path)
    assert str(path) in str(error.value)


@pytest.mark.parametrize("file_format", FORMATS)
@pytest.mark.parametrize("field", ["quote_id", "_source", "_evidence", "_input_issues", "QUOTE ID", " _SOURCE "])
def test_reserved_metadata_is_rejected_even_when_empty(tmp_path, file_format, field):
    path = write_table(tmp_path, file_format, ["supplier", field], [["A", ""]])
    with pytest.raises(ValueError, match="reserved metadata"):
        load_records(path)


@pytest.mark.parametrize("file_format", FORMATS)
def test_unknown_business_fields_and_evidence_survive(tmp_path, file_format):
    path = write_table(tmp_path, file_format, ["supplier", "采购备注/自定义", " Extra Detail "], [["A", "原文", "  kept  "]])
    record, = load_records(path)
    assert record["采购备注/自定义"] == "原文"
    assert record[" Extra Detail "] == "  kept  "
    assert record["_evidence"][" Extra Detail "]["raw_value"] == "  kept  "
    assert record["_input_issues"] == []


@pytest.mark.parametrize("file_format", FORMATS)
def test_position_and_content_determine_identity_not_path_kind_or_supplier(tmp_path, file_format):
    path = write_table(tmp_path, file_format, ["name", "price"], [["A", 100], ["A", 100]])
    original = load_records(path)
    assert len({record["quote_id"] for record in original}) == 2
    assert re.fullmatch(r"q_[0-9a-f]{64}", original[0]["quote_id"])
    copied = tmp_path / f"copy.{file_format.upper()}"
    copied.write_bytes(path.read_bytes())
    for kind in ("quotes", "history", "market"):
        reloaded = load_records(copied, kind=kind)
        assert [record["quote_id"] for record in reloaded] == [record["quote_id"] for record in original]
    assert load_records(path) == original
    changed = write_table(tmp_path, file_format, ["name", "price"], [["A", 101], ["A", 100]], name="changed")
    assert load_records(changed)[0]["quote_id"] != original[0]["quote_id"]


@pytest.mark.parametrize("file_format", FORMATS)
def test_only_truly_blank_rows_are_skipped(tmp_path, file_format):
    path = write_table(
        tmp_path, file_format, ["supplier", "price", "custom"],
        [["", "", ""], [" ", "\t", None], ["", 0, ""], ["", "", "unmapped content"]],
    )
    records = load_records(path)
    assert len(records) == 2
    assert records[0]["price"] == ("0" if file_format == "csv" else 0)
    assert records[1]["custom"] == "unmapped content"
    assert "malformed_row" in issue_codes(records[1])
    for record in records:
        for issue in record["_input_issues"]:
            assert set(issue) == {"code", "field", "message"}
    position = "json_pointer" if file_format == "json" else "row"
    assert records[0]["_source"][position] == ("/2" if file_format == "json" else 4)


@pytest.mark.parametrize("file_format", FORMATS)
def test_formula_text_is_preserved_as_an_input_issue(tmp_path, file_format):
    path = write_table(tmp_path, file_format, ["supplier", "price", "custom"], [["A", "=10*2", "=1+1"]])
    record, = load_records(path)
    assert record["price"] == "=10*2"
    assert record["_evidence"]["price"]["raw_value"] == "=10*2"
    assert record["_evidence"]["price"]["formula"] == "=10*2"
    assert {issue["field"] for issue in record["_input_issues"] if issue["code"] == "formula"} == {"price", "custom"}


@pytest.mark.parametrize("file_format", FORMATS)
def test_negative_values_and_nonformula_text_are_not_repaired(tmp_path, file_format):
    path = write_table(tmp_path, file_format, ["supplier", "quantity", "price", "notes"], [["A", "-2", "not quoted", "@literal"]])
    record, = load_records(path)
    assert record["quantity"] == "-2"
    assert record["price"] == "not quoted"
    assert record["notes"] == "@literal"
    assert record["_input_issues"] == []


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "gb18030"])
def test_csv_encodings_and_hash_of_original_bytes(tmp_path, encoding):
    path = write_table(tmp_path, "csv", ["供应商", "价格"], [["企业𠀀", "001.20"]], encoding=encoding)
    record, = load_records(path)
    assert record["supplier"] == "企业𠀀"
    assert record["price"] == "001.20"
    assert record["_source"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_csv_multiline_records_use_physical_start_lines(tmp_path):
    path = tmp_path / "multiline.csv"
    path.write_bytes(b'\r\nsupplier,notes,price\r\nA,"first\r\nsecond",100\r\n\r\nB,note,101\r\n')
    first, second = load_records(path)
    assert first["notes"] == "first\r\nsecond"
    assert first["_source"]["row"] == 3
    assert first["_source"]["row_end"] == 4
    assert first["_evidence"]["notes"]["row"] == 3
    assert first["_evidence"]["notes"]["column"] == 2
    assert second["_source"]["row"] == 6
    assert second["_evidence"]["price"]["row"] == 6


def test_csv_multiline_header_preserves_original_and_line_offset(tmp_path):
    path = write_table(tmp_path, "csv", ["Supplier\nName", "price"], [["A", 100]])
    record, = load_records(path)
    assert record["supplier"] == "A"
    assert record["_source"]["row"] == 3
    assert record["_evidence"]["supplier"]["raw_header"] == "Supplier\nName"


def test_csv_short_and_long_rows_remain_reviewable(tmp_path):
    path = write_table(tmp_path, "csv", ["supplier", "price"], [["A"], ["B", "2", "orphan"]])
    short, long = load_records(path)
    assert short["supplier"] == "A"
    assert "price" not in short["_evidence"]
    assert "malformed_row" in issue_codes(short)
    assert long["unmapped_column_3"] == "orphan"
    assert long["_evidence"]["unmapped_column_3"]["column"] == 3
    assert long["_evidence"]["unmapped_column_3"]["raw_header"] is None
    assert {"malformed_row", "missing_header"} <= issue_codes(long)


@pytest.mark.parametrize("file_format", ["csv", "xlsx"])
def test_missing_header_values_never_overwrite_real_fields(tmp_path, file_format):
    path = write_table(tmp_path, file_format, ["supplier", "unmapped_column_3", ""], [["A", "real", "orphan"]])
    record, = load_records(path)
    assert record["unmapped_column_3"] == "real"
    assert record["unmapped_column_3_"] == "orphan"
    assert "missing_header" in issue_codes(record)


@pytest.mark.parametrize(
    ("content", "message"),
    [(b'supplier,price\nA,"unterminated', "Invalid CSV"), (b"supplier,price\nA,\x00", "NUL"),
     (b"supplier,price\nA,\x81", "UTF-8 or GB18030"), (b"foo,bar\na,b", "no recognized")],
)
def test_invalid_csv_has_actionable_errors(tmp_path, content, message):
    path = tmp_path / "broken.csv"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=message) as error:
        load_records(path)
    assert str(path) in str(error.value)


@pytest.mark.parametrize("content", [b"", b"\xef\xbb\xbf", b"\n\r\n", b"supplier,price\n"])
def test_empty_csv(tmp_path, content):
    path = tmp_path / "empty.csv"
    path.write_bytes(content)
    assert load_records(path) == []


def test_xlsx_all_sheets_preambles_blank_sheets_and_actual_coordinates(tmp_path):
    path = tmp_path / "sheets.xlsx"
    workbook = Workbook()
    workbook.active.title = "空表"
    workbook.active["A50"].number_format = "0.00"
    for title in ("设备", "原材料"):
        sheet = workbook.create_sheet(title)
        sheet.append(["采购报价说明"])
        sheet.append([])
        sheet.append(["供应商", "物料编码", "未税单价"])
        sheet.append(["A", "001", 12.5])
        sheet.append([])
        sheet.append(["B", "002", 0])
    workbook["原材料"].sheet_state = "hidden"
    workbook.save(path)
    workbook.close()
    records = load_records(path)
    assert [(r["_source"]["sheet"], r["_source"]["row"]) for r in records] == [
        ("设备", 4), ("设备", 6), ("原材料", 4), ("原材料", 6),
    ]
    assert len({r["quote_id"] for r in records}) == 4
    assert records[2]["_evidence"]["unit_price_excl_tax"]["cell"] == "C4"
    assert records[2]["_evidence"]["unit_price_excl_tax"]["sheet"] == "原材料"


@pytest.mark.parametrize("supplier_label", ["供应商", "Supplier", "供应商名称"])
def test_xlsx_preamble_field_labels_do_not_hide_the_real_header(tmp_path, supplier_label):
    path = tmp_path / "preamble.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([supplier_label, "A"])
    sheet.append(["报价日期", datetime(2026, 1, 2)])
    sheet.append(["数量", 100])
    sheet.append(["供应商", "物料编码", "未税单价", "采购备注"])
    sheet.append(["A", "P-001", 12.5, "业务原文"])
    workbook.save(path)
    workbook.close()
    record, = load_records(path)
    assert record["_source"]["row"] == 5
    assert record["_evidence"]["unit_price_excl_tax"]["cell"] == "C5"
    assert record["采购备注"] == "业务原文"
    assert record["_input_issues"] == []


@pytest.mark.parametrize("leading_rows", [0, 1, 29, 30, 31])
def test_xlsx_header_search_boundary(tmp_path, leading_rows):
    path = tmp_path / "header.xlsx"
    workbook = Workbook()
    for _ in range(leading_rows):
        workbook.active.append(["说明文字"])
    workbook.active.append(["supplier", "price"])
    workbook.active.append(["A", 100])
    workbook.save(path)
    workbook.close()
    if leading_rows > 30:
        with pytest.raises(ValueError, match="30 leading rows"):
            load_records(path)
    else:
        record, = load_records(path)
        assert record["_source"]["row"] == leading_rows + 2


def test_xlsx_sparse_columns_rows_and_false_dimension(tmp_path):
    path = tmp_path / "sparse.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet["C5"] = "supplier"
    sheet["F5"] = "price"
    sheet["C8"] = "A"
    sheet["F8"] = 100
    workbook.save(path)
    workbook.close()
    replace_zip_member(path, "xl/worksheets/sheet1.xml", lambda data: re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1"', data))
    record, = load_records(path)
    assert record["_source"]["row"] == 8
    assert record["_evidence"]["supplier"]["cell"] == "C8"
    assert record["_evidence"]["price"]["cell"] == "F8"
    assert record["_evidence"]["price"]["column"] == 6
    assert record["_input_issues"] == []


@pytest.mark.parametrize("file_format", ["xlsx", "json"])
def test_numeric_boolean_and_null_evidence_keeps_original_types(tmp_path, file_format):
    path = write_table(tmp_path, file_format, ["supplier", "quantity", "tax_rate", "scope_complete", "notes"], [["A", 0, 0.13, False, None]])
    record, = load_records(path)
    for field, expected in {"quantity": 0, "tax_rate": 0.13, "scope_complete": False}.items():
        assert type(record[field]) is type(expected)
        assert record[field] == expected
        assert type(record["_evidence"][field]["raw_value"]) is type(expected)
        assert record["_evidence"][field]["raw_value"] == expected


def test_xlsx_dates_and_number_formats_do_not_rewrite_values(tmp_path):
    path = tmp_path / "types.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["supplier", "quantity", "record_date"])
    sheet.append(["A", 12, datetime(2026, 1, 2, 3, 4, 5)])
    sheet["B2"].number_format = "000000"
    workbook.save(path)
    workbook.close()
    record, = load_records(path)
    assert record["quantity"] == 12
    assert record["record_date"] == datetime(2026, 1, 2, 3, 4, 5)
    assert record["_evidence"]["record_date"]["raw_value"] == record["record_date"]


def test_xlsx_cached_formula_and_external_link_are_never_used_as_values(tmp_path, monkeypatch):
    path = write_table(tmp_path, "xlsx", ["supplier", "price", "notes"], [["A", "=10*2", "='[https://invalid.example/rates.xlsx]Sheet1'!A1"]])

    def cache_result(data):
        root = ElementTree.fromstring(data)
        namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        root.find(".//s:c[@r='B2']/s:v", namespace).text = "20"
        return ElementTree.tostring(root)

    replace_zip_member(path, "xl/worksheets/sheet1.xml", cache_result)
    original_loader = ingest.load_workbook
    calls = []

    def checked_loader(*args, **kwargs):
        calls.append(kwargs)
        return original_loader(*args, **kwargs)

    monkeypatch.setattr(ingest, "load_workbook", checked_loader)
    record, = load_records(path)
    assert calls == [{"read_only": True, "data_only": False, "keep_links": False}]
    assert record["price"] == "=10*2"
    assert record["_evidence"]["price"]["raw_value"] == "=10*2"
    assert record["_evidence"]["notes"]["formula"] == record["notes"]
    assert {issue["field"] for issue in record["_input_issues"]} == {"price", "notes"}


@pytest.mark.parametrize("formula", [ArrayFormula("B2", "=SUM(1,2)"), DataTableFormula("B2", r1="B1")])
def test_xlsx_array_and_data_table_formulas_are_reviewable(tmp_path, formula):
    path = write_table(tmp_path, "xlsx", ["supplier", "price"], [["A", formula]])
    record, = load_records(path)
    assert "formula" in issue_codes(record)
    assert record["_evidence"]["price"]["formula"] == record["price"]
    assert isinstance(record["price"], (str, dict))
    assert record["_evidence"]["price"]["raw_value"] == record["price"]


def test_xlsx_error_cell_remains_visible(tmp_path):
    path = write_table(tmp_path, "xlsx", ["supplier", "price"], [["A", "#DIV/0!"]])
    record, = load_records(path)
    assert record["price"] == "#DIV/0!"
    assert "cell_error" in issue_codes(record)


@pytest.mark.parametrize("headers", [["supplier", 123], ["supplier", "=1+1"], ["unrecognized", "heading"]])
def test_invalid_xlsx_headers_fail_explicitly(tmp_path, headers):
    path = write_table(tmp_path, "xlsx", headers, [["A", 1]])
    with pytest.raises(ValueError, match="header"):
        load_records(path)


def test_xlsx_invalid_later_sheet_does_not_return_partial_success(tmp_path):
    path = tmp_path / "partial.xlsx"
    workbook = Workbook()
    workbook.active.append(["supplier", "price"])
    workbook.active.append(["A", 1])
    workbook.create_sheet("坏表").append(["unknown", "columns"])
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError, match="坏表"):
        load_records(path)


def test_corrupt_xlsx_variants_raise_value_error(tmp_path):
    path = tmp_path / "corrupt.xlsx"
    for content in (b"", b"not a ZIP workbook", b"PK\x03\x04truncated"):
        path.write_bytes(content)
        with pytest.raises(ValueError, match="corrupt.xlsx"):
            load_records(path)
    with ZipFile(path, "w") as archive:
        archive.writestr("unrelated.txt", "not a workbook")
    with pytest.raises(ValueError, match="corrupt.xlsx"):
        load_records(path)


def test_xlsx_corrupt_sheet_xml_is_actionable(tmp_path):
    path = write_table(tmp_path, "xlsx", ["supplier", "price"], [["A", 1]])
    replace_zip_member(path, "xl/worksheets/sheet1.xml", lambda _: b"<invalid")
    with pytest.raises(ValueError, match="Cannot ingest"):
        load_records(path)


@pytest.mark.parametrize("wrapper", [None, "single", "quotes", "records"])
def test_json_supported_shapes_and_pointers(tmp_path, wrapper):
    row = {"name": "A", "spec": "S", "a/b~c": {"raw": [1, 2]}}
    if wrapper == "single":
        payload = row
        pointer = ""
    elif wrapper is None:
        payload = [row]
        pointer = "/0"
    else:
        payload = {wrapper: [row]}
        pointer = f"/{wrapper}/0"
    record, = load_records(write_json(tmp_path, payload))
    assert record["_source"]["json_pointer"] == pointer
    assert record["_evidence"]["supplier"]["json_pointer"] == pointer + "/name"
    assert record["_evidence"]["a/b~c"]["json_pointer"] == pointer + "/a~1b~0c"
    record["a/b~c"]["raw"].append(99)
    assert record["_evidence"]["a/b~c"]["raw_value"] == {"raw": [1, 2]}
    record["_source"]["file"] = "changed by a consumer"
    assert record["_evidence"]["supplier"]["file"] != record["_source"]["file"]


def test_json_legacy_prices_remain_unscoped_and_trace_each_number(tmp_path):
    path = write_json(tmp_path, {"prices": [0, 100, 12.5, 100]})
    records = load_records(path, kind="history")
    assert [r["price"] for r in records] == [0, 100, 12.5, 100]
    assert len({r["quote_id"] for r in records}) == 4
    for index, record in enumerate(records):
        assert record["_evidence"]["price"]["json_pointer"] == f"/prices/{index}"
        assert record["_evidence"]["price"]["raw_value"] == record["price"]
        assert "item_id" not in record
        assert "supplier" not in record
        assert "price_basis" not in record


@pytest.mark.parametrize("payload", [{}, [], {"quotes": []}, {"records": []}, {"prices": []}, [{}, {"supplier": None}]])
def test_empty_json_records(tmp_path, payload):
    assert load_records(write_json(tmp_path, payload)) == []


def test_json_unknown_only_populated_objects_remain_visible(tmp_path):
    record, = load_records(write_json(tmp_path, [{"custom": [1, 2]}]))
    assert record["custom"] == [1, 2]
    assert "malformed_row" in issue_codes(record)


def test_json_bom_and_nested_business_metadata(tmp_path):
    path = write_json(tmp_path, {"supplier": "A", "configuration": {"_source": "vendor document"}}, encoding="utf-8-sig")
    record, = load_records(path)
    assert record["configuration"] == {"_source": "vendor document"}
    assert record["_evidence"]["configuration"]["raw_value"] == {"_source": "vendor document"}


@pytest.mark.parametrize("field", ["quote_id", "_source", "_evidence", "_input_issues"])
def test_json_wrapper_metadata_injection_is_rejected(tmp_path, field):
    path = write_json(tmp_path, {"quotes": [{"supplier": "A"}], field: {"forged": True}})
    with pytest.raises(ValueError, match="reserved metadata"):
        load_records(path)


@pytest.mark.parametrize(
    "payload",
    ["{", "[1]", "[null]", '[{"supplier":"A"},true]', '{"quotes":{}}',
     '{"records":"bad"}', "null", "true", "123", '"text"',
     '{"quotes":[],"records":[]}', '{"quotes":[],"currency":"CNY"}',
     '{"prices":[true]}', '{"prices":["100"]}', '{"prices":[{}]}',
     '{"supplier":"A","":100}', '{"supplier":"A","price":NaN}',
     '{"supplier":"A","price":Infinity}', '{"supplier":"A","price":-Infinity}',
     '{"quotes":[],"quotes":[]}', '{"supplier":"A","configuration":{"x":1,"x":2}}'],
)
def test_invalid_json_shapes_and_duplicate_keys_have_actionable_errors(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_records(path)
    assert str(path) in str(error.value)
    assert "JSON" in str(error.value)


def test_json_malformed_record_reports_its_pointer(tmp_path):
    path = write_json(tmp_path, {"records": [{"supplier": "A"}, 5]})
    with pytest.raises(ValueError, match="/records/1"):
        load_records(path)


def test_json_invalid_encoding_is_actionable(tmp_path):
    path = tmp_path / "encoding.json"
    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        load_records(path)


@pytest.mark.parametrize("suffix", [".xls", ".pdf", ".txt", ""])
def test_unsupported_format_lists_supported_alternatives(tmp_path, suffix):
    with pytest.raises(ValueError, match=r"\.csv, \.xlsx, or \.json"):
        load_records(tmp_path / ("input" + suffix))


def test_missing_and_unreadable_files_raise_value_error(tmp_path, monkeypatch):
    path = tmp_path / "missing.csv"
    with pytest.raises(ValueError, match="Cannot read input file"):
        load_records(path)

    def deny_read(self):
        raise PermissionError("synthetic denied access")

    monkeypatch.setattr(Path, "read_bytes", deny_read)
    with pytest.raises(ValueError, match="synthetic denied access"):
        load_records(path)


def test_invalid_kind_is_actionable(tmp_path):
    with pytest.raises(ValueError, match="quotes, history, or market"):
        load_records(tmp_path / "input.csv", kind="other")
