# Procurement review MVP

## Goal and authorization
Deliver the user's requested local installation, working structured quotation review,
tests, optimization, and GitHub update. The user explicitly authorizes implementation,
local deployment, testing and push in this session. Their AGENTS priority places these
instructions above skill suggestions for additional planning approvals.

## Requirements
- R1: Read multiple Excel/CSV/JSON quotes, Chinese and English headers, and preserve
  immutable original field values, file SHA256, cells/rows/JSON pointers.
- R2: Extract supplier, item, specification/configuration, quantity, unit, currency,
  net/gross price, tax, freight/installation, delivery, payment and warranty.
- R3: Normalize declared tax and fee bases with deterministic decimal arithmetic.
  Missing, contradictory, nonfinite, ambiguous or formula-only values stay visible.
- R4: Compare within an item only. Different units, quantities, currencies, technical
  specifications or scope require human resolution. Duplicate supplier/item offers
  cannot masquerade as independent bidders.
- R5: Provide configurable price/delivery/payment scores and exact contributions.
- R6: Compare current peers, matched dated company purchases, same-supplier historical
  quotations and supplied dated market references. Reject unrelated/stale references.
- R7: Classify normal, low explained, abnormally low, high explained or insufficient
  evidence. An explanation requires a named human review and evidence reference.
- R8: A blocked decision has no recommended supplier anywhere in its JSON/Excel/UI.
  Return candidates, blockers and supplier questions. Every recommendation is conditional.
- R9: Apply an input-bound review file, preserve before/after audit entries and recompute
  all numbers/flags. Corrections cannot erase original evidence or bypass validation.
- R10: Deliver JSON, detailed Excel, Chinese advice, reusable templates and Windows launch
  commands. A small localhost upload/review interface may accompany the core.
- R11: Run regression, acceptance and local startup checks; push verified code to the
  existing GitHub repository. It is currently PUBLIC; use synthetic data exclusively.

## Acceptance
- Tests cover 2, 5 and 12 suppliers, three categories, valid tax conversion, invalid
  values, unknown fees, unequal specifications/units/quantities/currencies, duplicate
  suppliers, unrelated history, stale markets and historical-only low prices.
- Test blocked recommendation consistency and review re-computation/audit/stale binding.
- Verify spreadsheet cells trace to files; export user strings as text, never formulas.
- Demonstrate ordinary and blocked/reviewed runs with JSON, Excel and Chinese advice.
- Preserve existing upstream tests or explain any verified upstream packaging limitation.

## Boundaries
PDF/OCR, semantic technical equivalence, ERP/SRM, lifecycle costing, authenticated
multiuser deployment and automatic external market collection are future scope.
The application exposes no award/order/payment/contract/supplier-messaging action.
