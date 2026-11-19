---
name: evaluate-candidate
description: Use when an NBA fantasy prop has passed M3 authorization and needs one-candidate M6 methodology evaluation before ranking.
---

# Evaluate Candidate

Use the frozen methodology and M6 evaluator as the authority. Evaluate one eligible prop at a time; this procedure does not rank candidates or finalize a slate.

## Procedure

1. Confirm the candidate's canonical identity, platform, event, category, and direction. M3 authorization is a hard boundary; do not broaden it based on evidence or a projection.
2. Bind the candidate to its M5 observations and provenance. Snapshot 3 is the T-20 observation. Do not reconstruct, retime, or backfill a missing observation.
3. Review the available evidence in context, including projection movement, recent performance, same-season opponent history when available, role and availability, and relevant game or player conditions. Cite the evidence IDs used for support and risk. Use only authorized sources and preserve platform separation.
4. Apply the relevant rules in the frozen design. Do not turn qualitative factors into a score, add a threshold, or make a single trend or player label an automatic decision.
5. Express the judgment with the typed M6 fields and cited evidence IDs, then use `fifth_pick.methodology.evaluate_candidate()` to produce the `CandidateAudit`. Do not substitute a hand-written confidence or status for the evaluator's result.
6. Report the candidate key, M6 status and confidence, cited support and risks, and any gaps or exclusions. A material unresolved gap must remain visible and must not be filled by inference.

## Boundaries

- `QUALIFIED` is an M6 result, not a rank, final selection, or Joseph approval.
- `INSUFFICIENT EVIDENCE`, `BLOCKED`, and other non-qualified results are not promoted to keep work moving.
- If critical evidence is unresolved, return `INSUFFICIENT EVIDENCE` with no confidence judgment. Do not assign provisional `LOW` confidence as a holding value.
- Do not invent source facts, rely on name-only identity, combine platform lines, or claim that a retained excerpt proves source authenticity.
- Keep the full methodology in the frozen design and M6 implementation; this skill is a procedure, not a replacement specification.
