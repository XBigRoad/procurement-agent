import json
from datetime import date

from procurement_agent.cli import main
from procurement_agent.templates import demo_quotes


def test_cli_blocks_anomalous_winner(tmp_path, monkeypatch):
    quotes = tmp_path / "quotes.json"
    rows = demo_quotes(date(2026, 11, 2))[:3]
    rows[2]["unit_price_excl_tax"] = 55
    quotes.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "procurement-agent",
            "compare",
            "--quotes",
            str(quotes),
            "--as-of",
            "2026-11-02",
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["recommended_supplier"] is None
    assert result["candidate_supplier"] == "模拟供应商C"
    assert result["procurement_decision"]["status"] == "manual_review_required"
    assert result["procurement_decision"]["recommended_supplier"] is None


def test_cli_all_outputs_and_review_replay(tmp_path, monkeypatch):
    quotes = tmp_path / "quotes.json"
    rows = demo_quotes(date(2026, 11, 2))[:3]
    rows[0]["freight"] = None
    quotes.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    result_path = tmp_path / "result.json"
    review_path = tmp_path / "review.json"
    args = ["procurement-agent", "compare", "--quotes", str(quotes), "--as-of", "2026-11-02",
            "--output", str(result_path), "--report", str(tmp_path / "report.xlsx"),
            "--advice", str(tmp_path / "advice.md"), "--review-template", str(review_path)]
    monkeypatch.setattr("sys.argv", args)
    assert main() == 0
    result = json.loads(result_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review.update(reviewer="测试审核人", corrections=[{"quote_id": result["quotes"][0]["quote_id"],
                  "field": "freight", "value": 0, "reason": "运费已含", "evidence": "模拟确认函"}])
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("sys.argv", args[:-2] + ["--review", str(review_path)])
    assert main() == 0
    after = json.loads(result_path.read_text(encoding="utf-8"))
    assert after["recommended_supplier"] == "模拟供应商A"
    assert (tmp_path / "report.xlsx").is_file()
    assert "采购" in (tmp_path / "advice.md").read_text(encoding="utf-8")


def test_cli_protects_original_input(tmp_path, monkeypatch, capsys):
    path = tmp_path / "source.json"
    original = json.dumps(demo_quotes(date(2026, 11, 2)))
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["procurement-agent", "compare", "--quotes", str(path), "--output", str(path)])
    assert main() == 2
    assert path.read_text(encoding="utf-8") == original
    assert "原始" in capsys.readouterr().err


def test_cli_templates(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["procurement-agent", "templates", "--directory", str(tmp_path)])
    assert main() == 0
    assert (tmp_path / "quotes.xlsx").is_file()
    assert (tmp_path / "history.json").is_file()
