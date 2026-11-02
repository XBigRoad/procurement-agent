# Upstream sources

Checked and combined on 2026-11-01.

## procurement-agent-skills

- Source: https://github.com/gasquet82-code/procurement-agent-skills
- Retrieved commit: `b27d641b3558fbb6b9fbcfd7b4edd54493711100`
- Role here: business skills, safety rules, output formats and procurement terminology.
- Note: the source repository did not contain a LICENSE file in the retrieved revision. Keep attribution and confirm reuse terms before external redistribution.

## rfqdiff

- Source: https://github.com/yigitcan-ozturk/rfqdiff
- Retrieved commit: `7a99522bd86d23fa44e555b1aa9fc83d1ca2df30`
- Role here: deterministic commercial quotation scoring and report export.
- License: MIT; original license is retained in `rfqdiff-upstream/LICENSE`.

## Design boundary

The LLM/Skill layer may extract, explain and ask for clarification. Numeric calculations, thresholds, rankings and provenance remain deterministic. A reasonableness flag is not an award decision.

## Enterprise V1 extension, 2026-11-02

`procurement_agent/scoring.py` adapts the MIT rfqdiff ratio formulas for Decimal
arithmetic, zero-day delivery and exact-score ties. The retained upstream tree
stays available as the original reference and regression suite. The production
service uses a single enterprise pipeline for evidence, tax/fee normalization,
comparability, scoped references, risk decisions and human-review replay.

`.gitattributes` pins the shipped pilot CSV to LF so its existing golden SHA256
stays byte-identical on Windows and Linux. Uploaded quotation bytes are not changed.

Steedos purchase is a workflow/object-model reference only; it is not installed or
vendored into this V1, and no order, approval mutation or supplier messaging is added.
