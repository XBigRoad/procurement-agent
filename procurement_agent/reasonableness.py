"""Deterministic price-reasonableness checks for procurement quotations.

This module deliberately does not make an award decision. It produces evidence
and flags for human review; the LLM/Skill layer may explain them without
changing the underlying calculations.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any, Iterable


def _numbers(values: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            out.append(number)
    return out


def analyze_price_reasonableness(
    quotes: list[dict[str, Any]],
    *,
    historical_prices: Iterable[Any] = (),
    peer_low_threshold: float = 0.20,
    peer_high_threshold: float = 0.20,
    history_threshold: float = 0.20,
) -> dict[str, Any]:
    """Return explainable price flags for comparable, normalized quotes.

    Each quote should contain ``supplier`` and numeric ``price``. Optional
    ``comparable`` and ``missing_fields`` values are propagated into flags.
    Thresholds express relative deviation from peer/history medians.
    """
    prices = _numbers(q.get("price") for q in quotes)
    history = _numbers(historical_prices)
    peer_median = median(prices) if prices else None
    history_median = median(history) if history else None
    findings: list[dict[str, Any]] = []

    for quote in quotes:
        supplier = str(quote.get("supplier") or quote.get("name") or "未命名供应商")
        try:
            if isinstance(quote["price"], bool):
                raise ValueError("boolean price")
            price = float(quote["price"])
            if not math.isfinite(price) or price <= 0:
                raise ValueError("invalid price")
        except (KeyError, TypeError, ValueError):
            findings.append({"supplier": supplier, "status": "insufficient_data", "reasons": ["缺少可计算报价"]})
            continue
        reasons: list[str] = []
        flags: list[str] = []
        if quote.get("comparable") is False:
            flags.append("not_comparable")
            reasons.append("报价尚未确认与其他供应商技术规格等效")
        missing = quote.get("missing_fields") or []
        if missing:
            flags.append("missing_fields")
            reasons.append("缺少字段：" + "、".join(map(str, missing)))
        peer_delta = None
        history_delta = None
        if peer_median is not None and peer_median:
            peer_delta = (price - peer_median) / peer_median
            if peer_delta <= -peer_low_threshold:
                flags.append("unusually_low_vs_peers")
                reasons.append(f"低于本批可计算报价中位数 {abs(peer_delta):.1%}")
            elif peer_delta >= peer_high_threshold:
                flags.append("unusually_high_vs_peers")
                reasons.append(f"高于本批可计算报价中位数 {peer_delta:.1%}")
        if history_median is not None and history_median:
            history_delta = (price - history_median) / history_median
            if abs(history_delta) >= history_threshold:
                flags.append("deviates_from_history")
                direction = "高于" if history_delta > 0 else "低于"
                reasons.append(f"{direction}历史价格中位数 {abs(history_delta):.1%}")
        if not reasons:
            status = "within_reference_range"
            reasons.append("未发现超过当前阈值的价格偏离")
        elif any(x in flags for x in ("not_comparable", "missing_fields", "unusually_low_vs_peers")) or (history_delta is not None and history_delta <= -history_threshold):
            status = "review_required"
        else:
            status = "review_recommended"
        findings.append({
            "supplier": supplier,
            "price": price,
            "status": status,
            "flags": flags,
            "reasons": reasons,
            "peer_median": peer_median,
            "peer_delta": peer_delta,
            "history_median": history_median,
            "history_delta": history_delta,
        })
    return {
        "reference": {"peer_median": peer_median, "history_median": history_median},
        "findings": findings,
        "decision_boundary": "仅提供价格合理性证据，不替代技术评审、供应商准入或最终定标。",
    }
