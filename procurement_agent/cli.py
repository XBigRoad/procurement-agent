"""Command-line interface using the shared evidence-based procurement service."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from zipfile import BadZipFile


def _object_file(raw_path: str | None, label: str) -> dict | None:
    if not raw_path:
        return None
    value = json.loads(Path(raw_path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{label}须为JSON对象")
    return value


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def compare(args: argparse.Namespace) -> int:
    from .engine import create_review_template
    from .reports import write_excel
    from .service import run_comparison

    inputs = args.quotes + (args.history or []) + (args.market or [])
    inputs += [p for p in (args.review, args.weights, args.policy) if p]
    input_paths = {Path(path).resolve() for path in inputs}
    outputs = [p for p in (args.output, args.report, args.advice, args.review_template) if p]
    if any(Path(path).resolve() in input_paths for path in outputs):
        raise ValueError("输出路径须与原始输入文件不同，以保留原始证据")
    if len({Path(path).resolve() for path in outputs}) != len(outputs):
        raise ValueError("JSON、Excel、建议和复核模板须使用不同输出路径")
    result = run_comparison(
        args.quotes, history_paths=args.history or (), market_paths=args.market or (),
        weights=_object_file(args.weights, "权重"), policy=_object_file(args.policy, "规则"),
        review=_object_file(args.review, "人工复核"), as_of=args.as_of,
    )
    serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        _write_text(Path(args.output), serialized)
    else:
        print(serialized)
    if args.report:
        write_excel(result, Path(args.report))
    if args.advice:
        _write_text(Path(args.advice), result["advice_zh"])
    if args.review_template:
        _write_text(Path(args.review_template), json.dumps(create_review_template(result), ensure_ascii=False, indent=2))
    if args.output:
        print(f"已生成结果：{Path(args.output).resolve()}")
        print(f"决策状态：{result['procurement_decision']['status']}")
    return 0


def serve(args: argparse.Namespace) -> int:
    try:
        import streamlit  # noqa: F401
    except ImportError as exc:
        raise ValueError("网页依赖未安装，请运行 scripts/install.ps1") from exc
    return subprocess.call([
        sys.executable, "-m", "streamlit", "run", str(Path(__file__).with_name("app.py")),
        "--server.address", "127.0.0.1", "--server.port", str(args.port),
        "--server.headless", "true", "--browser.gatherUsageStats", "false",
    ])


def make_templates(args: argparse.Namespace) -> int:
    from .templates import write_templates
    output = Path(args.directory) if args.directory else Path("output") / date.today().isoformat() / "templates"
    write_templates(output)
    print(f"已生成输入模板：{output.resolve()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="procurement-agent", description="企业采购报价审核与人工复核建议")
    subparsers = parser.add_subparsers(dest="command", required=True)
    comparison = subparsers.add_parser("compare", help="读取多家报价、审查风险并生成比价报告")
    comparison.add_argument("--quotes", nargs="+", required=True, help="CSV/JSON/XLSX 报价文件")
    comparison.add_argument("--history", nargs="+", help="带物料、规格、口径和日期的历史采购/报价文件")
    comparison.add_argument("--market", nargs="+", help="用户提供的带日期市场参考文件")
    comparison.add_argument("--weights", help="权重JSON")
    comparison.add_argument("--policy", help="阈值和参考时效JSON")
    comparison.add_argument("--review", help="已填写的人工复核JSON")
    comparison.add_argument("--as-of", help="分析日期 YYYY-MM-DD；默认为本机当天")
    comparison.add_argument("--output", help="综合JSON；省略时打印至终端")
    comparison.add_argument("--report", help="Excel比价报告 .xlsx")
    comparison.add_argument("--advice", help="中文采购建议 .md")
    comparison.add_argument("--review-template", help="导出与本批输入绑定的人工复核JSON模板")
    comparison.set_defaults(func=compare)
    server = subparsers.add_parser("serve", help="启动本机采购审核网页")
    server.add_argument("--port", type=int, default=8511)
    server.set_defaults(func=serve)
    templates = subparsers.add_parser("templates", help="生成标准Excel/JSON输入模板")
    templates.add_argument("--directory", help="模板目录，默认 output/当天日期/templates")
    templates.set_defaults(func=make_templates)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        if args.command == "serve" and not 1024 <= args.port <= 65535:
            raise ValueError("本机端口须在1024至65535之间")
        return args.func(args)
    except (ValueError, OSError, KeyError, BadZipFile) as error:
        print(f"错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
