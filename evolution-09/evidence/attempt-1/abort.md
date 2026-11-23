# Attempt 1 — ABORT before TP1

- Launch commit `5ba85c4` contains the independent Chase GO.
- At 20:42:13 UTC on November 23, 2026, the router started the free MiMo worker.
- The invocation stopped at its 180-second timeout. The OpenCode runtime log reported “Free usage limit reached” for MiMo. The route ledger contains no verified token or cost values for this attempt.
- There was no worker handoff, graded test-point result, receipt, or adversary verdict. No paid fallback was configured.
- Preserve the [route ledger](ledger-slice.jsonl). The re-flight requires a new card and a new GO.
