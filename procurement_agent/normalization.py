"""Strict quotation normalization; unknown money is never silently made zero."""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Any

BUSINESS_FIELDS = set("""
supplier item_id item_name category specification configuration brand material grade
quantity unit currency unit_price_excl_tax unit_price_incl_tax total_price_excl_tax
total_price_incl_tax tax_rate freight installation packaging commissioning tooling
fee_basis fee_tax_rate freight_tax_rate installation_tax_rate packaging_tax_rate
commissioning_tax_rate tooling_tax_rate lead_time_days lead_time_weeks payment_days
payment_terms payment_anchor prepayment_percent warranty_months scope_complete quote_date
valid_until record_date record_type price price_basis notes source_url
""".split())
FEE_FIELDS = ("freight", "installation", "packaging", "commissioning", "tooling")
CENT = Decimal("0.01")
ZERO = Decimal(0)


def json_safe(value: Any) -> Any:
    """Preserve invalid source values as text rather than emitting nonstandard JSON."""
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def decimal_value(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("需要明确的数值")
    text = str(value).strip()
    if not text or len(text) > 100:
        raise ValueError("需要有效数值")
    if "," in text:
        if not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
            raise ValueError("千位分隔符格式不明确")
        text = text.replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("需要数值，单位应填写在单位列") from exc
    if not number.is_finite() or abs(number) > Decimal("1e15"):
        raise ValueError("数值须为有限值，绝对值不超过 10^15")
    if number != 0 and abs(number) < Decimal("1e-12"):
        raise ValueError("非零数值绝对值须至少为 10^-12，避免超出可审计精度")
    return number


def rate_value(value: Any) -> Decimal:
    percent = isinstance(value, str) and value.strip().endswith(("%", "％"))
    parsed = decimal_value(value.strip()[:-1] if percent else value)
    result = parsed / 100 if percent or parsed > 1 else parsed
    if result < 0 or result > 1:
        raise ValueError("税率须在 0% 至 100% 之间")
    return result


def as_number(value: Decimal | None, places: int = 6) -> float | None:
    if value is None:
        return None
    with localcontext() as context:
        context.prec = 60
        return float(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ValueError("日期须采用 YYYY-MM-DD 或 ISO 日期时间") from exc


def text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        import json
        return json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True)
    return " ".join(str(value).split())


def make_issue(quote: dict, code: str, field: str, message: str,
               severity: str = "blocker", question: str | None = None) -> dict:
    return {
        "quote_id": quote["quote_id"], "item_id": quote["item_id"],
        "supplier": quote["supplier"], "code": code, "severity": severity,
        "field": field, "message": message,
        "question": question or f"请核实{field}并提供报价单或书面确认依据：{message}",
    }


def normalize_quote(record: dict, *, reference: bool = False) -> tuple[dict, list[dict]]:
    raw = {k: v for k, v in record.items() if not k.startswith("_") and k != "quote_id"}
    supplier = text_value(raw.get("supplier"))
    item_id = text_value(raw.get("item_id") or raw.get("item_name"))
    quote = {
        "quote_id": record["quote_id"], "supplier": supplier or "未提供供应商",
        "item_id": item_id or f"unknown:{record['quote_id']}",
        "item_name": text_value(raw.get("item_name") or raw.get("item_id")),
        "raw_fields": json_safe(raw), "evidence": json_safe(record.get("_evidence", {})),
        "source": json_safe(record.get("_source", {})), "calculation_steps": [],
    }
    issues: list[dict] = []

    def issue(code: str, field: str, message: str, severity: str = "blocker") -> None:
        issues.append(make_issue(quote, code, field, message, severity))

    def numeric(field: str, *, required: bool = False, positive: bool = False,
                rate: bool = False) -> Decimal | None:
        value = raw.get(field)
        if value is None or value == "":
            if required:
                issue("missing_field", field, f"缺少 {field}；空白与零费用有不同含义")
            return None
        try:
            number = rate_value(value) if rate else decimal_value(value)
            if number < 0 or (positive and number == 0):
                raise ValueError("须大于零" if positive else "须大于或等于零")
            return number
        except ValueError as exc:
            issue("invalid_number", field, f"{field}：{exc}")
            return None

    if not supplier and not reference:
        issue("missing_field", "supplier", "缺少供应商名称")
    if not item_id:
        issue("missing_field", "item_id", "至少提供物料编码或物料名称")
    if not raw.get("item_id") and raw.get("item_name"):
        issue("name_as_item_key", "item_id", "按物料名称精确分组；建议维护统一物料编码", "warning")
    if not record.get("_source") or not record.get("_evidence"):
        issue("missing_evidence", "source", "缺少原始文件或字段证据")
    for item in record.get("_input_issues", []):
        issue(item["code"], item.get("field", "source"), item["message"])
    if "comparable" in raw and text_value(raw["comparable"]).lower() in {"false", "0", "否", "no"}:
        issue("not_comparable", "comparable", "原始报价已明确标记为不可比，请先核实原始技术口径")
    if raw.get("missing_fields"):
        issue("declared_missing_fields", "missing_fields", "原始报价声明存在缺失字段：" + text_value(raw["missing_fields"]))

    for field in ("specification", "configuration", "brand", "material", "grade", "notes"):
        quote[field] = text_value(raw.get(field))
    if not quote["specification"]:
        issue("missing_field", "specification", "缺少规格型号，技术等效性尚未确认")
    category_map = {"原材料": "raw_material", "材料": "raw_material", "模具": "mold", "设备": "equipment"}
    category = text_value(raw.get("category"))
    quote["category"] = category_map.get(category, category.lower())
    if quote["category"] not in {"raw_material", "mold", "equipment"}:
        issue("missing_or_invalid_category", "category", "采购类型应为原材料、模具或设备")
    unit_map = {"千克": "kg", "公斤": "kg", "吨": "t", "克": "g", "件": "pcs", "个": "pcs",
                "只": "pcs", "台": "unit", "套": "set", "米": "m", "平方米": "m2"}
    unit = text_value(raw.get("unit")).lower()
    quote["unit"] = unit_map.get(unit, unit)
    if not unit:
        issue("missing_field", "unit", "缺少计价单位")
    currency = text_value(raw.get("currency")).upper()
    quote["currency"] = {"人民币": "CNY", "RMB": "CNY", "元": "CNY"}.get(currency, currency)
    if not re.fullmatch(r"[A-Z]{3}", quote["currency"]):
        issue("invalid_currency", "currency", "币种须为三位代码，如 CNY、USD")
    quantity = numeric("quantity", required=True, positive=True)
    if quantity is not None and quantity > Decimal("1e9"):
        issue("invalid_number", "quantity", "数量超过本版本支持的 10^9 上限")
        quantity = None
    tax = numeric("tax_rate", required=True, rate=True)
    quote["quantity"], quote["tax_rate"] = float(quantity) if quantity is not None else None, as_number(tax)

    # Legacy values participate only when their precise unit/total and tax basis is explicit.
    if raw.get("price") not in (None, ""):
        basis = text_value(raw.get("price_basis"))
        target = {"unit_excl_tax": "unit_price_excl_tax", "unit_incl_tax": "unit_price_incl_tax",
                  "total_excl_tax": "total_price_excl_tax", "total_incl_tax": "total_price_incl_tax"}.get(basis)
        if target is None:
            issue("unknown_price_basis", "price_basis", "price 必须明确单价/总价及含税/未税口径")
        elif raw.get(target) not in (None, ""):
            issue("duplicate_price_representation", "price", "price 与专用金额字段同时提供，请保留一个事实来源")
        else:
            raw[target] = raw["price"]
            quote["calculation_steps"].append(f"price 按明示口径 {basis} 映射至 {target}")

    amounts = {field: numeric(field, positive=True) for field in (
        "unit_price_excl_tax", "unit_price_incl_tax", "total_price_excl_tax", "total_price_incl_tax")}
    if all(value is None for value in amounts.values()):
        issue("missing_price", "price", "未提供可计算的报价金额")
    unit_net, unit_gross = amounts["unit_price_excl_tax"], amounts["unit_price_incl_tax"]
    line_net, line_gross = amounts["total_price_excl_tax"], amounts["total_price_incl_tax"]
    if line_net is not None and line_gross is not None and tax is not None:
        if abs(line_gross - line_net * (1 + tax)) > CENT * 2:
            issue("tax_total_conflict", "total_price_incl_tax", "明确填写的含税总价与未税总价×(1+税率)不一致（误差超过0.02）")
    if quantity is not None:
        if unit_net is None and line_net is not None:
            unit_net = line_net / quantity
        if unit_gross is None and line_gross is not None:
            unit_gross = line_gross / quantity
    if tax is not None:
        if unit_net is None and unit_gross is not None:
            unit_net = unit_gross / (1 + tax)
            quote["calculation_steps"].append(f"未税单价 = 含税单价 {unit_gross} ÷ (1 + 税率 {tax})")
        if unit_gross is None and unit_net is not None:
            unit_gross = unit_net * (1 + tax)
        if unit_net is not None and unit_gross is not None and abs(unit_gross - unit_net * (1 + tax)) > CENT:
            issue("tax_price_conflict", "tax_rate", "含税价、未税价和税率不能互相校验（单价误差超过0.01）")
        if unit_net is not None and unit_gross is not None and quantity is not None:
            if abs((unit_gross - unit_net * (1 + tax)) * quantity) > CENT * 2:
                issue("tax_total_conflict", "tax_rate", "税价差额按采购数量折算超过0.02，请确认舍入口径或修正单价")
    if quantity is not None:
        if line_net is not None and unit_net is not None and abs(line_net - unit_net * quantity) > CENT * 2:
            issue("quantity_price_conflict", "total_price_excl_tax", "未税总价与单价×数量不一致（误差超过0.02）")
        if line_gross is not None and unit_gross is not None and abs(line_gross - unit_gross * quantity) > CENT * 2:
            issue("quantity_price_conflict", "total_price_incl_tax", "含税总价与单价×数量不一致（误差超过0.02）")
    quote["unit_price_excl_tax"] = as_number(unit_net)
    quote["unit_price_incl_tax"] = as_number(unit_gross)

    net_fees, gross_fees = ZERO, ZERO
    all_fees_known = True
    quote["fee_details"] = {}
    basis = {"未税": "excl_tax", "含税": "incl_tax"}.get(text_value(raw.get("fee_basis")), text_value(raw.get("fee_basis")))
    for field in FEE_FIELDS:
        value = raw.get(field)
        if field not in ("freight", "installation") and value in (None, ""):
            continue  # Covered by scope_complete, not asserted as a separate free service.
        if text_value(value).lower() in {"included", "已含", "已包含", "含在报价内", "不适用", "n/a"}:
            fee = ZERO
        else:
            fee = numeric(field, required=field in ("freight", "installation"))
        if fee is None:
            all_fees_known = False
            continue
        if fee == 0:
            quote["fee_details"][field] = {"excl_tax": 0.0, "incl_tax": 0.0}
            continue
        tax_field = f"{field}_tax_rate" if raw.get(f"{field}_tax_rate") not in (None, "") else "fee_tax_rate"
        fee_tax = numeric(tax_field, required=True, rate=True)
        if basis not in {"excl_tax", "incl_tax"}:
            issue("unknown_fee_basis", "fee_basis", f"{field} 为非零费用，须明确含税或未税口径")
            all_fees_known = False
            continue
        if fee_tax is None:
            all_fees_known = False
            continue
        net = fee if basis == "excl_tax" else fee / (1 + fee_tax)
        gross = fee * (1 + fee_tax) if basis == "excl_tax" else fee
        net_fees += net
        gross_fees += gross
        quote["fee_details"][field] = {"excl_tax": as_number(net), "incl_tax": as_number(gross), "tax_rate": as_number(fee_tax)}
        quote["calculation_steps"].append(f"{field}：原值 {fee}，{basis}，税率 {fee_tax}，未税折算 {as_number(net)}")
    quote["fees_excl_tax"] = as_number(net_fees, 2) if all_fees_known else None
    quote["normalized_total_excl_tax"] = (
        as_number(unit_net * quantity + net_fees, 2)
        if all_fees_known and unit_net is not None and quantity is not None and tax is not None else None)
    quote["normalized_total_incl_tax"] = (
        as_number(unit_gross * quantity + gross_fees, 2)
        if all_fees_known and unit_gross is not None and quantity is not None and tax is not None else None)
    quote["calculation_steps"].append("可比未税总成本 = 未税单价 × 数量 + 明示未税附加费用；费用按整行一次计入")

    scope = text_value(raw.get("scope_complete")).lower()
    quote["scope_complete"] = scope in {"true", "1", "是", "完整", "已确认", "yes"}
    if not quote["scope_complete"]:
        issue("scope_incomplete", "scope_complete", "报价范围尚未明确完整，请确认包装、安装调试、工装、软件和备件适用范围")
    lead = numeric("lead_time_days")
    weeks = numeric("lead_time_weeks")
    if lead is None and weeks is not None:
        lead = weeks * 7
        quote["calculation_steps"].append("交期天数 = 交期周数 × 7")
    if lead is not None and weeks is not None and abs(lead - weeks * 7) > Decimal("0.001"):
        issue("lead_time_conflict", "lead_time_days", "天和周两种交期表述不一致")
    if lead is None and not reference:
        issue("missing_field", "lead_time_days", "缺少明确交期天数或周数")
    payment = numeric("payment_days", required=not reference)
    warranty = numeric("warranty_months", required=not reference)
    prepayment = numeric("prepayment_percent")
    if prepayment is not None and prepayment > 100:
        issue("invalid_number", "prepayment_percent", "预付款比例须在0至100之间")
    quote.update(lead_time_days=as_number(lead), payment_days=as_number(payment),
                 warranty_months=as_number(warranty), prepayment_percent=as_number(prepayment))
    terms = text_value(raw.get("payment_terms"))
    quote["payment_terms"] = terms
    anchor = text_value(raw.get("payment_anchor")).lower()
    anchor = {"验收": "acceptance", "到货": "delivery", "发票": "invoice"}.get(anchor, anchor)
    inferred_anchor = ""
    if re.search(r"验收|acceptance", terms, re.I):
        inferred_anchor = "acceptance"
    elif re.search(r"发票|invoice", terms, re.I):
        inferred_anchor = "invoice"
    elif re.search(r"到货|货到|delivery", terms, re.I):
        inferred_anchor = "delivery"
    if not anchor:
        anchor = inferred_anchor
    quote["payment_anchor"] = anchor
    if not reference:
        if not terms:
            issue("missing_field", "payment_terms", "缺少原始付款条件")
        if anchor not in {"acceptance", "delivery", "invoice"}:
            issue("unknown_payment_anchor", "payment_anchor", "需明确账期从验收、到货还是收票开始计算")
        if inferred_anchor and anchor and anchor != inferred_anchor:
            issue("payment_anchor_conflict", "payment_anchor", "账期起算点与原始付款条款不一致")
        if re.search(r"预付|定金|首付|%|％|阶段|里程碑|deposit|milestone", terms, re.I) or (prepayment or ZERO) > 0:
            issue("complex_payment_terms", "payment_terms", "分阶段或预付款条款须由人工确认标准化账期及适用性")
        day_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:天|days?)", terms, re.I)
        if len(day_matches) == 1 and payment is not None and Decimal(day_matches[0]) != payment:
            issue("payment_days_conflict", "payment_days", "标准账期与付款条款中的天数不一致")

    for field in ("quote_date", "valid_until", "record_date"):
        value = raw.get(field)
        quote[field] = None
        if value not in (None, ""):
            try:
                quote[field] = parse_date(value).isoformat()
            except ValueError as exc:
                issue("invalid_date", field, str(exc))
    quote["record_type"] = text_value(raw.get("record_type")).lower()
    quote["source_url"] = text_value(raw.get("source_url"))
    return quote, issues
