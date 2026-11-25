# E6 native automatic compaction boundary witness

Use OpenCode 1.18.20 in a new scratch session with a scripted loopback
provider. Configure the resolved model with 8,000 context tokens, 6,400
input tokens, and zero reserved tokens in the native compaction setting.
The test provider sends an ordinary response with reported usage over
6,400 tokens. It emits a fixed summary that carries the synthetic next
action when OpenCode requests compaction. The driver must observe a
native automatic compaction record and a subsequent assistant turn in
the same session. The subsequent request must contain the retained action.

This is a controlled test of native threshold and continuation wiring.
Provider usage in this witness is synthetic. Model quality and the
historical hosted provider's actual limits are outside the claim.
Failure means missing or manual compaction, a different session, missing
retained action, or incomplete export. Route failure aborts the trial.

## CHASE

GO — Codex independent Chase — 2026-11-25 — 33306b0

## Postflight

PASS — Codex independent Chase — 2026-11-25 — E6 native boundary witness (GO 762a3d4).

The first recorded response contained 6,510 total tokens against the
configured 6,400 input limit. OpenCode recorded a compaction part with
`auto: true`, a summary, and a later non-summary assistant turn in the
same session. The script captured the retained action in the continuation
request. The process exited 0 and the driver issued no manual compact
command. [Native event and request projection](observed.json)

This establishes the scripted above-threshold runtime path. It does not
measure the historical provider's model limit or summarization quality.
It also does not establish that the summary was the only source of the
retained action.

The [driver](run.py.txt) preserves the executed source. To replay locally,
copy it to a scratch Python file and run it from the repository root.
It requires OpenCode 1.18.20 and a local loopback listener. It starts
no remote model, provider or production workflow.
