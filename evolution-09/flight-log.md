# Sortie 9 flight log

The E8 prerequisite passed its [targeted re-flight](../evolution-08/flight-log.md#targeted-tp4-re-flight--2026-11-23).
Joseph reported an extended submission deadline of December 30, 2026.

## Attempt 1 — hosted route

The independent agent Chase gave GO at `5ba85c4`. The hosted MiMo worker
reached its free usage limit and did not produce a validated handoff.
The sortie stopped before TP1. Token totals and provider accounting were
unverified. See the [preserved abort](evidence/attempt-1/abort.md).

## Attempt 2 — local tier-2 re-flight

The Chase gave fresh GO before execution. The harness ran from a clean
checkout of `c59b7b5` with two distinct local Qwen models and separate
contexts. The [harness result](evidence/harness-result.json) records the
failed control.

| Test point | Result | Evidence |
| --- | --- | --- |
| TP1 · Isolate claim | PASS | The [ledger](ledger-slice.jsonl) records the planted claim as unverified, followed by `claim_isolated`. |
| TP2 · Execute fixture | PASS | The [planted receipt](receipts/planted.json) records exit 1 with command, commit, timestamp, and digests. |
| TP3 · Detect false claim | PASS | The [planted verdict](ledger-slice.jsonl) is `REFUTED` and cites `exit_code`. |
| TP4 · Accept true control | FAIL | The [control receipt](receipts/control.json) records exit 0, but the [control verdict](ledger-slice.jsonl) is `REFUTED` and cites `exit_code`. |
| TP5 · Enforce one lease | PASS | The [ledger](ledger-slice.jsonl) records acquisition, denial, expiration, reacquisition, and release in order. |
| TP6 · Account for calls | PASS | The [cost table](cost-table.md) and `sortie_accounting` event record three calls totaling $0.00. |

## Debrief

The test demonstrated why a verdict needs checking even when it cites a real
receipt. The adversary correctly refuted the planted claim but cited the same
field to refute a claim supported by exit 0. This is a false positive on the
preregistered control. The output does not establish why the model made that
error. A follow-up experiment could test whether requiring the adversary to
report the observed field value, then mechanically checking that value
against the receipt, reduces citation errors. The two routes used different
models in the same family, so the result does not establish cross-family
performance.

## CHASE

FAIL — Codex independent Chase (e9_chase), 2026-11-23

TP4 failed. The control receipt records exit 0, but the separate control verdict from `qwen3:4b` was `REFUTED` and cited `exit_code`. The frozen card requires `NOT-REFUTED` and defines a failed observable as a falsification. All four independently recomputed SHA-256 output hashes matched the receipts, both receipts name the approved launch commit, and the ledger records the isolated unverified claim, planted refutation, required lease sequence, and three budgeted calls totaling $0.00.

## Attempt 3 — cross-family local re-flight

The Chase authorized `ba5748b` before execution. Qwen delivered the worker
handoff and Llama evaluated the planted and control claims in distinct
calls. All six observables matched. The [ledger](evidence/attempt-3/ledger-slice.jsonl)
records claim isolation, refutation citing `exit_code`, acceptance of the
true control, lease contention and recovery, and three calls totaling
$0.00. Both [receipts](evidence/attempt-3/receipts/) record the launch
commit, exact commands, exit codes, and output digests.

The adversary's optional missing-fields note incorrectly named two hashes
that were present. The verdict and citation met the card's criteria, but
the note is a separate reliability defect. The harness result cannot attest
to general adversary accuracy.

### CHASE

PASS — Codex independent Chase (e9_chase), 2026-11-23

The cross-family re-flight at `ba5748b` met the preregistered output criteria.
Both receipts name the launch commit and all four recomputed SHA-256 digests
matched. Qualification: the planted verdict incorrectly lists the two output
hash fields as missing. This pass does not establish reliable missing-field
detection.
