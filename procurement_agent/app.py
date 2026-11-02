"""Local Streamlit quotation review UI over the shared service.

Run from the repository root with:
    python -m streamlit run procurement_agent/app.py --server.address 127.0.0.1

Each browser session owns a temporary workspace. Uploads are immutable copies;
review runs reuse those exact paths and never replace the original evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4
from zipfile import BadZipFile

import streamlit as st

# Streamlit executes a file rather than a package module. Resolve only our own
# repository root; never derive import paths from a browser-supplied filename.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from procurement_agent.reports import (  # noqa: E402
    CLASSIFICATION_NAMES,
    build_advice,
    decision_rows,
    report_tables,
    write_excel,
)
from procurement_agent.scoring import DEFAULT_WEIGHTS  # noqa: E402

DEMO_DIR = ROOT / "samples" / "v1"
SESSION_KEY = "procurement_review_session"
ALLOWED_SUFFIXES = {".xlsx", ".csv", ".json"}

LIGHT_STYLE = """
<style>
:root { color-scheme: light; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background: #f7f9fc; color: #192b3a;
}
[data-testid="stSidebar"] { background: #eef2f7; color: #192b3a; }
.stApp { font-family: "Microsoft YaHei", sans-serif; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1480px; }
[data-testid="stMetric"] { background: #ffffff; padding: 1rem; border-radius: 8px; }
</style>
"""


@dataclass(frozen=True)
class Upload:
    name: str
    data: bytes


@dataclass
class ReviewSession:
    temporary: TemporaryDirectory
    root: Path
    quote_paths: list[Path]
    history_paths: list[Path]
    market_paths: list[Path]
    weights: dict[str, float]
    as_of: str
    signature: str
    demo: bool = False
    result: dict[str, Any] | None = None
    downloads: dict[str, bytes] = field(default_factory=dict)
    export_error: str | None = None

    def close(self) -> None:
        """Release only this session's own temporary upload/export copies."""
        self.temporary.cleanup()


def _safe_name(name: str) -> str:
    # Both slash styles must be handled even when the host OS differs from the
    # uploading browser. Prefix avoids reserved Windows basenames such as CON.
    basename = name.replace("\\", "/").rsplit("/", 1)[-1]
    suffix = Path(basename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("支持的文件类型为 XLSX、CSV、JSON。")
    stem = Path(basename).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")[:100]
    return f"input_{stem or 'upload'}{suffix}"


def _save_uploads(root: Path, kind: str, uploads: list[Upload]) -> list[Path]:
    paths = []
    for index, upload in enumerate(uploads):
        if not upload.data:
            raise ValueError("上传文件为空，请检查文件内容。")
        name = _safe_name(upload.name)
        folder = root / "inputs" / kind / f"{index:03d}"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        with target.open("xb") as stream:
            stream.write(upload.data)
        paths.append(target)
    return paths


def create_session(
    quotes: list[Upload],
    history: list[Upload],
    market: list[Upload],
    *,
    weights: dict[str, float],
    as_of: str,
    signature: str = "",
    demo: bool = False,
) -> ReviewSession:
    """Create a private, date-scoped upload workspace without running a comparison."""
    if not quotes:
        raise ValueError("请至少上传一份包含供应商报价的文件。")
    temporary = TemporaryDirectory(prefix="procurement-review-")
    root = Path(temporary.name) / date.today().isoformat()
    try:
        return ReviewSession(
            temporary=temporary,
            root=root,
            quote_paths=_save_uploads(root, "quotes", quotes),
            history_paths=_save_uploads(root, "history", history),
            market_paths=_save_uploads(root, "market", market),
            weights=dict(weights),
            as_of=as_of,
            signature=signature,
            demo=demo,
        )
    except Exception:
        temporary.cleanup()
        raise


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def run_session(session: ReviewSession, review: dict[str, Any] | None = None) -> None:
    """Recompute using immutable source files and atomically replace displayed results."""
    from procurement_agent.engine import create_review_template
    from procurement_agent.service import run_comparison

    result = run_comparison(
        session.quote_paths,
        history_paths=session.history_paths,
        market_paths=session.market_paths,
        weights=session.weights,
        review=review,
        as_of=session.as_of,
    )
    template = create_review_template(result)
    if review is not None:
        # Each recomputation replays a complete review against immutable inputs.
        # Seed the next editable file with the accepted changes so a second
        # review round does not silently drop earlier corrections/explanations.
        template["corrections"] = review.get("corrections", [])
        template["explanations"] = review.get("explanations", [])
    downloads = {
        "json": _json_bytes(result),
        "advice": build_advice(result).encode("utf-8"),
        "review": _json_bytes(template),
    }
    output = session.root / "output" / uuid4().hex
    output.mkdir(parents=True, exist_ok=True)
    export_error = None
    try:
        workbook = output / "采购报价审核.xlsx"
        write_excel(result, workbook)
        downloads["excel"] = workbook.read_bytes()
    except (ValueError, OSError) as error:
        # JSON remains the complete evidence source when Excel cannot represent
        # a long/control-character-containing original value.
        export_error = str(error)
    session.result = result
    session.downloads = downloads
    session.export_error = export_error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"复核 JSON 含有重复字段：{key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"复核 JSON 含有无效数值：{value}")


def parse_review(data: bytes) -> dict[str, Any]:
    value = json.loads(
        data.decode("utf-8-sig"), object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )
    if not isinstance(value, dict):
        raise TypeError("复核 JSON 顶层必须是对象。")
    return value


def _uploads(files: Any) -> list[Upload]:
    return [Upload(file.name, file.getvalue()) for file in (files or [])]


def input_signature(
    quotes: list[Upload], history: list[Upload], market: list[Upload],
    weights: dict[str, float], as_of: str,
) -> str:
    # This is only a stale-display indicator. The engine owns the authoritative
    # input_digest and all review-binding validation.
    groups = [
        [(upload.name, hashlib.sha256(upload.data).hexdigest()) for upload in group]
        for group in (quotes, history, market)
    ]
    return hashlib.sha256(_json_bytes([groups, weights, as_of])).hexdigest()


def demo_uploads() -> tuple[list[Upload], list[Upload], list[Upload]]:
    groups = []
    for name in ("quotes.json", "history.json", "market.json"):
        path = DEMO_DIR / name
        groups.append([Upload(name, path.read_bytes())])
    return groups[0], groups[1], groups[2]


def _display_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _show_table(headers: list[str], rows: list[list[Any]]) -> None:
    if not rows:
        st.caption("本次无记录。")
        return
    records = [
        {header: _display_value(value) for header, value in zip(headers, row, strict=True)}
        for row in rows
    ]
    # Evidence/configuration columns can legitimately mix numbers and text.
    # Normalize only mixed display columns; ordinary numeric columns retain
    # numeric sorting and the JSON/Excel projections keep the original types.
    for header in headers:
        values = [record[header] for record in records if record[header] is not None]
        types = {"number" if type(value) in (int, float) else type(value) for value in values}
        if len(types) > 1:
            for record in records:
                if record[header] is not None:
                    record[header] = str(record[header])
    # Streamlit's dataframe renders string values as data, not HTML/Markdown.
    st.dataframe(
        records,
        hide_index=True, width="stretch",
    )


def _show_error(message: str, error: Exception) -> None:
    st.error(message)
    # Exceptions can contain input text. Plain text prevents Markdown images or
    # HTML in uploaded values from producing browser requests or active content.
    st.text(str(error))


def _show_result(session: ReviewSession) -> None:
    result = session.result
    if result is None:
        return
    if session.demo:
        st.info("当前显示合成演示数据。")
    decision = result.get("procurement_decision") or {}
    if decision.get("status") == "conditional_recommendation" and not decision.get("blocking_flags"):
        st.success("已形成有条件推荐，请按企业授权流程审核。")
    else:
        st.warning("待人工复核：请先处理阻断项，再提交复核文件重新计算。")
    metrics = st.columns(3)
    metrics[0].metric("报价记录", len(result.get("quotes", [])))
    metrics[1].metric("阻断问题", sum(issue.get("severity") == "blocker" for issue in result.get("issues", [])))
    metrics[2].metric("复核记录", len(result.get("audit_log", [])))
    st.subheader("候选与决策")
    decisions = decision_rows(result)
    _show_table(list(decisions[0]), [list(row.values()) for row in decisions])
    if decision.get("reason"):
        st.text(str(decision["reason"]))
    if decision.get("blocking_flags"):
        st.text("阻断标记：" + json.dumps(decision["blocking_flags"], ensure_ascii=False))

    tables = report_tables(result)
    tabs = st.tabs(["评分与报价", "风险与确认", "价格参考", "字段证据", "人工复核", "采购建议"])
    with tabs[0]:
        _show_table(*tables["供应商评分"])
        with st.expander("报价明细与原始业务字段"):
            _show_table(*tables["报价明细"])
        with st.expander("逐项计算步骤"):
            _show_table(*tables["计算明细"])
        st.caption("价格分类：" + " / ".join(CLASSIFICATION_NAMES.values()))
    with tabs[1]:
        _show_table(*tables["风险与确认"])
    with tabs[2]:
        _show_table(*tables["价格参考"])
        with st.expander("历史与市场参考明细"):
            _show_table(*tables["参考明细"])
        with st.expander("被排除的参考记录"):
            _show_table(*tables["参考排除"])
    with tabs[3]:
        _show_table(*tables["原始证据"])
        with st.expander("原始值、复核后有效值与标准化结果"):
            _show_table(*tables["字段对照"])
        with st.expander("来源文件与规则配置"):
            _show_table(*tables["输入文件"])
            _show_table(*tables["规则配置"])
    with tabs[4]:
        _show_table(*tables["人工复核"])
    with tabs[5]:
        st.code(build_advice(result), language=None, wrap_lines=True)

    st.subheader("下载本次结果")
    stamp = session.as_of
    downloads = st.columns(4)
    with downloads[0]:
        st.download_button("完整 JSON", session.downloads["json"], f"采购审核_{stamp}.json",
                           mime="application/json", on_click="ignore", key="download_json")
    with downloads[1]:
        st.download_button(
            "Excel 报告", session.downloads.get("excel", b""), f"采购审核_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled="excel" not in session.downloads, on_click="ignore", key="download_excel",
        )
    with downloads[2]:
        st.download_button("中文建议", session.downloads["advice"], f"采购建议_{stamp}.txt",
                           mime="text/plain; charset=utf-8", on_click="ignore", key="download_advice")
    with downloads[3]:
        st.download_button("复核模板", session.downloads["review"], f"人工复核_{stamp}.json",
                           mime="application/json", on_click="ignore", key="download_review")
    if session.export_error:
        st.warning("Excel 导出未完成，完整 JSON 与中文建议仍可下载。")
        st.text(session.export_error)
    st.caption("本次运行标识")
    st.text(str(result.get("run_id", "")))


def main() -> None:
    st.set_page_config(page_title="采购报价审核", page_icon="📋", layout="wide")
    st.markdown(LIGHT_STYLE, unsafe_allow_html=True)  # constant CSS only
    st.title("采购报价审核")
    st.caption("上传报价 → 查看差异与证据 → 人工复核 → 重新计算")

    with st.sidebar:
        st.header("比较设置")
        price_weight = st.slider("价格权重（%）", 0, 100, round(DEFAULT_WEIGHTS["price"] * 100), key="price_weight")
        lead_weight = st.slider("交期权重（%）", 0, 100, round(DEFAULT_WEIGHTS["lead_time"] * 100), key="lead_weight")
        payment_weight = st.slider("付款权重（%）", 0, 100, round(DEFAULT_WEIGHTS["payment_terms"] * 100), key="payment_weight")
        total = price_weight + lead_weight + payment_weight
        st.caption(f"权重合计：{total}%")
        valid_weights = total == 100
        if not valid_weights:
            st.warning("请将三项权重合计设为 100%。")
        as_of = st.date_input("分析日期", value=date.today(), key="as_of").isoformat()
        st.caption("文件在本机当前会话中处理，参考价格由使用者提供。")
        clear = st.button("清空本次会话", key="clear_session")
    if clear:
        previous = st.session_state.pop(SESSION_KEY, None)
        if previous is not None:
            previous.close()

    st.subheader("1. 上传比较资料")
    quote_files = st.file_uploader("供应商报价（可多选）", type=["xlsx", "csv", "json"],
                                  accept_multiple_files=True, key="quote_uploads")
    with st.expander("历史采购、市场参考与已有复核文件（可选）"):
        history_files = st.file_uploader("历史采购 / 同供应商历史报价", type=["xlsx", "csv", "json"],
                                        accept_multiple_files=True, key="history_uploads")
        market_files = st.file_uploader("市场参考", type=["xlsx", "csv", "json"],
                                       accept_multiple_files=True, key="market_uploads")
        initial_review = st.file_uploader("已有复核 JSON", type=["json"], key="initial_review")

    quotes, history, market = _uploads(quote_files), _uploads(history_files), _uploads(market_files)
    weights = {"price": price_weight / 100, "lead_time": lead_weight / 100,
               "payment_terms": payment_weight / 100}
    signature = input_signature(quotes, history, market, weights, as_of)
    actions = st.columns([1, 1, 3])
    compare_clicked = actions[0].button("开始比较", type="primary", key="compare",
                                       disabled=not quotes or not valid_weights)
    demo_clicked = actions[1].button("加载合成演示", key="demo", disabled=not valid_weights)
    if compare_clicked or demo_clicked:
        previous = st.session_state.pop(SESSION_KEY, None)
        if previous is not None:
            previous.close()
        session = None
        try:
            source_groups = demo_uploads() if demo_clicked else (quotes, history, market)
            review = parse_review(initial_review.getvalue()) if initial_review and not demo_clicked else None
            session = create_session(*source_groups, weights=weights, as_of=as_of,
                                     signature=signature, demo=demo_clicked)
            with st.spinner("正在比较报价并生成报告…"):
                run_session(session, review=review)
            st.session_state[SESSION_KEY] = session
        except (ValueError, TypeError, OSError, ImportError, KeyError, BadZipFile) as error:
            if session is not None:
                session.close()
            _show_error("本次比较未完成，请根据以下错误修正输入后重新比较。", error)

    session = st.session_state.get(SESSION_KEY)
    if session is None:
        st.info("上传报价后开始比较，或加载合成演示查看完整流程。")
        return
    if session.signature != signature:
        st.warning("输入文件、权重或分析日期已更改，请重新比较后查看本次结果。")
        return

    st.subheader("2. 人工复核并重新计算")
    st.caption("下载复核模板，填写复核人、时间、修改原因和证据引用，再上传。后续模板保留已提交的修改和解释；每次计算使用完整复核文件。")
    edited_review = st.file_uploader("上传修改后的复核 JSON", type=["json"], key="edited_review")
    apply_clicked = st.button("应用复核并重新计算", key="apply_review", disabled=edited_review is None)
    if apply_clicked:
        try:
            review = parse_review(edited_review.getvalue())
            with st.spinner("正在校验复核文件并重新计算…"):
                run_session(session, review)
            st.success("复核已应用，以下为重新计算后的结果。")
        except (ValueError, TypeError, OSError, ImportError, KeyError, BadZipFile) as error:
            _show_error("复核未应用，以下保留上一次成功计算的结果。", error)
    _show_result(session)


if __name__ == "__main__":
    main()
