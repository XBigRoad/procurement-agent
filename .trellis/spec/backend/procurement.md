# Procurement calculation contract

The shared service owns computation. Monetary arithmetic uses finite Decimal values.
Missing costs remain unknown. All supplied fields retain original value and source
hash/cell/pointer. Compare only matching item contexts; validate historical scope,
currency, units, quantity and date before deriving references. Supplier is not a row id.
Human reviews bind to input/policy digests and preserve original values. Every
recommendation projection obeys the same decision gate. UI/report code projects
results without overriding business rules. Tests exercise risk cases and review replay.

## Scope and entry points

This contract applies to all CSV/XLSX/JSON ingestion, comparison, report and UI
changes. `service.run_comparison(quote_paths, *, history_paths=(), market_paths=(),
weights=None, policy=None, review=None, as_of=None)` is the shared boundary.
`engine.create_review_template(result)` creates an input-bound review document.
The complete field schema remains in `docs/DATA_CONTRACT.md`.

## Input and result contracts

Source records include immutable `_source` and `_evidence` metadata. A quote has
an identity derived from file hash and source position. `raw_fields` preserves the
initial business values; `effective_fields` holds reviewed values. Reviews require
`input_digest`, `reviewer`, timezone-aware `reviewed_at`, reasons and evidence.
The digest binds source content, positions, values, analysis date and rules;
incidental upload paths and filenames do not change it.

`procurement_decision.status` is `manual_review_required` or
`conditional_recommendation`. Blocked batches expose candidates and issues, and
all `recommended_supplier` projections are null. The interfaces use this decision.
No API key, remote model service or database is required for this local pipeline.

## Validation and error matrix

| Condition | Required behavior |
|---|---|
| Unknown cost, incomplete scope or incompatible specifications | Structured blocker and supplier question |
| Invalid input or review document | Actionable ValueError; CLI exit2 or UI error |
| Current quotation re-used as reference | Exclude by source hash/record identity; retain exclusion evidence |
| Incomplete historical scope | Exclude from baseline admission |
| Contradictory tax totals | `tax_total_conflict` blocker, checked at total precision |
| Same evidence uploaded into another session | Existing review digest remains valid |
| Changed source, rule, weight or analysis date | Previous review fails digest validation |
| Valid low-price explanation with other unresolved issues | Keep the unresolved blockers |

## Representative cases

Base case: three comparable, complete quotations produce weighted scores and
conditional advice. Valid review: a documented correction updates effective values,
recalculates the full result and adds before/after audit data. Invalid case: treating
the current low quote as independent history must leave the historical low-price
blocker in place.

```python
from procurement_agent.engine import create_review_template
from procurement_agent.service import run_comparison

result = run_comparison(quote_paths, as_of="2026-11-02")
review = create_review_template(result)
# The operator supplies reviewer, time, corrections and documentary references.
reviewed_result = run_comparison(quote_paths, as_of="2026-11-02", review=review)
```

## Regression assertions

`test_current_quote_cannot_contaminate_history` preserves the independent baseline.
`test_incomplete_reference_cannot_clear_historical_low_block` excludes partial scope.
`test_large_quantity_does_not_hide_inconsistent_totals` checks total-level conflicts.
`test_review_reusable_after_upload_copy_and_across_sessions` binds reviews to
substantive evidence. Report/UI tests assert null recommendation on blocked runs,
original evidence retention and consistent default scoring weights.

## Correct implementation of previous failure modes

The earlier total-price check divided a large contradiction by quantity before
applying tolerance. Check explicit net/gross totals directly at the configured
0.02 currency-unit tolerance, then derive unit amounts. The earlier review digest
included temporary upload directories. Bind content and rules instead so relocation
preserves valid review while substantive changes require a fresh review.
