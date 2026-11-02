"""rfqdiff's transparent ratio scoring, with Decimal arithmetic and zero-day support.

Algorithm adapted from rfqdiff 7a99522 (MIT), retained under rfqdiff-upstream/.
The enterprise decision gate is intentionally outside the scoring function.
"""
from __future__ import annotations

from decimal import Decimal

from .normalization import as_number, decimal_value

DEFAULT_WEIGHTS = {"price": 0.5, "lead_time": 0.3, "payment_terms": 0.2}


def validate_weights(weights: dict | None) -> dict[str, float]:
    values = DEFAULT_WEIGHTS if weights is None else weights
    if not isinstance(values, dict) or set(values) != set(DEFAULT_WEIGHTS):
        raise ValueError("权重必须且仅包含 price、lead_time、payment_terms")
    parsed = {key: decimal_value(value) for key, value in values.items()}
    if any(value < 0 or value > 1 for value in parsed.values()):
        raise ValueError("各项权重须在0至1之间")
    if abs(sum(parsed.values()) - 1) > Decimal("0.000000001"):
        raise ValueError("权重合计必须等于1")
    return {key: float(value) for key, value in parsed.items()}


def score_candidates(quotes: list[dict], weights: dict[str, float]) -> list[dict]:
    if not quotes:
        return []
    prices = [decimal_value(q["normalized_total_excl_tax"]) for q in quotes]
    leads = [decimal_value(q["lead_time_days"]) for q in quotes]
    payments = [decimal_value(q["payment_days"]) for q in quotes]
    if any(p <= 0 for p in prices) or any(x < 0 for x in leads + payments):
        raise ValueError("评分需正数总价、非负交期和账期")
    min_price, min_lead, max_payment = min(prices), min(leads), max(payments)
    output = []
    for quote, price, lead, payment in zip(quotes, prices, leads, payments, strict=True):
        price_part = min_price / price * decimal_value(weights["price"]) * 100
        lead_ratio = Decimal(1) if lead == 0 else min_lead / lead
        lead_part = lead_ratio * decimal_value(weights["lead_time"]) * 100
        pay_ratio = payment / max_payment if max_payment else Decimal(1)
        pay_part = pay_ratio * decimal_value(weights["payment_terms"]) * 100
        output.append({
            "quote_id": quote["quote_id"], "supplier": quote["supplier"], "item_id": quote["item_id"],
            "score": as_number(price_part + lead_part + pay_part),
            "price_score": as_number(price_part), "lead_time_score": as_number(lead_part),
            "payment_terms_score": as_number(pay_part), "_exact_score": price_part + lead_part + pay_part,
            "normalized_total_excl_tax": quote["normalized_total_excl_tax"],
            "currency": quote["currency"], "lead_time_days": quote["lead_time_days"],
            "payment_days": quote["payment_days"],
        })
    output.sort(key=lambda q: (-q["_exact_score"], q["supplier"], q["quote_id"]))
    previous_score, previous_rank = None, 0
    for index, row in enumerate(output, 1):
        row["rank"] = previous_rank if row["_exact_score"] == previous_score else index
        previous_score, previous_rank = row.pop("_exact_score"), row["rank"]
    return output
