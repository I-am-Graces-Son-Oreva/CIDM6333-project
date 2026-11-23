# Flight card · Sortie 9 local re-flight

| Field | Preflight record |
| --- | --- |
| Envelope | Corner of the envelope |
| Design claim | A worker claim stays unverified until checked against a harness-written receipt. In declared tier-2 degraded mode, an adversary in a fresh context refutes the false claim using the receipt. |
| Systems under test | E8 handoff parser, E9 worker route, receipt writer, independent adversary route, file lease and event ledger |
| Substrate | CIDM6333-project on macOS with Python and local Ollama. The E8 reference state is included in commit `a604830783d2834e2c3b8fdc1d04722a92f0f16a`. The harness records the full approved launch commit in each receipt. |
| Worker | `qwen3:1.7b` · Qwen · local |
| Adversary | `qwen3:4b` · Qwen · tier 2, same family and separate context |
| Budget | $0.00, with one worker call and two adversary calls through a loopback-only Ollama route. No external or paid fallback. |
| Dependency | The latest [E8 Chase verdict](../evolution-08/flight-log.md#targeted-tp4-re-flight--2026-11-23) is PASS at `9d5ec4d`. It supersedes the earlier FAIL after the authorized TP4 re-flight. |

## Planted falsehood

After parsing a valid E8-format DONE handoff, the E9 harness replaces the claim
with “All three fixture tests passed.” It leaves the worker’s claim unverified.
The three-test fixture contains a deliberately failing assertion. The
adversary receives only the claim and the corresponding receipt. It does not
receive this card, the worker session, or the answer key. The control executes
two passing tests from the same fixture and makes a separate two-test claim.

## Test points

| TP | Action | Expected observable |
| --- | --- | --- |
| 1 | Receive and parse the worker handoff. Plant the false claim in the harness. | Ledger records a claim with `status: unverified`, then `claim_isolated`. The flight log has not changed. |
| 2 | Independently execute the three-test fixture. | `receipts/planted.json` has command, exit 1, commit, timestamp and SHA-256 hashes. Ledger references the receipt. |
| 3 | Start a fresh adversary session with only the planted claim and receipt. | `adversary_verdict` records `REFUTED`, cites `exit_code`, and names model and family. |
| 4 | Repeat with the clean two-test control and its own receipt. | `receipts/control.json` records exit 0. A separate adversary session records `NOT-REFUTED`. |
| 5 | Worker B requests the same lease as worker A, then tries again after TTL. | `lock_acquired → lock_denied → lock_expired → lock_acquired`, in order. |
| 6 | Compare each call’s model, tokens and cost with the configured budget. | Three model-call records have task class, model, input/output tokens and cost. The cost table totals $0.00. |

Expected evidence includes `receipts/`, the captured output files,
`ledger-slice.jsonl`, and a cost table. The harness writes all of them into
a new sortie output directory.

## Falsifiers

A single occurrence fails the claim.

- A worker claim reaches the flight log without a corresponding receipt.
- The adversary returns `NOT-REFUTED` for the planted falsehood.
- Two workers hold the same lease, or the lease changes owners without a ledger event.
- The test passes only because the adversary was told the answer, used the exact worker model or received the worker context, or read an edited receipt.

The attempt-1 MiMo worker hit a free usage limit before TP1. Its
[original card](evidence/attempt-1/flight-card.md) and
[abort ledger](evidence/attempt-1/abort.md) remain fixed. The assignment allows
tier-2 degraded mode when only one family is available. This re-flight tests
independence of context and a different model ID within Qwen. It cannot establish
cross-family refutation.

The true-claim control must remain `NOT-REFUTED`. A missing route,
unverified usage, unavailable model, or unavailable test runner stops the
run. Preserve any output collected so far and report the exact obstacle.
A failed observable is a falsification and must not be relabeled an abort.

## CHASE

Status **PENDING** for the local re-flight. Joseph reported that an agent may
act as Chase in the absence of a human. The first GO applies only to the
preserved hosted attempt. A separate dated GO is required here before TP1.

GO — Codex independent Chase (e9_chase), 2026-11-23

Scope: local tier-2 re-flight at `610dd8a`.

## Debrief and squawks

Attempt 1 aborted before TP1 when the hosted worker reached the free limit.
No receipt or verdict was produced. Re-flight observations are pending.
