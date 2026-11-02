"""Command-line entry point for the enterprise procurement MVP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# rfqdiff is deliberately vendored under rfqdiff-upstream to preserve its source
# boundary and license. Add it only for this process, not globally.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "rfqdiff-upstream"))

from rfqdiff import (  # noqa: E402
    build_result,
    load_quotes,
    load_weights,
    score_quotes,
    validate_currencies,
    write_report,
)

from .io import load_history  # noqa: E402
from .reasonableness import analyze_price_reasonableness  # noqa: E402


def _load_all(paths: list[str]) -> list[dict]:
    quotes: list[dict] = []
    for raw_path in paths:
        quotes.extend(load_quotes(Path(raw_path)))
    if len(quotes) < 2:
        raise ValueError("至少需要两家供应商报价才能进行比较")
    return quotes


def compare(args: argparse.Namespace) -> int:
    quotes = _load_all(args.quotes)
    currency = validate_currencies(quotes)
    weights = load_weights(Path(args.weights)) if args.weights else None
    scored = score_quotes(quotes, weights)
    result = build_result(scored, currency, weights)
    history = load_history(Path(args.history)) if args.history else []
    reasonableness_quotes = [
        {
            "supplier": quote["name"],
            "price": quote["price"],
            "missing_fields": quote.get("missing_fields", []),
            "comparable": quote.get("comparable", True),
        }
        for quote in quotes
    ]
    result["price_reasonableness"] = analyze_price_reasonableness(
        reasonableness_quotes,
        historical_prices=history,
    )
    findings = {item["supplier"]: item for item in result["price_reasonableness"]["findings"]}
    winner = result["recommended_supplier"]
    winner_finding = findings.get(winner, {})
    if winner_finding.get("status") in {"review_required", "insufficient_data"}:
        result["procurement_decision"] = {
            "status": "manual_review_required",
            "recommended_supplier": None,
            "candidate_supplier": winner,
            "reason": "评分第一名存在价格合理性或数据完整性风险，不能自动形成定标建议。",
            "blocking_flags": winner_finding.get("flags", []),
        }
    else:
        result["procurement_decision"] = {
            "status": "review_recommended",
            "recommended_supplier": winner,
            "candidate_supplier": winner,
            "reason": "评分第一名未触发当前价格合理性阈值，但仍需人工确认技术和商务条件。",
            "blocking_flags": [],
        }
    output = Path(args.output) if args.output else None
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.report:
        write_report(result, Path(args.report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="procurement-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare_parser = subparsers.add_parser("compare", help="比较多家供应商报价并分析价格偏离")
    compare_parser.add_argument("--quotes", nargs="+", required=True, help="CSV/JSON/XLSX 报价文件")
    compare_parser.add_argument("--history", help="历史价格 CSV/JSON/XLSX，可选")
    compare_parser.add_argument("--weights", help="rfqdiff 权重 JSON，可选")
    compare_parser.add_argument("--output", help="输出综合 JSON，可选")
    compare_parser.add_argument("--report", help="输出评分 Excel，可选")
    compare_parser.set_defaults(func=compare)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return args.func(args)
    except (ValueError, OSError, KeyError) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
