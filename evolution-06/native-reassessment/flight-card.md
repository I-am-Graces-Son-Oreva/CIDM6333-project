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

Pending.
