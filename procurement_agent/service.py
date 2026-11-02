"""The shared application boundary used by both CLI and local review interface."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .engine import compare_records
from .ingest import load_records


def run_comparison(quote_paths: Iterable[str | Path], *,
                   history_paths: Iterable[str | Path] = (),
                   market_paths: Iterable[str | Path] = (),
                   weights: dict | None = None, policy: dict | None = None,
                   review: dict | None = None, as_of: str | None = None) -> dict:
    def load(paths: Iterable[str | Path], kind: str) -> list[dict]:
        if isinstance(paths, (str, Path)):
            paths = [paths]
        result = []
        for path in paths:
            result.extend(load_records(Path(path), kind=kind))
        return result

    result = compare_records(load(quote_paths, "quotes"),
                             history=load(history_paths, "history"),
                             market=load(market_paths, "market"),
                             weights=weights, policy=policy, review=review, as_of=as_of)
    from .reports import build_advice
    result["advice_zh"] = build_advice(result)
    return result
