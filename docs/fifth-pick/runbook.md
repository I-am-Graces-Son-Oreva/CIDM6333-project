# Fifth Pick M5 Snapshot Runbook

## Scope

M5 records the three authorized projection observations and their provenance. It does not evaluate candidates, perform T-20 conclusions, rank, finalize, or make a decision for Joseph. No M5 command performs source retrieval; callers pass the successful M4 `SourceBoard` to `SnapshotWorkflow`. M5 tests and acceptance are offline and require no API key or live request.

## Runtime Storage

Create the M2 `RunStore` with the operational root `var/fifth-pick/`. For each validated run ID, M5 writes:

```text
var/fifth-pick/runs/<run_id>/receipts.jsonl
var/fifth-pick/runs/<run_id>/snapshots/ledger.jsonl
```

Tests inject a temporary `RunStore` root. Runtime artifacts are not source fixtures and must not be committed. M4 marks built-in live boards `LIVE` and synthetic `FixtureTransport` boards `FIXTURE`; M5 rejects `UNKNOWN` origin. The snapshot ledger contains the canonical observation, evidence mode, source provenance, a structured excerpt copied from the M4 projection, and the unchanged M4 combined payload SHA-256. It does not contain the API key or raw response bodies.

## Collecting Snapshots

1. On the first usable successful M4 board observation for a run, call `SnapshotWorkflow.collect(run_id, 1, board)`. This is Snapshot 1 only if its source observation and system recording both precede that event's tipoff. Identity must resolve through the canonical registry and the exact category/direction must pass `AuthorizationGate`; unresolved or unauthorized projections are not snapshotted.
2. For each event and candidate, let `T20 = tipoff - 20 minutes`. The Snapshot 2 target is the midpoint between Snapshot 1's actual source retrieval time and T20, capped at `T20 - 60 minutes` (`tipoff - 80 minutes`). When a 60-minute separation is possible, an observation before the calculated target is rejected. When it is not possible, any distinct observation after Snapshot 1 and by the latest target can be recorded with its actual time.
3. Call `collect(run_id, 2, board)` with a fresh M4 board in the Snapshot 2 collection window. If a projection is unavailable before the latest target, the attempt is receipted and may be retried with a new legitimate board observation. At or after the latest target, call `mark_snapshot_2_missed(run_id, event_id)` for any remaining Snapshot 1 lines. The ledger and receipt use `SNAPSHOT_2_MISSED`; later attempts cannot backfill that slot.
4. Snapshot 3 targets the event-specific T-25 to T-20 window. Call `collect(run_id, 3, board)` with a fresh M4 board in that window. If a projection is unavailable from T-25 until tipoff, its attempt is receipted and another legitimate board observation may be collected before tipoff. A successful collection after T-20 but before tipoff is recorded as late with actual source retrieval and system recording times; it never substitutes a fabricated T-20 timestamp. At or after tipoff the missing observation is recorded as `PROJECTION_OBSERVATION_MISSED` and cannot be reconstructed.
5. Snapshot 3 is accepted only after Snapshot 1 and either an accepted Snapshot 2 or a recorded missed Snapshot 2. Out-of-order attempts are receipted and rejected. A duplicate `(run, slot, platform, player, category, direction, event)` returns the persisted record and adds an idempotent duplicate receipt.

`SnapshotWorkflow.read(run_id)` returns persisted snapshots; `read_missed(run_id)` returns missed-slot records. Supporting-source refreshes do not use this API and do not create projection snapshots. There is no backfill operation or fourth snapshot.

## Evidence and Stop Conditions

Every accepted observation keeps its platform, canonical player, category, projection, direction, event, source update time, system retrieval time, and snapshot number. Its provenance keeps source ID, access method, source timestamp, retrieval time, event reference, and payload hash. The structured source excerpt comes only from the accepted `SourceProjection`; it is not reconstructed from a hash or labeled as a raw payload.

If identity, authorization, source provenance, timestamps, or ledger contents are invalid, M5 fails closed. If a required slot is missed, retain the miss receipt and ledger marker; do not backfill or treat fewer observations as three. M5 does not authorize automatic finalization. Joseph remains Governance Zero.
