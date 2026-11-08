# Evolution 6 — TP2 Compaction Evidence

## Trigger

Declared budget: **8,000 tokens**

Declared threshold: **6,400 tokens (80%)**

Session A's final measured provider total before the controlled Sprint
compaction was **17,028 tokens**.

Because this exceeded the declared threshold, the E6 Sprint compactor
was exercised.

## Result

Tokens before: **17,028**

Estimated compacted representation after: **111**

Compaction event recorded: **YES**

Keep list recorded in ledger: **YES**

Keep-list items preserved word-for-word: **YES**

## Important Measurement Note

The `before` value comes from OpenCode's exported provider usage.

The `after` value is the Sprint compactor's local approximation for its
compacted text representation; it is not represented as a provider-billed
token count.

This evidence therefore does not mislabel a local estimate as provider usage.

## Verdict

**TP2 PASS for the Sprint compactor mechanism.**

All declared keep-list items survived compaction verbatim and the append-only
ledger contains the compaction event with before, after, and `kept[]`.
