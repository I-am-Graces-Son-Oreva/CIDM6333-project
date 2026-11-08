# Evolution 6 Handoff

## Current state

Session A completed six user turns and produced twelve actual OpenCode model calls.

All twelve calls have provider usage records in the runtime ledger.

The Sprint compactor was exercised after the measured context exceeded the declared 6,400-token threshold.

The declared keep list survived compaction word-for-word.

The working branch is main.

## Important context

The declared turn budget is 8,000 tokens and the compaction threshold is 6,400 tokens.

Do not use or paste Session A's transcript into Session B.

The raw OpenCode export is local evidence only and must not be committed.

The runtime truth is evolution-06/runtime-ledger.jsonl.

## Decisions with attribution

Joseph's Evolution 6 Flight Card declares the following precedence:

L2 ledger > L1 canon > L3 derived views.

The decision was recorded before flight in evolution-06/flight-card.md.

A stale L3 view must never override the L2 ledger.

## Next steps

1. Read evolution-06/runtime-ledger.jsonl and report the latest event type.

2. Read evolution-06/evidence/stale-status.md and compare its claim with the ledger.

3. Follow the L2 ledger if the stale L3 view contradicts it.

## Pending work

TP4: start a genuinely fresh Session B with no Session A transcript and verify that its first action is Next Step 1.

TP5: present the planted stale L3 view and verify that Session B follows L2 and logs the conflict.

README layers-of-truth declaration, Design Analysis, Flight Log, and AI_LOG entry remain to be completed.

## Verification checklist

Run:

python3 -m pytest tests/test_e6_context.py -q

Then inspect:

evolution-06/runtime-ledger.jsonl
evolution-06/evidence/session-a-budget.md
evolution-06/evidence/tp2-compaction.md

Verify that the ledger currently contains twelve turn_budget events, one compaction event, and one handoff_written event.

## Evidence

evolution-06/flight-card.md
evolution-06/runtime-ledger.jsonl
evolution-06/evidence/session-a-budget.md
evolution-06/evidence/tp2-compaction.md
evolution-06/evidence/compacted-context.txt
tests/test_e6_context.py

