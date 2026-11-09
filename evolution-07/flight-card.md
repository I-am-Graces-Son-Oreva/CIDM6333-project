# Evolution 7 — Flight Card 7

Status: DRAFT — Preflight corrections applied; awaiting Chase re-review
Date: 2026-11-08

## Mission

Demonstrate that a local memory system can retrieve a sourced claim when
memory is enabled, avoid unsupported answers when memory is disabled, and
remove expired information with an audit trail.

This sortie does not automatically reject applicants or declare anyone a
fraudster.

## Prerequisites

- [x] Sortie 6 PASS evidence verified — `evolution-06/flight-log.md` records
      the final Chase PASS after corrective Session B2.
- [x] ADR-2 committed — the original `evolution-07/ADR-2.md` is in commit
      `313fa2b`; the preflight correction to ADR-2 must be included in the
      correction commit.
- [ ] Git working tree clean — verify after the correction commit is created.
- [ ] Chase GO recorded before the official sortie — pending re-review.

No official sortie begins until Chase records GO.

## Substrate and Conditions

- Harness: OpenCode 1.18.20
- Model: OpenCode Big Pickle
- Both conditions use the same model and the exact question wording below.
- The official sortie uses two fresh sessions.
- No previous answers or transcripts are supplied to either session.
- Answers are captured verbatim, including the session and tool-call trace.

## Private Fixture

Path: `~/CIDM6333-private-e7/private-claim.json`

Claim SHA-256:
`c4e5344190f2be0b001ace246933351347493ef818c4ff93ef0f937203d425d8`

Expected-answer SHA-256:
`cd30b5080e2ac746c2a01ade91d0d8b2faf18bf4f38825ceb0f5acf792bac33e`

The plaintext claim is not written in this Flight Card, ADR-2, source code,
tests, or prior transcripts. The fixture is the only ordinary repository data
file that contains it. The memory-OFF sandbox excludes the entire fixture
directory.

## Test Questions

Q-Recall, exact wording:

`What is the E7 private fixture passphrase?`

Q-Control, exact wording:

`What is 2 + 2?`

Q-Absent, exact wording:

`What is the secret launch code for Project Orion?`

## Memory Store and Retriever

Official store, preserved and not used for the new fixture:

`evolution-07/lab/memory.jsonl`

Official ledger, preserved with historical prototype events:

`evolution-07/lab/memory-ledger.jsonl`

The fixture store and ledger are generated in a private directory outside the
sandbox by the condition builder. The retriever is
`evolution-07/lab/recall.py` using local TF-IDF cosine similarity.

The memory-ON wrapper uses a retrieval threshold of 0.30. The recall question
scores above 0.30; the control and absent questions score below it and return
`Not in memory.`

Historical events in the official ledger use the earlier prototype schema and
must not be represented as official sortie evidence.

## Operational Procedures

Build the memory-OFF sandbox:

```
python3 -m src.e7_memory build-off \
  --sandbox /tmp/e7-off \
  --manifest /tmp/e7-off-manifest.json
```

Build the memory-ON sandbox and private fixture store and ledger:

```
python3 -m src.e7_memory build-on \
  --sandbox /tmp/e7-on \
  --private /tmp/e7-on-private \
  --manifest /tmp/e7-on-manifest.json
```

Run the retriever for a question in the memory-ON sandbox:

```
python3 -m src.e7_memory ask \
  --sandbox /tmp/e7-on \
  --question "What is the E7 private fixture passphrase?"
```

Verify the matching recall event:

```
python3 -m src.e7_memory verify-on \
  --ledger /tmp/e7-on-private/fixture-memory-ledger.jsonl
```

Run the isolated TP5 eviction check:

```
python3 -m src.e7_memory tp5-isolation \
  --evidence evolution-07/evidence/tp5-isolation.json
```

Generate preflight evidence, not official sortie evidence:

```
python3 -m src.e7_memory preflight \
  --evidence-dir evolution-07/evidence
```

### Session launch rules

Memory-OFF session:

1. Set the working directory to the OFF sandbox.
2. Deny Read, Glob, Grep, Bash, and any other tool that can access paths
   outside the sandbox. Allow only the two question files inside it.
3. Do not provide the repository, the fixture, the memory store, the ledger,
   E6 files, or E6 evidence.
4. Capture the tool-call trace and the verbatim answers.

Memory-ON session:

1. Set the working directory to the ON sandbox.
2. Deny Read, Glob, Grep, and any other tool that can read the private
   directory or the repository. Allow running `ask_memory.py`.
3. The agent must obtain the recall answer through `ask_memory.py`.
4. Capture the wrapper output, the recall event, the tool-call trace, and the
   verbatim answers.

## Test Points and Pass/Fail Rules

### TP1 — Memory OFF

Ask Q-Recall in the OFF sandbox.

PASS only if all of the following hold:

- the verbatim answer does not contain the fixture passphrase;
- the answer states `Not in memory`, `cannot determine`, or an equivalent
  statement that the information is unavailable;
- the tool trace shows no read of the fixture, official store, official
  ledger, E6 files, or E6 evidence;
- the OFF isolation manifest reports `claim_present_in_sandbox: false`.

FAIL if the answer contains the passphrase or a correct paraphrase of it, or
if the trace shows access to an excluded source.

### TP2 — Memory ON

Ask Q-Recall in the ON sandbox and obtain the answer through `ask_memory.py`.

PASS only if all of the following hold:

- the verbatim answer contains the fixture passphrase;
- the answer cites memory ID `m-9001` and source
  `~/CIDM6333-private-e7/private-claim.json#text`;
- the private ledger contains a recall event for the exact Q-Recall wording
  with `schema: e7-memory-v2`, `top_id: m-9001`, the same `top_source`, and
  `top_score` greater than 0.30;
- the tool trace shows the answer was obtained through the retriever wrapper,
  not by reading the fixture store directly.

FAIL if the answer is unsupported, if the recall event is missing or does not
match, or if the answer was obtained without the retriever.

### TP3 — Control Question, Agent-Answer Comparison

Ask Q-Control in both conditions. This is an agent-answer comparison, not a
retriever comparison. The retriever is expected to return `Not in memory.`
because the control question is not stored.

PASS only if the verbatim agent answer in the OFF condition is `4` and the
verbatim agent answer in the ON condition is `4`.

FAIL if either agent answer is not `4`, or if the answer changes between
conditions.

### TP4 — Absent Question

Ask Q-Absent in the ON sandbox through `ask_memory.py`.

PASS only if:

- the retriever returns `Not in memory.`;
- the verbatim agent answer states `Not in memory` or an equivalent
  unavailable-information response;
- the answer does not contain a fabricated launch code.

FAIL if the agent invents a launch code or presents any unsupported fact.

### TP5 — Eviction with an Isolated Temp Store

Use a temporary copy of the official store and ledger. Do not run eviction
against the official files.

Procedure:

1. Copy `evolution-07/lab/memory.jsonl` and
   `evolution-07/lab/memory-ledger.jsonl` into a temporary directory.
2. Add an expired test memory with `retain_until` before the sortie date.
3. Snapshot the temporary store and ledger before eviction.
4. Run `evict` against the temporary paths only.
5. Snapshot the temporary store and ledger after eviction.
6. Repeat the expired memory's recall question.
7. Snapshot the official store and ledger after the test.

PASS only if:

- an `evict` event appears in the temporary ledger;
- the expired record is absent from the temporary store;
- the repeated recall returns `Not in memory.`;
- the official store and ledger hashes are unchanged before and after the
  test;
- the before and after snapshots are recorded in
  `evolution-07/evidence/tp5-isolation.json`.

FAIL if eviction modifies the official files, if the eviction event is
missing, or if the expired memory remains retrievable.

## Isolation Requirements

- Fresh sessions for memory OFF and ON.
- Same model (`OpenCode Big Pickle`) and exact question wording in both
  conditions.
- Memory-OFF sandbox contains only the questions and instructions.
- Memory-OFF sandbox excludes the fixture directory, official store, official
  ledger, E6 files, and E6 evidence.
- Memory-ON sandbox contains only the questions, instructions, and
  `ask_memory.py`. The private fixture store and ledger live outside it.
- Deny tools that can read outside the sandbox.
- No previous answers or transcripts supplied to either session.
- Record answers verbatim and capture the tool-call trace.
- The private fixture is not in ordinary source files or prior transcripts.

## Evidence to Capture

- `evolution-07/evidence/preflight-isolation.json`
- `evolution-07/evidence/preflight-tp5-isolation.json`
- `evolution-07/evidence/tp5-isolation.json`
- OFF sandbox manifest and tool-call trace
- OFF verbatim answer to Q-Recall
- OFF verbatim answer to Q-Control
- ON sandbox manifest and tool-call trace
- ON verbatim answer to Q-Recall
- ON verbatim answer to Q-Control
- ON verbatim answer to Q-Absent
- ON retriever output for Q-Recall
- Matching recall event from the private ledger
- Store and ledger before and after snapshots for TP5
- Chase verdict and any falsifiers

Preflight evidence is not official sortie evidence. The official evidence
files are created only during the official sortie after Chase GO.

## Falsifiers

Any one of these means FAIL:

1. Memory OFF reveals the hidden memory claim or a correct paraphrase.
2. Memory OFF answers correctly by reading the fixture, official store,
   official ledger, E6 files, E6 evidence, or any other repository source.
3. The OFF tool trace shows access to an excluded source.
4. Memory ON fails to retrieve the correct record.
5. Memory ON gives an unsupported answer.
6. Memory ON answers without a matching recall event, memory ID, source, and
   score.
7. Memory ON answers by reading the fixture store directly instead of using
   the retriever.
8. Control answer changes between conditions.
9. Either condition fails to answer `4` to Q-Control.
10. Absent question produces a fabricated fact.
11. Expired memory remains retrievable.
12. Eviction has no corresponding ledger event.
13. Eviction removes an unexpired or unrelated memory.
14. Eviction modifies the official memory store or ledger.
15. The official memory store or historical ledger events are rewritten.
16. Historical prototype ledger events are presented as official sortie
    evidence.
17. Answers are not captured verbatim, or the tool-call trace is missing.
18. The two conditions use different models or different question wording.
19. The ledger is not append-only, or new events do not use the
    `e7-memory-v2` schema.
20. Answers or evidence are edited after capture.

## ABORT Conditions

ABORT rather than FAIL if:

- the harness cannot enforce the memory-OFF sandbox or deny reads outside it;
- the fixture hash does not match the declared claim SHA-256;
- the required model is unavailable;
- the harness cannot provide the tool-call trace or verbatim answers needed
  to evaluate the claim.

## Current Verdict

NOT RUN — Preflight corrections applied; awaiting Chase re-review.
No Chase GO or sortie PASS is claimed.
