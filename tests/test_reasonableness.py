from procurement_agent import analyze_price_reasonableness


def test_flags_unusually_low_quote_and_history_deviation():
    result = analyze_price_reasonableness(
        [
            {"supplier": "A", "price": 100},
            {"supplier": "B", "price": 105},
            {"supplier": "C", "price": 55, "missing_fields": ["运费"]},
        ],
        historical_prices=[98, 102, 100],
    )
    finding = next(x for x in result["findings"] if x["supplier"] == "C")
    assert finding["status"] == "review_required"
    assert "unusually_low_vs_peers" in finding["flags"]
    assert "missing_fields" in finding["flags"]


def test_normal_quote_is_not_flagged():
    result = analyze_price_reasonableness(
        [{"supplier": "A", "price": 100}, {"supplier": "B", "price": 102}],
        historical_prices=[99, 101],
    )
    assert all(x["status"] == "within_reference_range" for x in result["findings"])
