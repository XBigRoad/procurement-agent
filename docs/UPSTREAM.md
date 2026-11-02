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
