# ADR-2: Memory Retrieval, State, Eviction, and Retention

Status: Implemented locally — preflight corrections applied; official sortie pending re-review
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
questions and instructions. The sandbox excludes the private fixture,
the official memory store, the official ledger, Evolution 6 files, and
Evolution 6 evidence. A manifest records the sandbox contents and
whether the fixture claim appears anywhere inside it.

The memory-ON condition uses a private fixture store and ledger outside
the sandbox. The agent obtains the answer by running `ask_memory.py`,
which calls the retriever. A matching recall event must record the
memory ID, source, and score. The condition uses a retrieval threshold
of 0.30 so the control and absent questions return `Not in memory.`

The private fixture is `evolution-07/fixtures/private-claim.json`. Its
plaintext claim is not stored in this ADR, the Flight Card, source
code, tests, or historical transcripts. The fixture is the only
ordinary repository data file that contains the claim, and the
memory-OFF sandbox excludes it.

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

- `tests/test_e7_memory.py`: 7 tests passed.
- `tests/test_e7_isolation.py`: isolation, fixture, retriever,
  TP5, and historical-ledger tests added during preflight correction.

Preflight isolation evidence:

- `evolution-07/evidence/preflight-isolation.json`
- `evolution-07/evidence/preflight-tp5-isolation.json`

These preflight files are not official sortie evidence. The official
Sortie 7 memory-OFF/memory-ON comparison has not yet been performed.

## Remaining Work

- Obtain a new Chase preflight review after the corrections are committed.
- Obtain Chase GO before the official sortie.
- Run memory-OFF and memory-ON comparisons with the corrected sandboxes.
- Verify absent-question, control-question, and eviction behavior.
- Record verbatim answers and supporting evidence.
- Complete the design analysis and AI_LOG.
- Record the final Chase verdict.
