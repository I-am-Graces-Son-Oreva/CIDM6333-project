# ADR-2: Memory Retrieval, State, Eviction, and Retention

Status: Implemented locally — official sortie pending
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

Local pytest results:
- test_remember_and_recall: PASS
- test_eviction: PASS
- test_forget: PASS

Seven local tests passed on 2026-11-08.

The official Sortie 7 memory-OFF/memory-ON
comparison has not yet been performed.

## Remaining Work

- Confirm the official Flight Card 7 acceptance criteria.
- Obtain Chase GO before the official sortie.
- Run memory-OFF and memory-ON comparisons.
- Verify absent-question and eviction behavior.
- Record verbatim answers and supporting evidence.
- Complete the design analysis and AI_LOG.
- Record the final Chase verdict.
