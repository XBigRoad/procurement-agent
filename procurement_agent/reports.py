"""Read-only Chinese report projections of the shared comparison result.

Scores, reference values and decisions are copied from the engine. This module
does not rank suppliers, calculate prices or turn a candidate into a winner.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

CLASSIFICATION_NAMES = {
    "normal": "正常",
    "low_explained": "低价有合理解释",
    "abnormally_low": "异常低价",
    "high_explained": "高价有合理解释",
    "insufficient_data": "证据不足",
}
STATUS_NAMES = {
    "manual_review_required": "待人工复核",
    "conditional_recommendation": "有条件推荐",
    "within_reference_range": "处于参考范围",
    "review_required": "必须复核",
    "review_recommended": "建议复核",
}
CATEGORY_NAMES = {
    "raw_material": "原材料",
    "raw_materials": "原材料",
    "material": "原材料",
    "mold": "模具",
    "mould": "模具",
    "tooling": "模具",
    "equipment": "设备",
}
FIELD_NAMES = {
    "quote_id": "报价标识", "supplier": "供应商", "item_id": "物料编码",
    "item_name": "物料名称", "category": "采购类别", "rank": "候选排序",
    "score": "综合评分", "price_score": "价格加权得分",
    "lead_time_score": "交期加权得分", "payment_terms_score": "付款加权得分",
    "price_contribution": "价格加权贡献", "lead_time_contribution": "交期加权贡献",
    "payment_terms_contribution": "付款加权贡献", "contributions": "加权贡献明细",
    "score_breakdown": "评分计算明细", "classification": "价格分类",
    "eligible_for_recommendation": "引擎判定可推荐", "blockers": "阻断标记",
    "specification": "规格", "configuration": "配置", "brand": "品牌",
    "material": "材质", "grade": "牌号", "quantity": "数量", "unit": "单位",
    "currency": "币种", "unit_price_excl_tax": "未税单价",
    "unit_price_incl_tax": "含税单价", "total_price_excl_tax": "未税总价",
    "total_price_incl_tax": "含税总价", "tax_rate": "税率",
    "fees_excl_tax": "未税费用明细", "fee_basis": "费用计价口径",
    "fee_tax_rate": "费用税率", "freight": "运费", "installation": "安装费",
    "packaging": "包装费", "commissioning": "调试费", "tooling": "工装费",
    "normalized_total_excl_tax": "统一口径未税总额",
    "normalized_total_incl_tax": "统一口径含税总额",
    "lead_time_days": "交期（天）", "payment_days": "账期（天）",
    "payment_terms": "付款条件", "payment_anchor": "付款起算条件",
    "prepayment_percent": "预付款比例", "warranty_months": "质保（月）",
    "scope_complete": "报价范围完整", "quote_date": "报价日期",
    "valid_until": "有效期至", "raw_fields": "原始业务字段",
    "status": "状态", "flags": "风险标记", "reasons": "判定依据",
    "severity": "风险级别", "code": "风险代码", "field": "字段",
    "message": "问题说明", "question": "待确认问题",
    "reference_id": "参考标识", "reason": "原因", "file": "来源文件",
    "sha256": "文件SHA256", "format": "格式", "sheet": "工作表",
    "row": "原始行号", "column": "原始列号", "cell": "原始单元格",
    "json_pointer": "JSON位置", "raw_value": "原始值", "formula": "原始公式文本",
    "reviewer": "复核人", "reviewed_at": "复核时间", "before": "修改前",
    "after": "修改后", "value": "复核值", "evidence": "证据引用",
    "kind": "复核类型", "action": "复核动作", "notes": "备注",
    "source_url": "来源链接", "record_date": "记录日期", "record_type": "记录类型",
    "effective_fields": "复核后有效字段", "reviewed_fields": "逐字段复核记录",
    "calculation_steps": "计算步骤", "calculation_step": "计算步骤原文",
    "step_index": "步骤序号", "source": "来源元数据", "reference_role": "参考类别",
    "matched_quote_ids": "匹配报价标识", "reference_ids": "参考引用标识",
    "record_role": "记录类别", "field_name": "字段名称", "original_present": "原始已提供",
    "original_value": "原始业务值", "effective_value": "本次有效值",
    "normalized_value": "标准化结果", "reviewed": "已人工修正",
}

Table = tuple[list[str], list[list[Any]]]


def _text(value: Any) -> str:
    if value is None:
        return "未提供"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _joined(values: Any) -> str:
    if isinstance(values, (list, tuple)):
        return "、".join(_text(value) for value in values) or "无"
    return _text(values) if values is not None else "无"


def decision_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project only explicit decisions, preserving a null recommendation.

    The batch gate also applies to item projections. A defensive closed display
    prevents an inconsistent/stale item recommendation leaking from a blocked run.
    Neither the top-level legacy mirror nor rank is a recommendation source.
    """
    decision = result.get("procurement_decision") or {}
    status = decision.get("status", "manual_review_required")
    allowed = status == "conditional_recommendation" and not decision.get("blocking_flags")
    rows = [{
        "范围": "本批次",
        "状态": STATUS_NAMES.get(status, _text(status)),
        "推荐供应商": decision.get("recommended_supplier") if allowed else None,
        "候选供应商": decision.get("candidate_suppliers") or [],
        "阻断标记": decision.get("blocking_flags") or [],
        "说明": decision.get("reason"),
    }]
    for item in result.get("item_results", []):
        item_status = item.get("status", status)
        rows.append({
            "范围": item.get("item_id"),
            "状态": STATUS_NAMES.get(item_status, _text(item_status)),
            "推荐供应商": (
                item.get("recommended_supplier")
                if allowed and item_status == "conditional_recommendation" else None
            ),
            "候选供应商": item.get("candidate_suppliers") or [],
            "阻断标记": item.get("blocking_flags") or [],
            "说明": item.get("reason"),
        })
    return rows


def _sections(result: Mapping[str, Any]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {
        "结论": [], "事实": [], "计算": [], "假设": [],
        "风险": [], "建议": [], "待确认问题": [], "证据": [],
    }
    decisions = decision_rows(result)
    for row in decisions:
        recommendation = row["推荐供应商"]
        sections["结论"].extend([
            f"{row['范围']}：{row['状态']}",
            f"推荐供应商：{recommendation if recommendation is not None else '暂不形成推荐'}",
            f"候选供应商：{_joined(row['候选供应商'])}",
        ])
        if row["说明"]:
            sections["结论"].append(_text(row["说明"]))
        if row["阻断标记"]:
            sections["风险"].append(f"{row['范围']}阻断标记：{_joined(row['阻断标记'])}")

    sections["事实"].append(
        f"运行标识：{_text(result.get('run_id'))}；分析日期：{_text(result.get('as_of'))}；"
        f"报价记录数：{len(result.get('quotes', []))}。"
    )
    for quote in result.get("quotes", []):
        sections["事实"].append(
            f"{_text(quote.get('item_id'))} / {_text(quote.get('supplier'))} "
            f"[{_text(quote.get('quote_id'))}]：规格 {_text(quote.get('specification'))}；"
            f"数量 {_text(quote.get('quantity'))} {_text(quote.get('unit'))}；"
            f"币种 {_text(quote.get('currency'))}；交期 {_text(quote.get('lead_time_days'))} 天；"
            f"账期 {_text(quote.get('payment_days'))} 天。"
        )
    sections["计算"].append(f"本次权重：{_text(result.get('weights'))}。数值引用统一计算引擎结果。")
    for row in result.get("rankings", []):
        sections["计算"].append(
            f"{_text(row.get('item_id'))} / {_text(row.get('supplier'))}："
            f"候选排序 {_text(row.get('rank'))}，综合评分 {_text(row.get('score'))}；"
            f"价格 / 交期 / 付款加权得分 {_text(row.get('price_score'))} / "
            f"{_text(row.get('lead_time_score'))} / {_text(row.get('payment_terms_score'))}；"
            f"统一口径未税总额 {_text(row.get('normalized_total_excl_tax'))} "
            f"{_text(row.get('currency'))}。"
        )
    baseline_names = {
        "peer": "本批可比报价", "history": "公司采购历史",
        "supplier_history": "同供应商历史报价", "market": "提供的市场参考",
    }
    for finding in result.get("findings", []):
        classification = finding.get("classification")
        sections["计算"].append(
            f"{_text(finding.get('item_id'))} / {_text(finding.get('supplier'))}："
            f"{CLASSIFICATION_NAMES.get(classification, _text(classification))}；"
            f"判定依据：{_joined(finding.get('reasons'))}。"
        )
        for family, label in baseline_names.items():
            median = finding.get(f"{family}_median")
            delta = finding.get(f"{family}_delta")
            delta_text = f"{delta:.2%}" if isinstance(delta, (int, float)) else _text(delta)
            sections["计算"].append(
                f"  {label}：中位数 {_text(median)}；相对偏离 {delta_text}。"
            )
    sections["假设"] = [_text(value) for value in result.get("assumptions", [])]
    if not sections["假设"]:
        sections["假设"].append("引擎未列出额外假设；缺失信息保留为待确认。")
    for issue in result.get("issues", []):
        context = f"{_text(issue.get('item_id'))} / {_text(issue.get('supplier'))}"
        sections["风险"].append(
            f"{context} [{_text(issue.get('severity'))}/{_text(issue.get('code'))}] "
            f"{_text(issue.get('message'))}"
        )
        if issue.get("question"):
            sections["待确认问题"].append(f"{context}：{issue['question']}")
    for exclusion in result.get("reference_exclusions", []):
        sections["风险"].append(
            f"排除参考 {_text(exclusion.get('reference_id'))}：{_text(exclusion.get('reason'))}"
        )
    if not sections["风险"]:
        sections["风险"].append("本次引擎未列出风险；结论适用范围以本批输入和规则为准。")
    if decisions[0]["状态"] == STATUS_NAMES["conditional_recommendation"]:
        sections["建议"].append("按物料分别复核有条件推荐，确认技术、商务和证据后履行企业审批流程。")
    else:
        sections["建议"].append("先处理阻断项，补充原始证明；由具名复核人填写复核文件后重新计算。")
    sections["建议"].append("候选排序用于比较；最终采购决定由企业授权人员作出。")
    if not sections["待确认问题"]:
        sections["待确认问题"].append("引擎未列出专项问题；采购人员仍应确认技术配置、供货范围和商务条件。")
    sections["证据"].append(f"输入绑定摘要：{_text(result.get('input_digest'))}")
    for source in result.get("input_files", []):
        sections["证据"].append(
            f"来源文件：{_text(source.get('file'))}；SHA256：{_text(source.get('sha256'))}"
        )
    evidence = evidence_records(result)
    sections["证据"].append(
        f"字段原始证据 {len(evidence)} 条；人工复核记录 {len(result.get('audit_log', []))} 条。"
        "逐字段原值、位置及修改前后值见 Excel 原始证据 / 人工复核页与完整 JSON。"
    )
    return sections


def build_advice(result: Mapping[str, Any]) -> str:
    """Return plain Chinese advice with facts and interpretations kept distinct."""
    return "采购报价审核建议\n\n" + "\n\n".join(
        f"【{title}】\n" + "\n".join(lines) for title, lines in _sections(result).items()
    ) + "\n"


def evidence_records(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expose original evidence without substituting reviewed business values."""
    if "evidence" in result:
        return [dict(row) for row in result.get("evidence", [])]
    records = []
    for quote in result.get("quotes", []):
        for field, evidence in (quote.get("evidence") or {}).items():
            records.append({
                **evidence, "quote_id": quote.get("quote_id"),
                "supplier": quote.get("supplier"), "field": field,
            })
    return records


def _records_table(records: Iterable[Mapping[str, Any]], columns: list[str]) -> Table:
    records = list(records)
    keys = list(columns)
    for record in records:
        for key in record:
            if key not in keys:
                keys.append(key)
    rows = []
    for record in records:
        row = []
        for key in keys:
            value = record.get(key)
            if key == "classification":
                value = CLASSIFICATION_NAMES.get(value, value)
            elif key == "status":
                value = STATUS_NAMES.get(value, value)
            elif key == "category":
                value = CATEGORY_NAMES.get(value, value)
            row.append(value)
        rows.append(row)
    return [FIELD_NAMES.get(key, key) for key in keys], rows


def _field_comparisons(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Join the engine's original, effective and normalized values by field."""
    rows = []
    for quote in result.get("quotes", []):
        original = quote.get("raw_fields") or {}
        effective = quote.get("effective_fields") or {}
        reviewed = quote.get("reviewed_fields") or {}
        for field in dict.fromkeys([*original, *effective, *reviewed]):
            audit = reviewed.get(field) or {}
            rows.append({
                "item_id": quote.get("item_id"), "supplier": quote.get("supplier"),
                "quote_id": quote.get("quote_id"), "field": field,
                "field_name": FIELD_NAMES.get(field, field),
                "original_present": field in original, "original_value": original.get(field),
                "effective_value": effective.get(field), "normalized_value": quote.get(field),
                "reviewed": field in reviewed, "reviewer": audit.get("reviewer"),
                "reviewed_at": audit.get("reviewed_at"), "reason": audit.get("reason"),
                "evidence": audit.get("evidence"),
            })
    return rows


def report_tables(result: Mapping[str, Any]) -> dict[str, Table]:
    """Build the shared display/export tables without modifying the result."""
    advice_rows: list[list[Any]] = []
    for row in decision_rows(result):
        for key, value in row.items():
            if key != "范围":
                advice_rows.append([key, row["范围"], value])
    for section, lines in _sections(result).items():
        advice_rows.extend([section, "本批次", line] for line in lines)
    tables = {"采购建议": (["类别", "对象", "内容"], advice_rows)}
    tables["供应商评分"] = _records_table(result.get("rankings", []), [
        "item_id", "supplier", "rank", "normalized_total_excl_tax", "currency", "score",
        "classification", "lead_time_days", "payment_days", "price_score",
        "lead_time_score", "payment_terms_score", "eligible_for_recommendation", "blockers", "quote_id",
    ])
    tables["报价明细"] = _records_table(result.get("quotes", []), [
        "item_id", "item_name", "supplier", "quote_id", "category", "specification",
        "configuration", "quantity", "unit", "currency", "unit_price_excl_tax",
        "unit_price_incl_tax", "tax_rate", "fees_excl_tax",
        "normalized_total_excl_tax", "normalized_total_incl_tax", "lead_time_days",
        "payment_days", "payment_terms", "warranty_months", "scope_complete", "raw_fields",
        "effective_fields", "calculation_steps",
    ])
    tables["字段对照"] = _records_table(_field_comparisons(result), [
        "item_id", "supplier", "quote_id", "field", "field_name", "original_present",
        "original_value", "effective_value", "normalized_value", "reviewed", "reviewer",
        "reviewed_at", "reason", "evidence",
    ])
    steps = []
    for role, records in (("报价", result.get("quotes", [])),
                          ("参考", result.get("reference_records", []))):
        for quote in records:
            for index, step in enumerate(quote.get("calculation_steps") or [], start=1):
                steps.append({
                    "record_role": role, "item_id": quote.get("item_id"),
                    "supplier": quote.get("supplier"), "quote_id": quote.get("quote_id"),
                    "step_index": index, "calculation_step": step,
                })
    tables["计算明细"] = _records_table(steps, [
        "record_role", "item_id", "supplier", "quote_id", "step_index", "calculation_step",
    ])
    tables["风险与确认"] = _records_table(result.get("issues", []), [
        "item_id", "supplier", "quote_id", "severity", "code", "field", "message", "question",
    ])
    baseline_columns = ["item_id", "supplier", "quote_id", "classification", "status", "reasons"]
    for family in ("peer", "history", "supplier_history", "market"):
        baseline_columns.extend([f"{family}_median", f"{family}_delta", f"{family}_reference_ids"])
    baselines = []
    for finding in result.get("findings", []):
        row = dict(finding)
        references = finding.get("reference_ids") or {}
        for family in ("peer", "history", "supplier_history", "market"):
            row[f"{family}_reference_ids"] = finding.get(
                f"{family}_reference_ids", references.get(family, []),
            )
        baselines.append(row)
    tables["价格参考"] = _records_table(baselines, baseline_columns)
    # Translate the baseline headers while preserving additional engine fields.
    labels = {"peer": "同批报价", "history": "公司采购历史",
              "supplier_history": "同供应商历史", "market": "市场参考"}
    headers, rows = tables["价格参考"]
    translations = {
        f"{family}_{suffix}": f"{label}{display}"
        for family, label in labels.items()
        for suffix, display in (("median", "中位数"), ("delta", "偏离率"),
                                ("reference_ids", "引用标识"))
    }
    tables["价格参考"] = ([translations.get(header, header) for header in headers], rows)
    tables["参考明细"] = _records_table(result.get("reference_records", []), [
        "quote_id", "reference_role", "record_type", "record_date", "supplier", "item_id",
        "specification", "configuration", "quantity", "unit", "currency",
        "normalized_total_excl_tax", "normalized_total_incl_tax", "matched_quote_ids",
        "source", "raw_fields", "calculation_steps",
    ])
    tables["参考排除"] = _records_table(result.get("reference_exclusions", []), [
        "reference_id", "reason",
    ])
    tables["原始证据"] = _records_table(evidence_records(result), [
        "quote_id", "supplier", "field", "raw_value", "file", "sha256", "format",
        "sheet", "row", "column", "cell", "json_pointer", "formula",
    ])
    tables["人工复核"] = _records_table(result.get("audit_log", []), [
        "quote_id", "reviewer", "reviewed_at", "kind", "field", "before", "after",
        "reason", "evidence",
    ])
    config_rows = [["运行", field, result.get(field)] for field in (
        "schema_version", "run_id", "input_digest", "generated_at", "as_of",
    )]
    for field in ("weights", "policy"):
        config_rows.extend([field, key, value] for key, value in (result.get(field) or {}).items())
    config_rows.extend(["价格分类", key, value] for key, value in CLASSIFICATION_NAMES.items())
    config_rows.extend(["假设", index, value] for index, value in enumerate(
        result.get("assumptions", []), start=1,
    ))
    tables["规则配置"] = (["类别", "配置项", "值"], config_rows)
    tables["输入文件"] = _records_table(result.get("input_files", []), [
        "file", "sha256", "format",
    ])
    return tables


def _cell_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _number_format(header: str) -> str:
    if any(word in header for word in ("税率", "比例", "偏离率", "_delta")):
        return "0.00%"
    if any(word in header for word in ("金额", "总额", "单价", "总价", "中位数")):
        return '#,##0.00;[Red]-#,##0.00'
    if any(word in header for word in ("得分", "评分", "贡献", "数量")):
        return "0.00"
    return "0.########"


def write_excel(result: Mapping[str, Any], path: Path) -> None:
    """Write an auditable workbook; all input strings remain literal text.

    Excel cannot represent every possible JSON string. Reject unrepresentable
    control characters/oversized cells explicitly instead of silently truncating
    evidence. The UI can still offer the complete JSON and text downloads.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)
    font = Font(name="Microsoft YaHei", size=10)
    header_font = Font(name="Microsoft YaHei", size=10, bold=True)
    underline = Border(bottom=Side(style="thin", color="B8C1CC"))
    try:
        for title, (headers, rows) in report_tables(result).items():
            if len(rows) >= 1_048_576 or len(headers) > 16_384:
                raise ValueError(f"{title} 超出 Excel 行列限制，请使用完整 JSON。")
            sheet = workbook.create_sheet(title)
            sheet.sheet_view.showGridLines = False
            widths = [min(34, max(14, len(header) * 2 + 2)) for header in headers]
            for row_index, row in enumerate([headers, *rows], start=1):
                for column_index, value in enumerate(row, start=1):
                    value = _cell_value(value)
                    if isinstance(value, str) and (
                        len(value) > 32767 or ILLEGAL_CHARACTERS_RE.search(value)
                    ):
                        raise ValueError(
                            f"{title} 第 {row_index} 行第 {column_index} 列包含 Excel "
                            "无法完整保存的文本，请使用完整 JSON。"
                        )
                    cell = sheet.cell(row=row_index, column=column_index, value=value)
                    if isinstance(value, str):
                        # openpyxl otherwise interprets '=' as a formula and
                        # Excel error literals as errors. Preserve the exact text.
                        cell.data_type = "s"
                        cell.number_format = "@"
                    elif isinstance(value, (int, float)) and not isinstance(value, bool):
                        cell.number_format = _number_format(headers[column_index - 1])
                    cell.font = header_font if row_index == 1 else font
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    if row_index == 1:
                        cell.border = underline
                    if value is not None:
                        display_width = sum(2 if ord(char) > 127 else 1 for char in str(value)[:100])
                        widths[column_index - 1] = min(48, max(widths[column_index - 1], display_width + 2))
                sheet.row_dimensions[row_index].height = 30 if row_index == 1 else 36
            for column_index, width in enumerate(widths, start=1):
                sheet.column_dimensions[get_column_letter(column_index)].width = width
            for row in sheet.iter_rows(min_row=2):
                line_count = 1
                for cell, width in zip(row, widths, strict=True):
                    if cell.value is None:
                        continue
                    wrapped_lines = sum(
                        max(1, math.ceil(sum(2 if ord(char) > 127 else 1 for char in line) / (width - 2)))
                        for line in str(cell.value).split("\n")
                    )
                    line_count = max(line_count, wrapped_lines)
                sheet.row_dimensions[row[0].row].height = min(150, max(30, line_count * 14 + 6))
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            sheet.print_options.horizontalCentered = False
            sheet.sheet_properties.pageSetUpPr.fitToPage = True
            sheet.page_setup.orientation = "landscape"
            sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
            sheet.page_setup.fitToWidth = 1
            sheet.page_setup.fitToHeight = 0
            sheet.print_title_rows = "1:1"
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(target)
    finally:
        workbook.close()
