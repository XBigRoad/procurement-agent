# Quality guidelines

Use deterministic Decimal money arithmetic and validate finite bounded numbers.
Every new blocker or correction needs a regression proving the decision gate in
JSON, reports and UI. All recommendation fields are null while the batch is blocked.
Keep source hashes byte-exact. Only shipped golden fixtures specify LF checkout;
never normalize a user's original evidence file before computing its hash.
Reference records require explicit role, matching scope, complete costs and valid
date. A current quote cannot be its own independent historical or market evidence.
Preserve the initial raw values and record corrected values separately.

Tests must run from a clean tracked-file export. Generate workbook fixtures with
`templates.write_templates(tmp_path, as_of=ANALYSIS_DATE)` or an explicit in-memory
workbook; read committed JSON fixtures directly when appropriate. Locally generated
`samples/v1/*.xlsx` and `output/` files are ignored and cannot be test prerequisites.
Keep each test's generated inputs inside its own `tmp_path`. CI checks both Windows
and Ubuntu using the same lock file and source fixtures.
