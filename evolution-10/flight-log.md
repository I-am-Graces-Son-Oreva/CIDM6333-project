# Sortie 10 flight log

The independent Chase gave GO on the [frozen flight card](flight-card.md)
and [prediction](prediction.md). The sortie ran offline from a clean clone
at the [recorded launch commit](evidence/launch-commit.txt). The witness
removed only the exact-grant check in that clone. It used a deterministic
grader, with one trial per case and no paid calls.

| TP | Result | Evidence |
| --- | --- | --- |
| 1 | GREEN, 12/12, exit 0 | [Results](evidence/tp1/results.json) · [delta](evidence/tp1/delta.json) |
| 2 | RED, 7/12, exit 1. Exactly five predicted IDs failed. | [Removal diff](evidence/tp2-removal.diff) · [results](evidence/tp2/results.json) · [delta](evidence/tp2/delta.json) |
| 3 | GREEN, 12/12, exit 0. All five recovered after restoration. | [Results](evidence/tp3/results.json) · [delta](evidence/tp3/delta.json) |
| 4 | RED, exit 1. The grader rejected the planted allow for `mit-p-hi`. | [Results](evidence/tp4/results.json) · [delta](evidence/tp4/delta.json) |
| 5 | No hollow cases in 24 Boolean stub trials. | [Results](evidence/tp5/results.json) · [delta](evidence/tp5/delta.json) |

The [ledger](evidence/ledger-slice.jsonl) records actual and expected exit
codes and RED IDs for all five test points.

## CHASE

VERDICT: PASS — Codex independent Chase — 2026-11-23 — Removing only the exact-grant rejection produced exit 1 and exactly the five preregistered regressions. TP1 and TP3 passed all 12 cases with exit 0, TP4 rejected the planted `mit-p-hi` allow with exit 1, and each TP5 case passed exactly one of the two Boolean constants.

## Debrief

The witness matched the prediction. Removing the pair-membership check
allowed five unauthorized actions while the separate unknown-identity and
outside-MVP controls still refused their inputs. Restoring the rule recovered
all five cases. One constant alone would appear competent on part of the
suite, but neither constant can pass the whole suite and no case accepts both.
These results support the exact authorization rule in isolation. Coverage of
provider data and LIVE admission requires separate evidence.

The repository includes a [manually dispatchable CI job](../.github/workflows/e10-gate.yml)
that calls the gate. The recorded flight uses local execution.

## Reassessment amendment

The [hollow-case positive control](hollow-amendment.md) detected a
single scratch assertion that would accept either Boolean decision. The
original corpus and baseline remained unchanged. The earlier TP5 result
only established that none of the original equality cases accepted both
constants. The positive control separately demonstrates detection.
