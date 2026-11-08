# Evolution 6 — Flight Card 6

## Sortie

Sortie 6 — Context Engineering and Handoff

## Envelope

Expansion

## Dependency

Sortie 5: PASS

Evolution 5 hardened the MCP server and measured AGENTS.md under its required limit.

## Design Claim

A handoff written at session end lets a fresh session resume with no loss of intent:

**the fresh session's first action is the one the handoff named.**

## Systems Under Test

- per-turn budget meter
- compactor with declared keep list
- handoff writer
- resume loader
- append-only runtime ledger
- layers-of-truth declaration

## Substrate

Repository: `CIDM6333-project`

Branch: `main`

Harness: OpenCode 1.18.20

Model/route: OpenCode Big Pickle

Declared turn budget: **8,000 tokens**

Compaction threshold: **80% = 6,400 tokens**

Token source: provider usage fields returned for each model call.

If provider usage fields are unavailable, the flight ABORTS unless a fallback count has been declared before flight.

## Declared Keep List

The following must survive compaction:

1. Current objective:
   `Complete Sortie 6 and prove that a fresh session can resume from the handoff without loss of intent.`

2. Open test point.

3. Exact next action.

4. Pointers to L1 canon:
   - `AGENTS.md`
   - `evolution-06/flight-card.md`
   - `README.md`

5. Pointer to L2 runtime ledger:
   - `evolution-06/runtime-ledger.jsonl`

6. Settled decisions:
   - L2 ledger outranks L1 canon.
   - L1 canon outranks L3 derived views.
   - A stale L3 view cannot block or override the ledger.

The declared keep-list text must survive compaction word-for-word.

## Layers of Truth

### L1 — Canon

Human-written rules and decisions.

Primary paths:

- `AGENTS.md`
- `README.md`
- `evolution-06/flight-card.md`
- `evolution-06/handoff.md`

### L2 — Ledger

Append-only runtime truth.

Primary path:

- `evolution-06/runtime-ledger.jsonl`

Required event types include:

- `turn_budget`
- `compaction`
- `handoff_written`
- `session_resumed`
- `layer_conflict`

### L3 — Derived

Regenerable views and summaries.

Examples:

- compaction summary
- status/derived-state files
- stale test view used in TP5

Precedence:

**L2 > L1 > L3**

L3 can never block a gate.

## Test Points

### TP1 — Per-Turn Budget

Session A runs a bounded task for at least six model calls.

PASS requires one `turn_budget` record for every call containing:

- session
- turn
- in
- out
- total
- budget
- percentage used
- action taken

No model call may be missing its budget record.

### TP2 — Compaction

Context crosses the 80% threshold.

PASS requires:

- compaction occurs;
- a `compaction` event records tokens before and after;
- the event records `kept[]`;
- the declared objective survives;
- L1 and L2 pointers survive;
- keep-list text survives word-for-word;
- the task continues after compaction.

### TP3 — Handoff

Session A ends.

PASS requires `evolution-06/handoff.md` with seven sections:

1. Current state
2. Important context
3. Decisions with attribution
4. Next steps
5. Pending work
6. Verification checklist
7. Evidence

Next Step 1 must be one concrete action.

A `handoff_written` ledger event records the handoff hash.

### TP4 — Fresh Resume

Start a genuinely fresh Session B.

Session B receives:

- the handoff;
- required L1 files;
- the L2 ledger.

Session B does **not** receive Session A's transcript.

PASS requires:

- B's first action exactly matches Handoff Next Step 1;
- B asks zero questions already answered by the handoff;
- a `session_resumed` event is written;
- B's first two turns are captured verbatim.

### TP5 — Layers-of-Truth Conflict

Plant a stale L3 derived view that contradicts the L2 ledger.

PASS requires:

- Session B detects the contradiction;
- B follows L2;
- L3 does not block or override the ledger;
- a `layer_conflict` event records the conflict and resolution.

## Instrumentation

Evidence will include:

- per-turn budget records
- compaction event
- ledger diff
- `handoff.md`
- handoff SHA-256 hash
- Session B's first two turns verbatim
- stale L3 test artifact
- conflict-resolution event

The runtime ledger is append-only.

## Pre-Registered Falsifiers

Any one of these means FAIL:

1. Session B asks a question the handoff already answered.
2. Session B's first action is not Handoff Next Step 1.
3. An L3 view contradicts the ledger and wins.
4. Any model call has no budget record.
5. Compaction occurs without a compaction event.
6. Session B passes because Session A's transcript was pasted into it.
7. The handoff is edited after Session B begins.

## ABORT Conditions

ABORT rather than FAIL if:

- the provider returns no usage fields and no fallback was declared before flight;
- the required model is unavailable;
- the harness cannot provide the evidence necessary to evaluate the claim.

## Chase Evidence Slice

Before flight, the Chase reads this Flight Card.

After flight, the Chase reads only:

- budget log / turn-budget records;
- ledger diff;
- `handoff.md`;
- Session B's first two turns.

The Chase does not rely on the author's summary.

## GO / NO-GO

**Status: AWAITING CHASE REVIEW**

No official Sortie 6 flight begins before Chase GO.

### Chase Review

Verdict: PENDING

Reason: PENDING
