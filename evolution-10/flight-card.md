# Flight card · Sortie 10

The cross-family E9 prerequisite passed at `4edbff7`. Graded execution
requires a fresh dated Chase GO.

| Field | Record |
| --- | --- |
| Envelope | Expansion |
| Design claim | Removing the exact-grant check or planting a wrong authorization answer turns the gate red. |
| Systems under test | Fifth Pick authorization, `evals/golden.jsonl`, code grader, baseline, delta and CI gate |
| Substrate | Python, frozen universe v1, no model route, judge none (code graders only) |
| Depends on | Sortie 9 PASS with an adversary from a different model family |
| Pre-registered | Preregistered suite commit `dc7f30b`. Golden SHA-256 `df83d560b81d7070f691b694180535c5cdf11b7ea39453471abf4620ed83b434`. See [prediction](prediction.md) for threshold, cases, predicted RED IDs and exact removal. |

| Test point | Observable |
| --- | --- |
| 1 | Clean build exits 0 with zero regressions. |
| 2 | Remove only the exact-grant check. Exit 1 with exactly the predicted IDs, plus a ledger event. |
| 3 | Restore the source. Exit 0 with the same IDs green and zero regressions. |
| 4 | Plant an allow result for `mit-p-hi`. The code grader rejects it. Order swapping applies to model judges. |
| 5 | Evaluate both Boolean constants. No case passes against both. |

Preserve results, deltas, exit codes and the ledger. Model judge transcripts
apply if a model judge is used.

## Falsifiers

- The gate goes green with the exact-grant check removed.
- The grader accepts the planted error, or a model judge changes its verdict when order swaps.
- A golden case passes under every constant stub.
- The threshold, cases, or baseline change after the first run to obtain a pass.

## Abort

If a model judge is required and its route is unavailable or rate-limited,
complete TP1–3 and TP5, record TP4 as aborted, then re-fly it. This version
uses a code grader.

## CHASE

GO — Codex independent Chase — 2026-11-23 — 9516b64
