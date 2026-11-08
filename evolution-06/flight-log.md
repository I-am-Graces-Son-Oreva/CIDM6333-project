# Evolution 6 — Flight Log

## Mission

Prove that context can be measured, compacted, handed off, and resumed by a
fresh session without losing intent.

Declared turn budget: **8,000 tokens**

Declared compaction threshold: **6,400 tokens (80%)**

Harness used for Session A and Session B: **OpenCode 1.18.20**

Model route: **Big Pickle**

## TP1 — Budget meter

**Verdict: PASS**

Session A contained six user turns.

OpenCode's export contained twelve actual assistant/model calls because some
user turns caused additional calls for tool use.

All twelve model calls contained provider token-usage fields.

A sanitized measurement table is stored at:

`evolution-06/evidence/session-a-budget.md`

The raw OpenCode export is intentionally not committed because it may contain
repository contents.

## TP2 — Compaction and keep list

**Verdict: PASS**

The declared budget was 8,000 tokens and the threshold was 6,400.

Session A's final measured provider total before the controlled Sprint
compaction was 17,028 tokens.

The Sprint compactor recorded:

- before: 17,028
- after: 111 local estimated tokens
- keep-list items: 10
- keep-list items preserved verbatim: 10/10

The `after` value is a local approximation of the compacted representation,
not a provider-billed token count.

Evidence:

`evolution-06/evidence/tp2-compaction.md`

`evolution-06/evidence/compacted-context.txt`

## TP3 — Handoff

**Verdict: PASS**

Session A wrote:

`evolution-06/handoff.md`

The handoff contains the seven required sections:

1. Current state
2. Important context
3. Decisions with attribution
4. Next steps
5. Pending work
6. Verification checklist
7. Evidence

A SHA-256 hash was recorded in the append-only runtime ledger through a
`handoff_written` event.

## TP4 — Fresh-session resume

**Verdict: PASS**

A new OpenCode Session B was started without loading Session A's transcript.

The handoff's first action was:

`Read evolution-06/runtime-ledger.jsonl and report the latest event type.`

Session B performed that action first and reported:

`handoff_written`

Session B asked zero questions whose answers were already contained in the
handoff.

A `session_resumed` PASS event records the result.

Evidence:

`evolution-06/evidence/session-b-resume.md`

## TP5 — Stale L3 conflict

**Verdict: PASS**

A deliberately stale L3 file claimed:

- the latest runtime event was `compaction`;
- Session A was still active;
- no handoff had been written.

The L2 runtime ledger proved that a handoff had been written.

Session B applied the declared precedence:

`L2 > L1 > L3`

Session B followed L2 and stated that the stale L3 view blocked nothing.

A `layer_conflict` PASS event records the result.

## Falsifier Review

The sortie would fail if:

- Session B asked a question already answered by the handoff;
- Session B performed a different first action;
- stale L3 information overrode L2;
- required budget or compaction evidence was missing;
- Session B passed only because Session A's transcript was pasted into it.

None of these falsifiers were observed.

## Test Results

`python3 -m pytest tests/test_e6_context.py -q`

Observed result before final documentation:

`5 passed`

## Overall Verdict

**PASS**

TP1: PASS

TP2: PASS

TP3: PASS

TP4: PASS

TP5: PASS


## Chase Post-Flight Review — Initial Flight

**Verdict: FAIL**

Chase reported:

`CHASE POST-FLIGHT: FAIL — Session B's first action was reading handoff.md and flight-card.md before the ledger, so it did not exactly match Handoff Next Step 1 (falsifier 2).`

### Diagnosis

The initial Session B bootstrap prompt instructed the fresh session to orient
itself using the handoff, Flight Card, and runtime ledger before performing
Next Step 1.

The observable OpenCode trace therefore read the handoff and Flight Card before
the runtime ledger.

Although Session B later described the ledger read as its first handoff action,
the observable tool trace did not exactly satisfy the preregistered first-action
requirement.

The falsifier is therefore valid.

### Corrective action

The re-flight will use the handoff information as the bootstrap context.

The fresh resume session will be given the handoff instructions directly and
will not be instructed to pre-read other repository files before executing
Next Step 1.

The original failed result is retained as evidence.


## Chase Final Post-Flight Review

**Verdict: PASS**

Chase reported:

`CHASE FINAL POST-FLIGHT: PASS — The original B failure remains documented (falsifier 2: it read handoff.md and flight-card.md before the ledger), but corrective B2's observable first repository action exactly matched Handoff Next Step 1 (read evolution-06/runtime-ledger.jsonl and report layer_conflict) with zero answered questions, no Session A transcript, L2 winning TP5, an intact handoff hash, 12/12 Session A budget records, and a recorded compaction event, so no falsifier remains.`

The final verdict preserves the original failed TP4 attempt and accepts the
corrective B2 re-flight as the successful test of the revised bootstrap
protocol.
