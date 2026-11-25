# E1 follow-up · Lower step limit

The original native OpenCode result at five steps stays fixed. Reuse the
existing pointer-chain fixture with OpenCode 1.18.20, a scratch copy of the
graduate triage persona, and a local Llama model. The only authority in the
scratch configuration is reading local fixtures. No writes or task
delegation are authorized.

Run one native session at three model steps. The chain must remain
incomplete, and the export must show two reads followed by an explicit
step-limit explanation with no further tool call. Preserve a shape-only
export, the tested persona's step count and the number of completed
reads. A missing receipt, a natural stop before two reads, an extra tool
call, or a claim of completing the chain falsifies the witness. If the
local route times out or is unavailable, record ABORT.

This is a configuration-boundary witness on a different model from the
historical Big Pickle route. It does not change the historical verdict.

## CHASE

GO — Codex independent Chase — 2026-11-25 — 2df54f3

## Attempt 1 and substrate amendment

Attempt 1 had one completed read and one tool error, followed by a stop
without the required explanation. The files were copied under `fixtures/`,
but the unchanged links specify `evolution-01/fixtures/`. The successful
process exit does not count as a witness PASS.
[Recorded events](attempt-1.json)

The retry places the same fixture bytes at their original relative path
and updates the single read allowlist and initial path to match. The
route, limit, expected behavior and falsifiers are unchanged. No retry
until the Chase records a new GO here.

GO — Codex independent Chase — 2026-11-25 — 9c7505e (layout-only amendment).

### Attempt 2 result

FAIL — Codex independent Chase — 2026-11-25 — E1 attempt 2 (GO ab8a995).

The native trace shows three step starts, two completed reads, and no
further tool call. All eight fixture digests matched. The model did not
produce the required explicit explanation that the step limit left the
chain incomplete. Exit 0 does not prove the explanation. This witness
establishes the lower read count and leaves the older five-step verdict
unchanged. [Trace projection](attempt-2.json) · [Fixture digests](fixture-digests.json)

### Configured-limit comparison

The [original native export](../evidence/tp2-sanitized.json) contains five
step starts, four completed reads and a final stop. The
[lower-limit export](attempt-2.json) contains three step starts, two
completed reads and a final stop. In both cases, the last step made no
additional tool call. This is direct evidence that the smaller configured
limit was reached. The runs used different models, so the comparison
does not isolate the setting as the sole cause of the observed difference.
The lower-limit run's missing user-facing explanation remains a FAIL.

### Native rerun with Qwen

Use local Qwen3 4B in OpenCode 1.18.20 with the same read-only chain,
configuration limit, and criteria as attempt 2. A missing explicit
step-limit explanation still fails. Disable thinking to keep the response
within the output budget. The only endpoint is the local model service.

GO — Codex independent Chase — 2026-11-25 — Qwen rerun at `458ceac`.

The [Qwen run](attempt-3.json) reached its 192-output-token limit on
the first step, with no reads and no explanation. The stop reason was
`length`. This run fails the three-step criteria. It does not supersede
the earlier native step-count comparison.

### Llama rerun with an explicit final-answer format

Return to the local Llama 3.2 3B model that completed the two reads.
Keep `steps: 3`, the read-only fixture and the same pass conditions.
Ask for a plain-text final report naming the last completed read and
the reason work stopped. The prompt must not supply a read result or
claim that a stop occurred. Require a fresh Chase GO before dispatch.

GO — Codex independent Chase — 2026-11-25 — Llama final-report retry at `ef4fd95`.

The [Llama final-report retry](attempt-4.json) stopped after two steps.
It completed only the read of step 1. Its report claimed step 2 was read
and step 3 was absent. The tool trace contradicts the first claim, and
byte checks confirmed all eight files were present. The attempt fails
both the read-count and explanation criteria. Attempt 2 remains the
evidence for the three-step runtime boundary.

**FAIL — independent Codex Chase — 2026-11-25 — attempt 4 (GO `6ab1129`).**
The trace shows one completed read and an early normal stop. The answer
misidentified the last read and claimed a verified fixture was missing.
