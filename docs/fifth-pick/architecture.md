# Fifth Pick Architecture

## Scope

This document describes the M2 domain model, receipts, and run storage only. Later milestone artifacts are listed as reserved and are not implemented by M2.

M2 provides typed vocabulary and an append-only evidence store. It does not provide source retrieval, identity resolution, authorization, snapshot scheduling, methodology, ranking, T-20 review, finalization, approval, or result grading.

## Module Map

| Module | M2 Responsibility |
|---|---|
| `src/fifth_pick/models.py` | Closed enums and typed dataclasses for observations, candidates, snapshots, provenance, evidence, decisions, results, and reason codes. |
| `src/fifth_pick/errors.py` | Typed validation, receipt, storage, unsafe-run-id, and receipt-conflict errors. |
| `src/fifth_pick/receipts.py` | Receipt schema and centralized redaction. |
| `src/fifth_pick/storage.py` | Injected-root run layout, atomic receipt writes, and event-key idempotency. |

M2 modules are standard-library only. They do not import network libraries, read environment variables, log, or write to `var/fifth-pick/`.

## Typed Vocabulary

Closed enums:

- `Platform`: `PRIZEPICKS`, `UNDERDOG`.
- `Category`: `POINTS`, `ASSISTS`, `REBOUNDS`, `PRA`, `REBOUNDS_ASSISTS`, `THREE_POINT_ATTEMPTS`.
- `Direction`: `HIGHER`, `LOWER`.
- `DecisionAction`: `APPROVE`, `REJECT`, `MODIFY`.
- `ResultStatus`: `HIT`, `MISS`, `PUSH`, `VOID`, `DNP`, `RESULT UNAVAILABLE`.
- `ReasonCode`: the frozen fail-closed vocabulary plus result and snapshot vocabulary.

`LIVE_MVP_CATEGORIES` contains only `POINTS`, `ASSISTS`, `REBOUNDS`, `PRA`, and `REBOUNDS_ASSISTS`. `THREE_POINT_ATTEMPTS` remains vocabulary-only and is not a live MVP category.

`DNP` and `VOID` are distinct from `MISS`. `RESULT UNAVAILABLE` is available when settlement is not trustworthy. M2 records vocabulary only; it does not adjudicate results.

Typed dataclasses:

- `Observation`: platform-specific projection with player, category, direction, event, source update time, retrieval time, snapshot number, source, and optional multiplier.
- `Candidate`: canonical player joined to platform, category, direction, projection, and event.
- `Snapshot`: snapshot number bound to a matching observation.
- `Provenance`: source, retrieval time, source timestamp, access method, stable reference, and payload hash.
- `Evidence`: claim, required provenance, and optional excerpt.
- `Decision`: explicit action, run ID, timestamp, slate version, and optional note.
- `Result`: result status, subject, source, recorded time, optional reason code, and optional provenance.

Validation is limited to typed required fields, non-empty text, finite numeric projections, snapshot numbers `1` through `3`, matching snapshot and observation numbers, positive slate versions, and closed enum membership. It does not implement later-milestone policy.

### Reason Codes

```text
PLAYER_IDENTITY_UNRESOLVED
CATEGORY_NOT_AUTHORIZED
PROJECTION_UNAVAILABLE
PROJECTION_OBSERVATION_MISSED
AVAILABILITY_UNRESOLVED
ROLE_OR_MINUTES_UNRESOLVED
T20_CHECK_UNAVAILABLE
SOURCE_CONFLICT_UNRESOLVED
INSUFFICIENT_SUPPORTING_EVIDENCE
RESULT UNAVAILABLE
SNAPSHOT_2_MISSED
```

The vocabulary is closed. Unknown values fail construction.

## Receipt Schema

Receipts are JSON Lines. Each line has the same fields:

```json
{"event":"BOARD_RETRIEVED","event_key":"board-retrieved-1","reason":null,"result":"OK","run_id":"run-20261115","source":"the-odds-api:us_dfs","subject":"nba:2026-11-15:lal-dal","timestamp":"2026-11-15T17:00:00+00:00"}
```

| Field | Meaning |
|---|---|
| `timestamp` | Caller-supplied receipt timestamp. |
| `event` | Observable event name, such as `BOARD_RETRIEVED`. |
| `result` | Observed result or status for the event. |
| `subject` | Entity acted on, such as a run, game, or candidate. |
| `source` | Source reference for the observation. |
| `reason` | Reason code or status, or `null` when no reason applies. |
| `run_id` | Run identity paired with the event key. |
| `event_key` | Stable idempotency key within the run. |

### Event-Key Extension

`event_key` is the only M2 schema extension beyond the plan's timestamp, event, result, subject, source, reason, and run ID list. It is required so "the same run/event key" is deterministic rather than inferred from event names, ordering, or timestamps. The idempotency pair is `(run_id, event_key)`.

## Run Layout

Storage receives an injected root. M2 writes only this layout:

```text
<injected-root>/
└── runs/
    └── <run_id>/
        └── receipts.jsonl
```

Run IDs must match `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. The resolved run path must remain under the injected root; traversal, separators, absolute paths, and symlink escapes fail closed.

The following plan artifacts are reserved and are not created or implemented in M2:

```text
run.json
snapshots/
evidence/
candidates.json
final.json
audit.json
```

## Atomic and Idempotent Receipts

`RunStore.append_receipt()` reads the current `receipts.jsonl`, compares the new receipt with existing receipts, and writes only when the event key is new.

- Same `(run_id, event_key)` with equivalent content returns the existing data, reports `created=False`, and appends nothing.
- Equivalence excludes `timestamp`, so a retry timestamp does not defeat idempotency.
- Same `(run_id, event_key)` with different content raises `ReceiptConflictError` and changes no bytes.
- Different event keys append a new line.
- Malformed JSONL, blank lines, non-object lines, unsupported field values, and invalid UTF-8 fail closed with `StorageError`.

Writes use a temporary file in the destination directory followed by `os.replace`. An injected write or replace failure preserves the old bytes and removes the temporary file. Cross-process concurrency is not claimed or tested in M2.

## Redaction

Redaction is centralized in `receipts.py` as a pure operation.

- Callers supply secret strings explicitly. M2 never reads `THE_ODDS_API_KEY` or any other environment variable.
- Exact supplied secrets are replaced with the single fixed marker `[REDACTED]`.
- Sensitive URL query values are redacted even when the caller does not list the value as a secret. Sensitive names include `apiKey`, `api_key`, `api-key`, `key`, `token`, `access_token`, `secret`, `client_secret`, `password`, `auth`, `authorization`, `sig`, and `signature`, matched case-insensitively.
- Non-sensitive query parameters and URL paths are preserved.
- `Receipt.redacted()` returns a new receipt and leaves the original values unchanged.

## Reserved Later Milestones

- M3: configuration, canonical registry, identity, and authorization.
- M4: source adapter, live client, quota, and source-level redaction.
- M5: snapshot collection and missed-snapshot recording.
- M6: evidence, methodology, confidence, and ranking.
- M7: T-20 review.
- M8: finalization, ceilings, and Joseph approval.
- M9: result grading.
- M10: harness hardening and hooks.
- M11: closeout, demo, and assurance.

Those milestones consume the M2 vocabulary and storage but are not implemented here.
