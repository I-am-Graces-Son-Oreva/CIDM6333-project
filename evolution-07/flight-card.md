# Evolution 7 — Flight Card 7

Status: DRAFT — Awaiting Chase GO
Date: 2026-11-08

## Mission

Demonstrate that a local memory system can retrieve
a sourced claim when memory is enabled, avoid
unsupported answers when memory is disabled,
and remove expired information with an audit trail.

## Prerequisites

- [ ] Sortie 6 PASS evidence verified
- [ ] ADR-2 committed
- [ ] Git working tree clean
- [ ] Chase GO recorded before official sortie

## Memory Store

Store: evolution-07/lab/memory.jsonl
Ledger: evolution-07/lab/memory-ledger.jsonl
Retriever: Local TF-IDF cosine similarity
Program: evolution-07/lab/recall.py

## Test Questions

Q-Recall:
What was the Evolution 6 final Chase verdict
after corrective Session B2?

Q-Control:
What is 2 + 2?

Q-Absent:
What is the secret launch code for Project Orion?

## Test Points

### TP1 — Memory OFF

Run Q-Recall in a fresh session without memory access.

Expected:
The agent cannot establish the specific verdict
from memory and does not invent an answer.

### TP2 — Memory ON

Run Q-Recall with the memory retriever available.

Expected:
The answer is PASS after corrective Session B2.
The response traces to memory ID m-0001 and its source.

### TP3 — Control Question

Ask Q-Control with memory OFF and ON.

Expected:
Both answers are 4.

### TP4 — Absent Question

Ask Q-Absent with memory ON.

Expected:
Not in memory. No fabricated launch code.

### TP5 — Eviction

Create an expired test memory, record its ID,
evict it, and repeat its recall question.

Expected:
An eviction event appears in the ledger,
the record is absent from the store,
and recall returns Not in memory.

## Isolation Requirements

- Fresh sessions for memory OFF and ON.
- Same model and question wording.
- Deny unrelated tools.
- No previous answers supplied to test sessions.
- Record answers verbatim.

## Evidence to Capture

- Memory OFF answer
- Memory ON answer and retrieved record ID
- Control answers in both conditions
- Absent-question answer
- Store before and after eviction
- Eviction ledger event
- Retrieval scores
- Chase verdict and any falsifiers

## Falsifiers

- Memory OFF reveals the hidden memory claim.
- Memory ON fails to retrieve the correct record.
- Memory ON gives an unsupported answer.
- Control answer changes between conditions.
- Absent question produces a fabricated fact.
- Expired memory remains retrievable.
- Eviction has no corresponding ledger event.

## Current Verdict

NOT RUN — Awaiting preflight review and Chase GO.
