---
name: final-slate-review
description: Use when an M6-ranked candidate set is being checked against the authoritative M4 slate, M8 ceiling, or M7 T-20 removals.
---

# Final Slate Review

Review the receipt-bound M8 proposal. The ceiling limits selections; it is never a target to fill. Only Joseph can make the official final decision.

## Procedure

1. Bind the review to the exact run and its receipt-verified M4 slate manifest. Do not accept a caller-supplied slate size, ceiling, or replacement pool.
2. Use M8 `finalize_slate()` with the authorized `CandidateCase` inputs. M8 reproduces M6 ranking, confidence eligibility, and Senior priority internally; do not manually reorder candidates or accept caller-created ranks/audits as authority.
3. Preserve the frozen ceiling pool: HALF SLATE permits at most four selections and FULL SLATE at most five. Zero qualifying selections is valid. A ceiling is not a target.
4. Apply M7 T-20 results only to candidates in that frozen pool. Preserve `STILL STRONG`, `DOWNGRADED`, and `REMOVE RECOMMENDED` as review conclusions, not Joseph decisions.
5. Keep M6 exclusions and candidates outside the frozen pool visible. If T-20 removes a candidate or evidence is unavailable, do not promote an outside candidate or fill the open slot.
6. Present the receipt-bound proposal, exclusions, unresolved gaps, and stop reason to Joseph. Only the existing interactive decision path may record `APPROVE`, `REJECT`, or `MODIFY`.

## Boundaries

- Do not change authorization, methodology, confidence eligibility, Senior priority, or slate ceilings during review.
- Do not replace M8 ranking/finalization with a skill-authored ranking or a manual candidate list.
- Do not treat a proposal, T-20 conclusion, or reviewer `PASS` as Joseph's approval.
