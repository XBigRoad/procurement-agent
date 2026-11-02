# Design

Keep the existing procurement business guidance and MIT upstream reference. Evolve
the enterprise pipeline into one authoritative calculation path shared by CLI and UI.

1. `ingest.py`: table recognition, aliases, immutable field evidence and source hashes.
2. `engine.py`: strict numeric validation, normalization, comparison groups, matched
   benchmarks, deterministic scoring, human decision gate and review audit.
3. `service.py`: file orchestration, JSON serialization and shared public entry point.
4. `reports.py`: Excel and Chinese advice projections of the engine result.
5. `cli.py` and `app.py`: local interfaces; neither calculates or overrides decisions.

The inter-module contract is `docs/DATA_CONTRACT.md`. Decimal is used before monetary
values are serialized to finite JSON numbers. Original inputs are never overwritten.
Reviews bind to a deterministic digest covering input content, policy, weights and
as-of date. Named explanations require documentary references. This is an auditable
local review record, not authenticated approval or automatic technical certification.

All unresolved blocking input/comparability risks conservatively block the batch.
Valid rankings may still be shown as candidates. Separate procurement items never
share a price baseline or a global sum of incompatible currencies. Market/history
inputs are user-provided evidence, not automatically fetched market truth.

Local deployment uses an isolated `.venv`, localhost-only UI and date-scoped output.
Revert the eventual Git commit to roll back code; source business files stay intact.
