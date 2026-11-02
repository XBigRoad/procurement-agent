import json
from pathlib import Path

from procurement_agent.cli import main


def test_cli_blocks_anomalous_winner(tmp_path, monkeypatch):
    quotes = tmp_path / "quotes.csv"
    quotes.write_text(
        "name,currency,price,lead_time_weeks,payment_days\n"
        "A,CNY,100,8,30\nB,CNY,102,8,30\nC,CNY,55,8,30\n",
        encoding="utf-8",
    )
    history = tmp_path / "history.csv"
    history.write_text("price\n98\n100\n102\n", encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "procurement-agent",
            "compare",
            "--quotes",
            str(quotes),
            "--history",
            str(history),
            "--output",
            str(output),
        ],
    )
    assert main() == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["recommended_supplier"] == "C"
    assert result["procurement_decision"]["status"] == "manual_review_required"
    assert result["procurement_decision"]["recommended_supplier"] is None
