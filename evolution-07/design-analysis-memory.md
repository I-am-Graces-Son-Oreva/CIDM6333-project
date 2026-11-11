# Evolution 7 Design Analysis — Explicit Auditable Memory vs. Hidden Conversation Memory

## Question

For the Graduate Application Identity-Assurance and Triage System, should persistent memory rely on hidden conversation history, or should memory be an explicit system with retrieval, provenance, retention, and deletion rules?

## Option A — Hidden Conversation Memory

A model may appear to remember information from earlier interactions without exposing a clear application-level memory record.

### Advantages

- Simple user experience.
- Less application code.
- Useful for informal continuity.

### Problems

- Difficult to prove exactly why something was recalled.
- Provenance may not be visible.
- Retention and expiration are difficult to audit.
- Deletion behavior may be difficult to verify.
- It is harder to distinguish remembered evidence from model inference.

## Option B — Explicit Auditable Memory

The application stores memory as explicit records with stable IDs, source information, retention metadata, and retrieval scores. Retrieval happens through a bounded service rather than by silently placing all historical information into model context.

### Advantages

- Recall can be tied to a specific memory ID and source.
- Retrieval decisions can be logged.
- Thresholds can reject weak matches.
- Expiration and eviction can be tested.
- Deleted or expired memories can be prevented from returning.
- The system can distinguish “not in memory” from unsupported guessing.

### Costs

- More implementation work.
- Requires a memory store and ledger.
- Requires retention and eviction logic.
- Requires isolation testing to prove that the model is not receiving the answer through another path.

## Nine Components

### 1. Goal

Provide useful persistent recall without turning memory into an invisible source of authority.

### 2. Memory Store

Use explicit JSONL memory records rather than relying on hidden conversation history.

### 3. Identity

Each memory receives a stable ID. IDs are not silently reused after deletion or eviction.

### 4. Provenance

A recalled memory identifies the source from which the stored claim originated.

### 5. Retrieval

The retriever ranks candidate memories and returns bounded structured results.

### 6. Threshold

Low-confidence retrieval is rejected instead of forcing an answer from a weak match.

### 7. Retention

Memory records include retention conditions. Expired information must become unavailable.

### 8. Audit Evidence

Capture recall and eviction events in an append-only ledger so later review can determine what the memory system did.

### 9. Isolation

Memory-OFF and Memory-ON tests must prevent alternate paths from leaking the private fixture into the answering model.

## Evidence From E7

The automated E7 tests exercised retrieval, threshold rejection, stable IDs, expiration, eviction, isolation boundaries, fixture consistency, and evidence capture.

The official model-based sortie did not complete. After independent Chase GO, the required Big Pickle answering model returned a free-usage-limit error under the approved sortie configuration. I recorded this as an ABORT rather than weakening the approved isolation boundary or claiming unsupported TP results.

## Judgment Loop

**Observe:** Persistent memory can improve continuity, but an unexplained recall is difficult to distinguish from leaked context, inference, or stale information.

**Orient:** Graduate application triage can involve information whose source, age, and continued validity matter. A remembered statement should therefore be inspectable and removable.

**Decide:** Use explicit auditable memory with stable IDs, provenance, retrieval thresholds, retention metadata, eviction, and a recall ledger.

**Act:** Keep memory behind a bounded retrieval service, test Memory-OFF against Memory-ON, and fail closed when the required isolation or evidence conditions cannot be maintained.

## Final Judgment

Use explicit auditable memory rather than hidden conversation memory for the graduate-triage system. Memory should have a receipt: what was recalled, where it came from, why it was eligible for retrieval, and whether it is still within its retention period.

A memory feature is not trustworthy merely because it recalls the correct answer. The system must also demonstrate provenance, bounded retrieval, enforceable retention, and isolation from alternate information paths.
