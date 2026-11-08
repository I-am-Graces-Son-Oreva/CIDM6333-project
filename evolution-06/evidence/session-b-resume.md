# Evolution 6 — Session B Resume Evidence

## TP4 — Fresh-session resume

Result: **PASS**

Session B was started as a fresh OpenCode session without loading Session A's transcript.

Handoff Next Step 1:

`Read evolution-06/runtime-ledger.jsonl and report the latest event type.`

Observed first action:

Session B read `evolution-06/runtime-ledger.jsonl` as the handoff's first action.

Observed latest event:

`handoff_written`

Questions requiring information already contained in the handoff:

`0`

## TP5 — Layer conflict

Result: **PASS**

The planted L3 derived view claimed:

- latest event was `compaction`;
- Session A was still active;
- no handoff had been written.

The L2 append-only ledger proved:

- the latest event was `handoff_written`;
- compaction had already occurred;
- the handoff existed.

Session B applied:

`L2 ledger > L1 canon > L3 derived views`

Winner:

`L2`

Did stale L3 block work?

`No`

## Overall

TP4: **PASS**

TP5: **PASS**
