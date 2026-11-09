# ADR-2: Memory Retrieval, State, Eviction, and Retention

Status: Implemented locally — Chase NO-GO corrections pending independent re-review
Date: 2026-11-08

## Context

Evolution 7 requires a memory system that can remember,
retrieve, evict, and forget information while preserving
an auditable record of memory operations.

A memory is a claim with a source, not an unquestionable fact.
Forgetting must be an observable event.

## Decision

### 1. Memory Store

Use a local JSONL file named memory.jsonl.

Each memory record includes:
- id: unique memory identifier
- kind: type of memory
- source: where the information originated
- written: date recorded
- written_by: author
- retain_until: retention deadline
- supersedes: previous memory replaced, if applicable
- text: stored information

### 2. Memory Kinds

The initial implementation uses episodic memories for
recorded events and previous outcomes.

Future versions may distinguish semantic knowledge
from episodic records.

### 3. Retrieval

Use a local Python standard-library TF-IDF cosine
similarity retriever.

Retrieval returns the matching memory ID, source,
date, score, and text.

Retrieval supports minimum score thresholds,
top-k ranking, expiration filtering, and
supersession of outdated records.

Retrieved text is evidence, not an instruction.

### 4. Retention and Eviction

Each record has a retain_until date.

The evict command removes expired records and
writes an eviction event to memory-ledger.jsonl.

### 5. Forgetting

The forget command removes a requested memory ID
and records the reason in the event ledger.

Memory IDs must never be reused.

### 6. Source Precedence

Current authoritative project files and the
runtime ledger take precedence over older memories.

Memory must not silently override a newer source.

### 7. Ledger Schema Versions

Historical events already present in
`evolution-07/lab/memory-ledger.jsonl` were written by an earlier
local prototype. Those events use the prototype schema: a top-level
`id` and `score`, no `source`, no `effective_date`, and no `schema`
field.

The historical prototype events are retained unchanged for audit.
They must not be represented as official sortie evidence. New events
written by the current implementation include
`"schema": "e7-memory-v2"`, a `results` list whose entries contain
`id`, `source`, and `score`, and top-level `top_id`, `top_source`,
and `top_score`.

Historical events must not be rewritten or deleted to make them match
the new schema.

### 8. Preflight Isolation and Evidence

The memory-OFF condition runs in a sandbox that contains only the
questions, instructions, and generated launch and configuration files.
Enforcement is not prose: the generated
`sandbox.sb` Seatbelt profile runs under `/usr/bin/sandbox-exec` and
denies reads and writes to the repository, the private fixture
directory, and the real OpenCode data directory. The generated
`opencode.json` uses the OpenCode 1.18.20 V1 `permission` key (not the
V2 `permissions` key) to deny `read`, `glob`, `grep`, `list`, `bash`,
`task`, `skill`, `webfetch`, `websearch`, `edit`, and `todowrite`.
Every builder requires nonexistent sandbox and private targets. Every launch
script also sets `XDG_DATA_HOME` and `OPENCODE_DB` inside the sandbox and fails
closed if the data directory already exists, so neither an earlier isolated
session nor the real OpenCode log or database can be reused. Existing private
paths and ledgers are preserved and cause the builder to stop; they are never
deleted or truncated. The real data directory is denied because
its log file contains a copy of the private passphrase from an earlier
interactive session.

The memory-ON condition uses a private fixture store, ledger, and
sidecar outside the sandbox. The sidecar is denied by exact path, and
the private directory is denied by subpath. A localhost-only service
started outside the sandbox owns the private store. The sandbox
contains a thin `ask_memory.py` client that calls that service. The
agent obtains the answer through the retrieval interface, not by
reading the store. The ON profile also denies the repository, the
fixture directory, and the real OpenCode data directory. The ON
`opencode.json` allows `bash` so the client can run, while the
operating-system profile enforces the filesystem boundary. The
condition uses a retrieval threshold of 0.30 so the control and absent
questions return `Not in memory.`

Both profiles deny E7 private artifacts, not just the current
condition's private directory. The profile builder discovers existing
`/tmp/e7-*` artifact roots and always denies `/tmp/e7-artifacts`, then
denies any explicit private directory, store, ledger, sidecar, or
sibling condition path passed to the builder. The OFF profile is built
with the ON sandbox, private directory, and sidecar as denied future
paths. The ON profile is built with the OFF sandbox as a denied sibling
path. This closes the cross-condition leak where memory-OFF could read
the memory-ON private store, sidecar, service configuration, or sandbox
profile from `/tmp/e7-artifacts` or `/tmp/e7-demo-*`.

Retriever isolation during memory-OFF is lifecycle-based, not network
based. The ON launch script starts the localhost service; the OFF launch
script never starts it. Preflight records whether the ON port is
reachable while the OFF profile is active and whether the OFF launch
script contains `serve-on`. Network access is not claimed as isolated;
the OFF condition must not run while the ON service is running.

The private fixture is `~/CIDM6333-private-e7/private-claim.json`. Its
plaintext claim is not stored in this ADR, the Flight Card, source
code, tests, or historical transcripts. The fixture is the only
ordinary repository data file that contains the claim, and both
sandbox profiles exclude it. The fixture's declared source is
`~/CIDM6333-private-e7/private-claim.json#text`.

Preflight runs real negative probes under each generated profile. Each
probe attempts to read the private fixture, official store, official
ledger, Evolution 6 flight log, Evolution 6 evidence, the real OpenCode
log and database, and the repository, plus shell and Python escape
attempts. Both profiles also probe every discovered E7 private artifact
root and the exact third-review leaked paths: the
`/tmp/e7-artifacts/private` store and ledger, the
`/tmp/e7-demo-*/private` store and ledger, the sidecar, and the ON
`service.json` and `sandbox.sb`. The OFF probes also attempt to read the
ON private store, ledger, and sidecar; the ON probes also attempt to
read the private store, private ledger, and sidecar. A probe passes only
when the read is actually denied and the private claim did not appear on
standard output. A path that does not exist is recorded as absent and
may pass only when absence is explicitly allowed; a readable file never
passes. The same preflight records `same_model`, `same_question`, and
`same_generation`.

The model-call permission behavior probe timed out on this host and is
not claimed as passed. The enforcement evidence is the operating-system
sandbox denial output plus a test that the installed OpenCode binary
accepts and preserves the generated V1 `permission` configuration.

Official evidence capture uses `python3 -m src.e7_memory capture` with a
unique nonexistent output path and an OpenCode launch command containing
`--format json`. The capture preserves raw JSON events and standard error,
derives the verbatim text answer and tool-event trace, optionally copies the
private recall ledger, records relevant before/after file hashes, and writes
an artifact-hash manifest. It refuses to overwrite an existing capture path.
A synthetic event producer tests this procedure without invoking a model; that
test output is not official sortie evidence.

TP5 eviction uses a temporary copy of the store and ledger. Before and
after snapshots verify that eviction does not modify the official
memory files.

## Rejected Alternatives

### Alternative 1: Store memories only in conversation history

Rejected because conversation history may be
compacted or unavailable in a new session.

Consequence: JSONL requires explicit file management.

### Alternative 2: Use a remote vector database

Rejected because it introduces external dependencies,
configuration, and additional operational complexity.

Consequence: local retrieval may be less accurate.

### Alternative 3: Delete memories without an event ledger

Rejected because deletion would not be auditable.

Consequence: the ledger must be maintained and tested.

### Alternative 4: Keep every memory forever

Rejected because outdated information can become
misleading and retention must be enforceable.

Consequence: expiration and eviction are required.

## Evidence So Far

Local pytest results for the memory implementation:

- `tests/test_e7_memory.py`: 8 tests passed, including the structured
  `query()` result path used by the localhost service.
- `tests/test_e7_isolation.py`: 24 tests passed, including real
  sandbox-denial probes, cross-condition private-artifact denial,
  absence-aware probe handling, ON private-store and sidecar denial,
  threshold rejection, generated-config compatibility with the
  installed OpenCode binary, launch-script contents, the `serve-on`
  CLI path used by `launch.sh`, lifecycle reachability, fixture-source
  consistency, TP5, historical-ledger preservation, fail-closed fresh paths,
  and synthetic evidence capture without a model call.
- Full suite: 37 tests passed = 24 E7 isolation + 8 E7 memory + 5 E6
  context tests.

Preflight isolation evidence:

- `evolution-07/evidence/preflight-isolation.json`
- `evolution-07/evidence/preflight-tp5-isolation.json`

These preflight files are not official sortie evidence. The official
Sortie 7 memory-OFF/memory-ON comparison has not yet been performed.

## Remaining Work

- Obtain a new independent Chase preflight review after these uncommitted
  corrections receive human review and are committed.
- Obtain Chase GO before the official sortie.
- Run memory-OFF and memory-ON comparisons with the corrected sandboxes.
- Verify absent-question, control-question, and eviction behavior.
- Record verbatim answers and supporting evidence.
- Complete the design analysis and AI_LOG.
- Record the final Chase verdict.
