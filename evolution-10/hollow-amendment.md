# Sortie 10 amendment · Hollow detector positive control

The original sortie and golden corpus stay fixed. This follow-up directly
answers the instructor's question about a hollow case.

- **Expected GREEN** · Run `evals/gate.py --hollow` on the frozen golden set.
- **Expected RED** · Copy that set to scratch and add `"assertion": "boolean"`
  to `mit-p-hi` only. Set no other field. Run `--hollow --golden` on the copy.
  The gate must exit 1 and report exactly `mit-p-hi`. Both Boolean constants
  satisfy the weak assertion.
- **Expected GREEN** · Re-run the original corpus. No regression.
- **Falsifiers** · Either constant fails the intentionally weak assertion,
  the witness is reported green, unrelated IDs turn red, or the frozen
  corpus or baseline changes.
- **Scope** · Offline deterministic eval. A custom corpus is only admitted
  by the contradiction check. The regular product gate does not accept it.

## CHASE

GO — Codex independent Chase — 2026-11-24 — 7cf3f86

Scope: review the one-case mutation and unchanged original corpus.

## Observed result

PASS — Codex independent Chase — 2026-11-24 — 4afcbdc.

The original and restored runs were identical and exited 0. The one-field
scratch mutation caused only `mit-p-hi` to accept both Boolean constants,
and the detector exited 1. Both frozen input hashes matched the ledger.
This verifies detection of the planted weakness.

[Mutation](evidence/hollow-amendment/one-case-change.json) ·
[Exit and hash ledger](evidence/hollow-amendment/ledger.jsonl) ·
[RED witness](evidence/hollow-amendment/weak/results.json)
