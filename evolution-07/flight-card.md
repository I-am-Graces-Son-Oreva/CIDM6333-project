# Evolution 7 — Flight Card 7

Status: DRAFT — Chase NO-GO corrections implemented; awaiting independent re-review
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

Source: `~/CIDM6333-private-e7/private-claim.json#text`

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

A localhost-only service, started outside the sandbox, owns the private store
and ledger. The ON sandbox contains a thin `ask_memory.py` client that calls
that service. The service writes recall events to the private ledger. The
private directory and the sidecar file are denied by the OS sandbox profile.

The memory-ON wrapper uses a retrieval threshold of 0.30. The recall question
scores above 0.30; the control and absent questions score below it and return
`Not in memory.` The verifier requires both `top_score` and the first result
score to be at least 0.30.

Historical events in the official ledger use the earlier prototype schema and
must not be represented as official sortie evidence.

## Operational Procedures

Allocate a unique run root. `mktemp -d` creates a new directory and fails
rather than selecting a previous run. Builders also reject any existing
sandbox, private directory, or sidecar target.

```
E7_RUN_ROOT=$(mktemp -d /tmp/e7-sortie.XXXXXX)
```

Build the memory-OFF sandbox:

```
python3 -m src.e7_memory build-off \
  --sandbox "$E7_RUN_ROOT/off" \
  --manifest "$E7_RUN_ROOT/off-manifest.json" \
  --deny "$E7_RUN_ROOT/on" \
  --deny "$E7_RUN_ROOT/on-private" \
  --deny "$E7_RUN_ROOT/on.private.json"
```

The builder always denies `/tmp/e7-artifacts` and any existing `/tmp/e7-*`
artifact root it discovers. The explicit `--deny` arguments cover ON paths that
do not exist at OFF build time.

Build the memory-ON sandbox and private fixture store and ledger:

```
python3 -m src.e7_memory build-on \
  --sandbox "$E7_RUN_ROOT/on" \
  --private "$E7_RUN_ROOT/on-private" \
  --manifest "$E7_RUN_ROOT/on-manifest.json" \
  --deny "$E7_RUN_ROOT/off"
```

The ON profile denies its own private directory, store, ledger, and sidecar,
plus the OFF sandbox and the discovered E7 artifact roots. The builder never
deletes an existing ledger: an existing private path is a hard error.

Each build writes `opencode.json` using the OpenCode 1.18.20 V1
`permission` key, `sandbox.sb` using the Seatbelt profile, and `launch.sh`.
The launch script sets `XDG_DATA_HOME` and `OPENCODE_DB` inside the sandbox,
refuses to launch if that data directory already exists, starts the ON service
when needed, and runs OpenCode under `/usr/bin/sandbox-exec`.

### Reproducible evidence capture

For each condition and test point, use a distinct output directory that does
not already exist. The capture command refuses overwrite, invokes the launch
script with OpenCode's raw JSON event format, preserves standard error, derives
the verbatim text answer and tool-event trace, copies the recall ledger when
provided, and records SHA-256 hashes before and after the run.

Memory-OFF example:

```
python3 -m src.e7_memory capture \
  --output "$E7_RUN_ROOT/evidence/tp1-off" \
  --condition memory-off \
  --test-point TP1 \
  --hash evolution-07/lab/memory.jsonl \
  --hash evolution-07/lab/memory-ledger.jsonl \
  -- "$E7_RUN_ROOT/off/launch.sh" --format json \
  "What is the E7 private fixture passphrase?"
```

Memory-ON example:

```
python3 -m src.e7_memory capture \
  --output "$E7_RUN_ROOT/evidence/tp2-on" \
  --condition memory-on \
  --test-point TP2 \
  --recall-ledger "$E7_RUN_ROOT/on-private/fixture-memory-ledger.jsonl" \
  --hash "$E7_RUN_ROOT/on-private/fixture-memory.jsonl" \
  --hash "$E7_RUN_ROOT/on-private/fixture-memory-ledger.jsonl" \
  --hash evolution-07/lab/memory.jsonl \
  --hash evolution-07/lab/memory-ledger.jsonl \
  -- "$E7_RUN_ROOT/on/launch.sh" --format json \
  "Use python3 ask_memory.py to answer exactly: What is the E7 private fixture passphrase?"
```

Repeat with new output directories for TP3-OFF, TP3-ON, and TP4.
Each capture directory contains `opencode-events.jsonl`,
`opencode-stderr.txt`, `verbatim-answer.txt`, `tool-trace.jsonl`, optional
`recall-events.jsonl`, and `capture-manifest.json`. TP5 continues to use its
isolated temporary store procedure, whose evidence records the temporary
store diff and official-file hashes before and after.

The capture implementation is validated with a synthetic JSON-event producer
that makes no OpenCode model call. This validation is not official sortie
evidence.

Run the retriever for a question in the memory-ON sandbox:

```
python3 -m src.e7_memory ask \
  --sandbox /tmp/e7-on \
  --question "What is the E7 private fixture passphrase?"
```

The `ask` command starts the localhost service, runs the thin client under the
generated sandbox profile, and shuts the service down.

Verify the matching recall event:

```
python3 -m src.e7_memory verify-on \
  --ledger /tmp/e7-on-private/fixture-memory-ledger.jsonl
```

Run the real denial probes:

```
python3 -m src.e7_memory probe --sandbox /tmp/e7-off --condition off
python3 -m src.e7_memory probe --sandbox /tmp/e7-on --condition on
```

Each probe must report `denied: true` and `leaked: false` for every protected
target, and `returncode: 0` for the allowed question read. A target that does
not exist may report `absent: true` only when `allow_absent: true`; a readable
file never passes. The probes include the exact third-review leaked paths under
`/tmp/e7-artifacts` and `/tmp/e7-demo-*`, plus the sibling condition's private
directory, store, ledger, sidecar, service configuration, and sandbox profile.
The `probe` command exits nonzero if any expected denial did not occur or any
probe leaked the private claim.

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

1. Run `$E7_RUN_ROOT/off/launch.sh` through the capture command from a fresh
   shell. The script changes to the
   OFF sandbox, uses a fresh OpenCode data directory, and runs OpenCode under
   the Seatbelt profile.
2. The generated config denies Read, Glob, Grep, List, Bash, Task, and the
   other file-reading tools. The OS profile denies the repository, the
   fixture directory, and the real OpenCode data directory.
3. Provide the three questions in the prompt. The agent does not need to read
   files.
4. Capture the tool-call trace and the verbatim answers.

Memory-ON session:

1. Run `$E7_RUN_ROOT/on/launch.sh` through the capture command from a fresh
   shell. The script starts the
   localhost service outside the sandbox, changes to the ON sandbox, uses a
   fresh OpenCode data directory, and runs OpenCode under the Seatbelt profile.
2. The generated config denies Read, Glob, Grep, List, Task, and the other
   file-reading tools, but allows Bash so the thin client can run. The OS
   profile denies the repository, the fixture directory, the private
   store/ledger/sidecar, and the real OpenCode data directory.
3. Provide the exact command `python3 ask_memory.py "<question>"` in the
   prompt. The agent must obtain the answer through `ask_memory.py` or the
   same localhost retrieval interface, not by reading the store.
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
- the OFF isolation manifest reports `claim_present_in_sandbox: false`;
- every OFF denial probe reports `denied: true` or an explicitly allowed
  `absent: true` for the protected targets;
- the OFF profile denies the ON private store, ledger, sidecar, service
  configuration, and sandbox profile, including the exact third-review paths
  under `/tmp/e7-artifacts` and `/tmp/e7-demo-*`;
- the ON service is not running and its port is not reachable while the OFF
  profile is active.

FAIL if the answer contains the passphrase or a correct paraphrase of it, or
if the trace shows access to an excluded source.

### TP2 — Memory ON

Ask Q-Recall in the ON sandbox and obtain the answer through the retriever
interface, normally `ask_memory.py`.

PASS only if all of the following hold:

- the verbatim answer contains the fixture passphrase;
- the answer cites memory ID `m-9001` and source
  `~/CIDM6333-private-e7/private-claim.json#text`;
- the private ledger contains a recall event for the exact Q-Recall wording
  with `schema: e7-memory-v2`, `top_id: m-9001`, the same `top_source`, and
  `top_score` at least 0.30;
- the first result in that event also has a score of at least 0.30;
- the tool trace shows the answer was obtained through the thin client or the
  localhost retrieval interface, not by reading the fixture store directly;
- the ON denial probes report `denied: true` or an explicitly allowed
  `absent: true` for the private store, private ledger, private sidecar,
  repository, real OpenCode data directory, and sibling E7 artifact roots.

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

Ask Q-Absent in the ON sandbox through the retriever interface, normally
`ask_memory.py`.

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
- Same model (`OpenCode Big Pickle`), exact question wording, and same
  generation in both conditions.
- Memory-OFF sandbox contains only the questions, instructions, and generated
  launch/config files.
- Memory-OFF sandbox excludes the fixture directory, official store, official
  ledger, E6 files, E6 evidence, the real OpenCode data directory, and every
  discovered E7 private artifact root, including `/tmp/e7-artifacts` and
  `/tmp/e7-demo-*`.
- Memory-OFF also denies the ON private directory, store, ledger, sidecar,
  service configuration, and sandbox profile, even when those paths do not yet
  exist.
- Memory-OFF is not run while the ON localhost service is running. Network
  isolation is not claimed; isolation is enforced by filesystem denial and by
  the OFF launch script never starting `serve-on`.
- The generated `opencode.json` uses the OpenCode 1.18.20 V1 `permission` key.
- Each launch script uses a fresh `XDG_DATA_HOME` and `OPENCODE_DB` inside the
  sandbox.
- The OS `sandbox-exec` profile, not prose instructions, enforces the
  filesystem boundary.
- Memory-ON sandbox contains only the questions, instructions, the thin
  `ask_memory.py` client, and generated launch/config files. The private
  fixture store, ledger, and sidecar live outside it and are denied by the OS
  profile.
- The ON agent may run Bash, but the OS profile denies the repository, the
  fixture directory, the private store/ledger/sidecar, and the real OpenCode
  data directory.
- No previous answers or transcripts supplied to either session.
- Record answers verbatim and capture the tool-call trace.
- The private fixture is not in ordinary source files or prior transcripts.
- The model-call permission behavior probe is not claimed as passed; the
  enforcement evidence is the OS denial output and the generated-config
  compatibility test.

## Evidence to Capture

- `evolution-07/evidence/preflight-isolation.json`
- `evolution-07/evidence/preflight-tp5-isolation.json`
- `evolution-07/evidence/tp5-isolation.json`
- OFF sandbox manifest, `opencode.json`, `sandbox.sb`, `launch.sh`, and
  tool-call trace
- OFF denial probe output
- OFF verbatim answer to Q-Recall
- OFF verbatim answer to Q-Control
- ON sandbox manifest, `opencode.json`, `sandbox.sb`, `launch.sh`, and
  tool-call trace
- ON denial probe output for the private store, ledger, and sidecar
- ON service log
- ON verbatim answer to Q-Recall
- ON verbatim answer to Q-Control
- ON verbatim answer to Q-Absent
- ON retriever output for Q-Recall
- Matching recall event from the private ledger
- Store and ledger before and after snapshots for TP5
- Fresh-session data-directory path showing the real OpenCode log/DB was not
  reused
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
21. Isolation is enforced only by prose instructions; the real denial probes
    are missing or any expected denial did not occur.
22. Either condition reuses the real OpenCode data directory or its log/DB.
23. The generated config uses V2 `permissions` instead of the V1 `permission`
    key, or the installed OpenCode binary rejects the generated config.
24. The ON sandbox can read the private store, private ledger, or sidecar.
25. The recall event has `top_score` below 0.30 or a first-result score below
    0.30.

## ABORT Conditions

ABORT rather than FAIL if:

- the harness cannot enforce the memory-OFF sandbox or deny reads outside it;
- `/usr/bin/sandbox-exec` is unavailable or any required denial probe fails;
- the installed OpenCode binary rejects the generated V1 `permission` config;
- the real OpenCode data directory cannot be excluded from a condition;
- the fixture hash does not match the declared claim SHA-256;
- the required model is unavailable;
- the harness cannot provide the tool-call trace or verbatim answers needed
  to evaluate the claim.

## Current Verdict

NOT RUN — Preflight corrections applied; awaiting Chase re-review.
No Chase GO or sortie PASS is claimed.

## Independent Chase Preflight Verdict — 2026-11-09

Verdict: CHASE GO

Reviewed commit: ac217fa0c290aee4d908078d874ecb26b4014394

Independent Chase re-review confirmed:
- All three previous NO-GO blockers corrected.
- 37 automated tests passed.
- Fresh sandbox and OpenCode data isolation enforced.
- Existing private ledgers preserved.
- JSON evidence capture and overwrite protection verified.
- Real macOS sandbox denial verified.
- Fixture hashes, retrieval scores, and TP5 isolation verified.
- All 25 falsifiers and 7 ABORT conditions reviewed.

Decision: GO for the official Evolution 7 sortie.

This is preflight approval only, not a sortie PASS.
