# Backend conventions

Read [procurement.md](procurement.md) before changing ingestion, normalization,
references, scoring, review replay, reports or interfaces. The public shared
boundary is `procurement_agent.service.run_comparison`; the engine owns decisions.

## Pre-development checklist

1. Read the active task PRD, design and implementation plan.
2. Read `docs/DATA_CONTRACT.md` for field and result contracts.
3. Search existing readers, validators and report projections before extending.
4. Preserve original evidence; keep references scoped and review files input-bound.

## Quality check

Run `python -m pytest tests -q` and `python -m ruff check procurement_agent tests`.
Run retained upstream tests with `PYTHONPATH=rfqdiff-upstream`. Exercise CLI report
export and the local UI for interface changes. Record exact commands and outcomes.
