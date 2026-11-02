"""Authoritative, deterministic quotation review and human-review replay engine."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from statistics import median

from .normalization import (
    BUSINESS_FIELDS,
    as_number,
    decimal_value,
    json_safe,
    make_issue,
    normalize_quote,
    parse_date,
)
from .scoring import score_candidates, validate_weights

DEFAULT_POLICY = {
    "low_threshold": 0.20, "high_threshold": 0.20,
    "history_max_age_days": 365, "market_max_age_days": 90,
    "require_full_package": False,
}
MATCH_FIELDS = (
    "item_id", "category", "specification", "configuration", "brand", "material",
    "grade", "quantity", "unit", "currency",
)
COMPARISON_FIELDS = MATCH_FIELDS[1:] + ("payment_anchor",)
CLASSIFICATION_ZH = {
    "normal": "正常报价", "low_explained": "偏低但可以解释",
    "abnormally_low": "异常低价，需要确认", "high_explained": "偏高但配置或服务更完整",
    "insufficient_data": "信息不足，无法判断",
}


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(json_safe(payload), ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _input_identity(records: list[dict]) -> list[dict]:
    """Bind reviews to source bytes and business values, not temporary upload paths."""
    rows = []
    for record in records:
        source = {key: value for key, value in record.get("_source", {}).items() if key != "file"}
        values = {key: value for key, value in record.items() if not key.startswith("_")}
        problems = [{"code": item.get("code"), "field": item.get("field")}
                    for item in record.get("_input_issues", [])]
        rows.append({"id": record["quote_id"], "source": source, "values": values, "input_issues": problems})
    return sorted(rows, key=lambda row: row["id"])


def validate_policy(policy: dict | None) -> dict:
    if policy is not None and (not isinstance(policy, dict) or set(policy) - set(DEFAULT_POLICY)):
        raise ValueError("规则配置包含未知字段；请参照 DATA_CONTRACT 和默认规则")
    output = {**DEFAULT_POLICY, **(policy or {})}
    for key in ("low_threshold", "high_threshold"):
        value = decimal_value(output[key])
        if not Decimal(0) < value < Decimal(1):
            raise ValueError(f"{key} 须大于0且小于1")
        output[key] = float(value)
    for key in ("history_max_age_days", "market_max_age_days"):
        value = decimal_value(output[key])
        if value != value.to_integral_value() or value < 0 or value > 36500:
            raise ValueError(f"{key} 须为0至36500之间的整数")
        output[key] = int(value)
    if not isinstance(output["require_full_package"], bool):
        raise ValueError("require_full_package 须为布尔值")
    return output


def _validate_records(records: list[dict], label: str) -> list[dict]:
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError(f"{label}须为结构化记录列表")
    output = copy.deepcopy(records)
    ids = set()
    for index, row in enumerate(output):
        row.setdefault("quote_id", f"{label}-{index + 1}-{_digest(row)[:12]}")
        row_id = row["quote_id"]
        if not isinstance(row_id, str) or not row_id:
            raise ValueError(f"{label}存在无效记录编号")
        if row_id in ids:
            raise ValueError(f"重复输入记录 {row_id}；请检查是否重复上传同一文件")
        ids.add(row_id)
    return output


def _apply_review(records: list[dict], review: dict | None, digest: str) -> tuple[list[dict], list[dict], dict]:
    working = copy.deepcopy(records)
    if review is None:
        return working, [], {}
    expected = {"input_digest", "reviewer", "reviewed_at", "corrections", "explanations"}
    if not isinstance(review, dict) or set(review) - expected:
        raise ValueError("复核文件格式错误或包含未知字段")
    if review.get("input_digest") != digest:
        raise ValueError("复核文件与当前原始报价、参考数据、日期或评分规则不匹配；请重新导出复核模板")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("人工复核必须填写复核人")
    try:
        reviewed_at = datetime.fromisoformat(str(review.get("reviewed_at", "")).replace("Z", "+00:00"))
        if reviewed_at.tzinfo is None:
            raise ValueError("missing timezone")
    except ValueError as exc:
        raise ValueError("复核时间须为带时区的ISO日期时间") from exc
    lookup = {row["quote_id"]: row for row in working}
    audit, explanations = [], {}
    for collection in ("corrections", "explanations"):
        changes = review.get(collection, [])
        if not isinstance(changes, list):
            raise ValueError(f"复核 {collection} 须为列表")
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("每条人工复核须为一个对象")
            allowed = {"quote_id", "reason", "evidence", "field", "value"} if collection == "corrections" else {"quote_id", "reason", "evidence", "kind"}
            if set(change) - allowed:
                raise ValueError("复核条目包含未知字段")
            row_id = change.get("quote_id")
            if row_id not in lookup:
                raise ValueError(f"人工复核指向未知报价 {row_id}")
            for key in ("reason", "evidence"):
                if not isinstance(change.get(key), str) or not change[key].strip():
                    raise ValueError("每条人工修改/解释均须填写原因和书面证据引用")
            entry = {
                "quote_id": row_id, "reviewer": reviewer.strip(),
                "reviewed_at": reviewed_at.isoformat(), "reason": change["reason"].strip(),
                "evidence": change["evidence"].strip(), "input_digest": digest,
                "action": collection,
            }
            if collection == "corrections":
                field = change.get("field")
                if field not in BUSINESS_FIELDS or "value" not in change:
                    raise ValueError("只能修正已定义业务字段，原始证据、编号和计算结果保持不可修改")
                row = lookup[row_id]
                entry.update(field=field, before=json_safe(row.get(field)), after=json_safe(change["value"]))
                row[field] = change["value"]
                row.setdefault("_reviewed_fields", {})[field] = dict(entry)
                row["_input_issues"] = [item for item in row.get("_input_issues", []) if item.get("field") != field]
            else:
                kind = change.get("kind")
                if kind not in {"low_price", "premium", "payment_terms"}:
                    raise ValueError("解释类型须为 low_price、premium 或 payment_terms")
                if (row_id, kind) in explanations:
                    raise ValueError("同一报价的同类解释重复，请保留唯一确认记录")
                entry.update(kind=kind, before="待人工复核", after="已记录人工解释，重新计算后判断")
                explanations[(row_id, kind)] = entry
            audit.append(entry)
    return working, audit, explanations


def create_review_template(result: dict) -> dict:
    corrections, explanations = [], []
    for entry in result.get("audit_log", []):
        common = {key: entry[key] for key in ("quote_id", "reason", "evidence")}
        if entry.get("action") == "corrections":
            corrections.append({**common, "field": entry["field"], "value": entry["after"]})
        elif entry.get("action") == "explanations":
            explanations.append({**common, "kind": entry["kind"]})
    return {
        "input_digest": result["input_digest"], "reviewer": "",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "corrections": corrections, "explanations": explanations,
    }


def _reference_rows(history: list[dict], market: list[dict], quotes: list[dict],
                    policy: dict, as_of: date) -> tuple[list[dict], list[dict], list[dict]]:
    valid, exclusions, all_normalized = [], [], []
    quotation_ids = {quote["quote_id"] for quote in quotes}
    quotation_hashes = {quote["source"].get("sha256") for quote in quotes if quote["source"].get("sha256")}
    seen_references: set[str] = set()
    for role, records in (("history", history), ("market", market)):
        for record in records:
            normalized, problems = normalize_quote(record, reference=True)
            normalized["reference_role"] = role
            all_normalized.append(normalized)
            reasons = [issue["message"] for issue in problems if issue["severity"] == "blocker"]
            if normalized["quote_id"] in quotation_ids or normalized["source"].get("sha256") in quotation_hashes:
                reasons.append("本批报价文件不能同时作为独立历史价或市场参考")
            if normalized["quote_id"] in seen_references:
                reasons.append("该参考记录已在其他参考来源中出现，保留一次以避免重复加权")
            seen_references.add(normalized["quote_id"])
            recorded = normalized["record_date"] or normalized["quote_date"]
            if not recorded:
                reasons.append("参考价缺少明确日期")
            else:
                age = (as_of - date.fromisoformat(recorded)).days
                if age < 0:
                    reasons.append("参考日期晚于分析日期")
                elif age > policy[f"{role}_max_age_days"]:
                    reasons.append(f"参考价超过 {policy[f'{role}_max_age_days']} 天时效范围")
            kind = {"采购": "purchase", "历史采购": "purchase", "报价": "quotation", "历史报价": "quotation"}.get(normalized["record_type"], normalized["record_type"])
            if role == "history":
                if kind not in {"purchase", "quotation"}:
                    reasons.append("历史记录须明确标注类型 purchase 或 quotation")
            normalized["record_type"] = kind
            matches = [q["quote_id"] for q in quotes if all(q.get(k) == normalized.get(k) for k in MATCH_FIELDS)]
            if not matches:
                reasons.append("物料、类型、规格配置、数量、单位或币种与本批报价不匹配")
            if not normalized["normalized_total_excl_tax"]:
                reasons.append("参考价缺少可用的统一口径金额")
            if reasons:
                exclusions.append({
                    "reference_id": normalized["quote_id"], "role": role,
                    "reason": "；".join(dict.fromkeys(reasons)), "source": normalized["source"],
                })
            else:
                normalized["matched_quote_ids"] = matches
                valid.append(normalized)
    return valid, exclusions, all_normalized


def _median(values: list[float]) -> Decimal | None:
    return median([decimal_value(value) for value in values]) if values else None


def _delta(value: float | None, reference: Decimal | None) -> Decimal | None:
    if value is None or reference is None or reference <= 0:
        return None
    return (decimal_value(value) - reference) / reference


def compare_records(quotes: list[dict], *, history: list[dict] | None = None,
                    market: list[dict] | None = None, weights: dict | None = None,
                    policy: dict | None = None, review: dict | None = None,
                    as_of: str | None = None) -> dict:
    """Compute auditable candidates; every recommendation remains human-conditional."""
    weights = validate_weights(weights)
    policy = validate_policy(policy)
    analysis_date = parse_date(as_of) if as_of else date.today()
    originals = _validate_records(quotes, "quotes")
    history = _validate_records(history or [], "history")
    market = _validate_records(market or [], "market")
    if len(originals) < 2:
        raise ValueError("至少需要两条报价，并由至少两家不同供应商参与比较")
    input_digest = _digest({"quotes": _input_identity(originals),
                            "history": _input_identity(history), "market": _input_identity(market),
                            "weights": weights, "policy": policy, "as_of": analysis_date.isoformat()})
    working, audit, explanations = _apply_review(originals, review, input_digest)
    normalized, issues = [], []
    original_lookup = {row["quote_id"]: row for row in originals}
    for row in working:
        quote, found = normalize_quote(row)
        if (quote["quote_id"], "payment_terms") in explanations:
            found = [item for item in found if item["code"] != "complex_payment_terms"]
        quote["reviewed_fields"] = json_safe(row.get("_reviewed_fields", {}))
        quote["effective_fields"] = quote["raw_fields"]
        quote["raw_fields"] = json_safe({k: v for k, v in original_lookup[row["quote_id"]].items()
                                         if not k.startswith("_") and k != "quote_id"})
        normalized.append(quote)
        issues.extend(found)
        for field in ("quote_date", "valid_until"):
            value = quote[field]
            if value and field == "quote_date" and date.fromisoformat(value) > analysis_date:
                issues.append(make_issue(quote, "future_quote", field, "报价日期晚于分析日期"))
            if value and field == "valid_until" and date.fromisoformat(value) < analysis_date:
                issues.append(make_issue(quote, "expired_quote", field, "报价已过有效期，请取得更新报价"))
        if quote["quote_date"] and quote["valid_until"] and quote["valid_until"] < quote["quote_date"]:
            issues.append(make_issue(quote, "invalid_validity_range", "valid_until", "有效期早于报价日期"))
        if not quote["quote_date"] or not quote["valid_until"]:
            issues.append(make_issue(quote, "quote_validity_unstated", "quote_date", "报价日期或有效期未注明，审批前需补充确认", "warning"))
        if quote["normalized_total_excl_tax"] is not None and quote["normalized_total_excl_tax"] <= 0:
            issues.append(make_issue(quote, "invalid_normalized_total", "price", "统一金额在货币精度下须大于零"))

    supplier_names = {q["supplier"] for q in normalized if q["supplier"] != "未提供供应商"}
    if len(supplier_names) < 2:
        raise ValueError("至少需要两家不同供应商；同一供应商多行或多份报价不构成竞价")
    groups: dict[str, list[dict]] = defaultdict(list)
    for quote in normalized:
        groups[quote["item_id"]].append(quote)
    incomparable_items: set[str] = set()
    for item_id, group in groups.items():
        differences = [field for field in COMPARISON_FIELDS if len({json.dumps(q.get(field), ensure_ascii=False, sort_keys=True) for q in group}) > 1]
        if differences:
            incomparable_items.add(item_id)
            for quote in group:
                issues.append(make_issue(quote, "not_comparable", ",".join(differences),
                                         "本物料报价存在口径或技术差异：" + "、".join(differences)))
        counts: dict[str, int] = defaultdict(int)
        for quote in group:
            counts[quote["supplier"]] += 1
        for quote in group:
            if counts[quote["supplier"]] > 1:
                incomparable_items.add(item_id)
                issues.append(make_issue(quote, "duplicate_supplier_item", "supplier", "同一供应商对同一物料存在多条报价，请明确有效版本或拆分采购项"))
        if len(counts) < 2:
            incomparable_items.add(item_id)
            issues.append(make_issue(group[0], "insufficient_competition", "supplier", "本物料不足两家供应商，需补充报价或按单一来源流程复核"))
    if policy["require_full_package"]:
        for supplier in supplier_names:
            supplied = {q["item_id"] for q in normalized if q["supplier"] == supplier}
            missing = set(groups) - supplied
            if missing:
                quote = next(q for q in normalized if q["supplier"] == supplier)
                issues.append(make_issue(quote, "missing_package_items", "item_id", "整包报价缺少物料：" + "、".join(sorted(missing))))

    valid_references, exclusions, reference_quotes = _reference_rows(history, market, normalized, policy, analysis_date)
    input_blockers = defaultdict(list)
    for issue in issues:
        if issue["severity"] == "blocker":
            input_blockers[issue["quote_id"]].append(issue)
    findings = []
    for quote in normalized:
        row_id, item_id = quote["quote_id"], quote["item_id"]
        peers = [q for q in groups[item_id] if not input_blockers[q["quote_id"]] and q["normalized_total_excl_tax"] is not None]
        peer_values = [q["normalized_total_excl_tax"] for q in peers] if item_id not in incomparable_items and len(peers) >= 2 else []
        matched = [r for r in valid_references if row_id in r["matched_quote_ids"]]
        company = [r for r in matched if r["reference_role"] == "history" and r["record_type"] == "purchase"]
        supplier_history = [r for r in matched if r["reference_role"] == "history" and r["record_type"] == "quotation" and r["supplier"] == quote["supplier"]]
        markets = [r for r in matched if r["reference_role"] == "market"]
        references = {"peer": peers if peer_values else [], "history": company,
                      "supplier_history": supplier_history, "market": markets}
        finding = {"quote_id": row_id, "supplier": quote["supplier"], "item_id": item_id,
                   "flags": [], "reasons": [], "reference_ids": {key: [r["quote_id"] for r in rows] for key, rows in references.items()}}
        low_signals, high_signals = [], []
        for family, rows in references.items():
            baseline = _median([r["normalized_total_excl_tax"] for r in rows])
            delta = _delta(quote["normalized_total_excl_tax"], baseline)
            finding[f"{family}_median"] = as_number(baseline, 2)
            finding[f"{family}_delta"] = as_number(delta)
            if delta is not None:
                if delta <= -decimal_value(policy["low_threshold"]):
                    low_signals.append((family, delta))
                if delta >= decimal_value(policy["high_threshold"]):
                    high_signals.append((family, delta))
        blockers = input_blockers[row_id]
        finding["reasons"].extend(item["message"] for item in blockers)
        finding["flags"].extend(item["code"] for item in blockers)
        labels = {"peer": "本批有效报价", "history": "企业历史采购价", "supplier_history": "同供应商历史报价", "market": "有效市场参考价"}
        for family, delta in low_signals + high_signals:
            finding["reasons"].append(f"{'低于' if delta < 0 else '高于'}{labels[family]}中位数 {abs(delta):.1%}")
        if blockers:
            classification = "insufficient_data"
        elif low_signals and high_signals:
            classification = "insufficient_data"
            new_issue = make_issue(quote, "conflicting_reference_signals", "references", "不同价格参考给出相反偏离信号，需核实参考的适用性")
            issues.append(new_issue)
            finding["flags"].append(new_issue["code"])
            finding["reasons"].append(new_issue["message"])
        elif low_signals:
            if (row_id, "low_price") in explanations:
                classification = "low_explained"
                finding["reasons"].append("人工低价解释：" + explanations[(row_id, "low_price")]["reason"])
            else:
                classification = "abnormally_low"
                for family, delta in low_signals:
                    code = f"unusually_low_vs_{family}"
                    finding["flags"].append(code)
                    issues.append(make_issue(quote, code, "price", f"报价低于{labels[family]}中位数 {abs(delta):.1%}",
                                             question="请确认低价原因、报价有效性、是否漏报费用及规格配置，并提供书面依据"))
        elif high_signals:
            if (row_id, "premium") in explanations:
                classification = "high_explained"
                finding["reasons"].append("人工配置/服务溢价解释：" + explanations[(row_id, "premium")]["reason"])
            else:
                classification = "insufficient_data"
                finding["flags"].append("unexplained_premium")
                issues.append(make_issue(quote, "unexplained_premium", "price", "报价明显偏高，配置或服务溢价尚无经复核的证据"))
        elif all(finding[f"{family}_median"] is None for family in references):
            classification = "insufficient_data"
            finding["flags"].append("no_valid_reference")
            issues.append(make_issue(quote, "no_valid_reference", "references", "有效同口径报价或外部价格证据不足"))
        else:
            classification = "normal"
            finding["reasons"].append("未发现达到当前规则阈值的价格偏离")
        finding["classification"] = classification
        finding["classification_zh"] = CLASSIFICATION_ZH[classification]
        finding["status"] = "review_required" if classification in {"insufficient_data", "abnormally_low"} else ("within_reference_range" if classification == "normal" else "review_recommended")
        finding["flags"] = list(dict.fromkeys(finding["flags"]))
        findings.append(finding)
    finding_lookup = {item["quote_id"]: item for item in findings}

    rankings, item_results = [], []
    for item_id, group in groups.items():
        computable = [q for q in group if q["normalized_total_excl_tax"] is not None and q["normalized_total_excl_tax"] > 0
                      and q["lead_time_days"] is not None and q["payment_days"] is not None]
        ranked = score_candidates(computable, weights) if item_id not in incomparable_items else []
        if ranked and len(ranked) > 1 and ranked[1]["rank"] == 1:
            quote = next(q for q in group if q["quote_id"] == ranked[0]["quote_id"])
            issues.append(make_issue(quote, "tied_top_score", "score", "第一名并列，需人工选择或补充评分依据"))
        candidates = [r["supplier"] for r in ranked if r["rank"] == 1]
        if not candidates:
            candidates = list(dict.fromkeys(q["supplier"] for q in group))
        item_results.append({"item_id": item_id, "status": "pending", "candidate_suppliers": candidates,
                             "recommended_supplier": None})
        rankings.extend(ranked)
    blocking = [item for item in issues if item["severity"] == "blocker"]
    blocked = bool(blocking) or not rankings
    winners = []
    for item in item_results:
        item["status"] = "manual_review_required" if blocked else "conditional_recommendation"
        if not blocked and len(item["candidate_suppliers"]) == 1:
            item["recommended_supplier"] = item["candidate_suppliers"][0]
            winners.append(item["recommended_supplier"])
    for row in rankings:
        row["classification"] = finding_lookup[row["quote_id"]]["classification"]
        row["blockers"] = list(dict.fromkeys(item["code"] for item in blocking if item["quote_id"] == row["quote_id"]))
        row["eligible_for_recommendation"] = not blocked
    candidates = list(dict.fromkeys(supplier for item in item_results for supplier in item["candidate_suppliers"]))
    recommendation = winners[0] if winners and len(set(winners)) == 1 and not blocked else None
    decision = {
        "status": "manual_review_required" if blocked else "conditional_recommendation",
        "recommended_supplier": recommendation,
        "candidate_supplier": candidates[0] if len(candidates) == 1 else None,
        "candidate_suppliers": candidates,
        "blocking_flags": list(dict.fromkeys(item["code"] for item in blocking)),
        "reason": ("待人工复核：当前存在未闭环的报价、价格合理性或可比性风险。补充证据并重新计算后再提交人工审批。"
                   if blocked else "形成供人工审批的条件性采购建议；不同物料的建议见逐项结果，最终定标由人工完成。"),
    }
    evidence, input_files = [], {}
    for role, records in (("quotes", normalized), ("reference", reference_quotes)):
        for quote in records:
            source = quote["source"]
            input_files[_digest(source)] = source
            for field, proof in quote["evidence"].items():
                evidence.append({**proof, "quote_id": quote["quote_id"], "supplier": quote["supplier"], "field": field, "record_role": role})
    result = {
        "schema_version": "1.0", "run_id": _digest({"input": input_digest, "review": review})[:24],
        "input_digest": input_digest, "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": analysis_date.isoformat(), "weights": weights, "policy": policy,
        "input_files": list(input_files.values()), "quotes": normalized, "rankings": rankings,
        "item_results": item_results, "findings": findings, "issues": issues, "evidence": evidence,
        "reference_exclusions": exclusions,
        "reference_records": reference_quotes,
        "audit_log": audit, "procurement_decision": decision,
        "recommended_supplier": decision["recommended_supplier"],
        "candidate_supplier": decision["candidate_supplier"],
        "price_reasonableness": {"findings": findings, "decision_boundary": "价格合理性证据服务于人工审批。"},
        "assumptions": [
            "按物料逐项比较，货品总价不含另列附加费；每项附加费用按该报价行一次计入。",
            "评分基于未税总成本；含税现金支出单列展示，不推定企业可抵扣税额。",
            "原始报价的完整范围声明须由采购员核验；语义技术等效判断由人工完成。",
            "未单列的包装、调试、工装等费用以明确的完整报价范围声明为依据。",
            "历史及市场参考由用户提供；程序核对口径和时效，不自动采集或认证市场价格。",
            "人工复核记录采用本地人员自报身份，正式审批仍依企业授权制度执行。",
            "本版本按验收/到货/收票起点一致的标准账期评分；分阶段付款须人工确认。",
        ],
        "advice_zh": "",
    }
    return json_safe(result)
