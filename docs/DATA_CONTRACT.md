# MVP inter-module contract

## Input records
`ingest.load_records(path: Path, kind: str = "quotes") -> list[dict]` accepts
`.csv`, `.xlsx`, `.json`. `kind` is quotes/history/market. Canonical fields:

supplier, item_id, item_name, category, specification, configuration, brand, material,
grade, quantity, unit, currency, unit_price_excl_tax, unit_price_incl_tax,
total_price_excl_tax, total_price_incl_tax, tax_rate, freight, installation,
packaging, commissioning, tooling, fee_basis, fee_tax_rate, freight_tax_rate,
installation_tax_rate, lead_time_days, lead_time_weeks, payment_days, payment_terms,
payment_anchor, prepayment_percent, warranty_months, scope_complete, quote_date,
valid_until, record_date, record_type, price, price_basis, notes, source_url.

Read values without silently repairing them. `name` aliases supplier, `spec` aliases
specification. Legacy price remains price; it is not assumed to be net/gross or unit.
Chinese aliases include 供应商/供应商名称, 物料编码/物料名称, 规格/规格型号, 数量,
单位, 币种, 含税单价/未税单价/含税总价/未税总价, 税率, 运费, 安装费, 交期(天),
账期(天), 付款条件, 质保(月), 报价范围完整. Category values normalize in engine.

Reader-generated metadata (reject attempts to inject these from input):
- `quote_id`: stable identifier from file hash + sheet/row or JSON pointer; unique
  within the input. Never use supplier alone as the identity.
- `_source`: {file, sha256, format, sheet?, row?, json_pointer?}.
- `_evidence`: mapping canonical field -> {file, sha256, format, sheet?, row?,
  column?, cell?, json_pointer?, raw_value, formula?}; every supplied value traced.
- `_input_issues`: list of {code, field, message}. Formula-only/cached formula values
  need explicit review; do not evaluate Excel formulas or external links.

JSON accepts array of objects, {quotes:[...]}/{records:[...]}, or a single object.
Legacy {prices:[numbers]} may become records with price but will be excluded as
unscoped references. Duplicate canonical headers fail explicitly. Excel scans up
to 30 leading rows for a table header, reads all nonempty table worksheets and
retains actual cell positions. Preserve unknown business fields/evidence where safe.

## Engine and service API
`engine.compare_records(quotes, *, history=None, market=None, weights=None,
policy=None, review=None, as_of=None) -> dict`

`service.run_comparison(quote_paths, *, history_paths=(), market_paths=(), weights=None,
policy=None, review=None, as_of=None) -> dict` loads inputs then invokes engine.
weights/policy/review are dicts (CLI/UI parse JSON). as_of is YYYY-MM-DD or None.
`engine.create_review_template(result) -> dict` returns an input-bound editable file.

## Result (plain JSON)
- schema_version, run_id, input_digest, generated_at, as_of, weights, policy.
- input_files: source metadata list; assumptions: string list.
- quotes: normalized records including quote_id, supplier, item_id, item_name,
  category, specification, configuration, quantity, unit, currency,
  unit_price_excl_tax, unit_price_incl_tax, tax_rate, fees_excl_tax,
  normalized_total_excl_tax, normalized_total_incl_tax, lead_time_days,
  payment_days, payment_terms, warranty_months, scope_complete, evidence, raw_fields.
  `raw_fields` always contains original values; `effective_fields` holds reviewed
  values. `reviewed_fields` and `audit_log` explain each change; calculation_steps
  describe derived money. `_reviewed_fields` is reserved reader/engine metadata.
- rankings: flat list grouped by item_id, with quote_id/supplier/item_id, rank,
  score, price_score, lead_time_score, payment_terms_score,
  normalized_total_excl_tax, currency, lead_time_days, payment_days,
  classification, eligible_for_recommendation, blockers (code list).
- item_results: {item_id, status, candidate_suppliers, recommended_supplier} list.
- findings: {quote_id, supplier, item_id, classification, status, flags, reasons,
  peer_median, peer_delta, history_median, history_delta,
  supplier_history_median, supplier_history_delta, market_median, market_delta} list.
  classification values: normal, low_explained, abnormally_low, high_explained,
  insufficient_data. status values: within_reference_range, review_required,
  review_recommended. All four baseline families expose matched reference ids.
- issues: {quote_id, item_id, supplier, code, severity, field, message, question}
  list; severity blocker/warning/info.
- evidence: {quote_id, supplier, field, ...source evidence} list.
- reference_exclusions: {reference_id, reason} list; audit_log: review entries.
- procurement_decision: {status, recommended_supplier, candidate_supplier,
  candidate_suppliers, blocking_flags, reason}; status manual_review_required or
  conditional_recommendation. All recommended_supplier projections are null when
  blocked; rank alone never authorizes award. Top-level recommended_supplier and
  candidate_supplier mirror the decision. Multiple item winners are not forced
  into a single supplier; see item_results.
- advice_zh: Chinese narrative populated by service via reports.build_advice.

## Review input
{input_digest, reviewer, reviewed_at, corrections: [{quote_id, field, value,
reason, evidence}], explanations: [{quote_id, kind, reason, evidence}]}.
`kind` is low_price, premium or payment_terms. Engine requires a named reviewer, ISO date/time,
correct digest, known ids/fields and nonempty reasons/documentary references.
Corrections update business fields only; original evidence remains. Every change
gets before/after audit metadata. Explanations do not clear missing/invalid fields
or incomparable specifications; corrected business data must pass the same rules.
The digest binds content hashes, source positions, business values, analysis date
and effective rules. Upload directory, file rename and upload ordering do not
invalidate the same evidence. Re-exported templates include cumulative accepted
corrections and explanations, with a blank reviewer for the next deliberate review.

References require scope_complete and all applicable price/fee metadata. History
must explicitly state purchase or quotation; missing type is excluded, not guessed.
Current quotation IDs/source hashes cannot be reused as historical/market evidence.
Repeated references across roles are excluded to prevent duplicate weighting.
Explicit tax totals and aggregate unit-tax differences are reconciled at 0.02 total
currency-unit tolerance; large quantities never hide contradictory totals.

## Output projection API
`reports.build_advice(result) -> str`
`reports.write_excel(result, path: Path) -> None`
Reports read authoritative findings/decision; no recalculation. Suggested tabs:
采购建议, 供应商评分, 报价明细, 风险与确认, 价格参考, 原始证据, 人工复核, 规则配置.
Use Microsoft YaHei, no fill colors, freeze panes, filters, useful number formats.
All user strings must be written as text (including =,+,-,@ prefixes).
