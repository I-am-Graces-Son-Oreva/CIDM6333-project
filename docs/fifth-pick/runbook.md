# Fifth Pick M5 Snapshot and M8 Finalization Runbook

## Scope

M5 records the three authorized projection observations and their provenance. It does not evaluate candidates, perform T-20 conclusions, rank, finalize, or make a decision for Joseph. No M5 command performs source retrieval; callers pass the successful M4 `SourceBoard` to `SnapshotWorkflow`. M5 tests and acceptance are offline and require no API key or live request.

## Runtime Storage

Production uses `application_run_store()`, whose application-owned root is the repository's `var/fifth-pick/`. M5 writes each validated run under that root:

```text
var/fifth-pick/runs/<run_id>/receipts.jsonl
var/fifth-pick/runs/<run_id>/snapshots/ledger.jsonl
```

M5 tests inject a temporary `RunStore` root. Runtime artifacts are not source fixtures and must not be committed. M4 marks built-in live boards `LIVE` and synthetic `FixtureTransport` boards `FIXTURE`; M5 rejects `UNKNOWN` origin. The snapshot ledger contains the canonical observation, evidence mode, source provenance, a structured excerpt copied from the M4 projection, and the unchanged M4 combined payload SHA-256. It does not contain the API key or raw response bodies.

## Collecting Snapshots

1. On the first usable successful M4 board observation for a run, call `SnapshotWorkflow.collect(run_id, 1, board)`. This is Snapshot 1 only if its source observation and system recording both precede that event's tipoff. Identity must resolve through the canonical registry and the exact category/direction must pass `AuthorizationGate`; unresolved or unauthorized projections are not snapshotted.
2. For each event and candidate, let `T20 = tipoff - 20 minutes`. The Snapshot 2 target is the midpoint between Snapshot 1's actual source retrieval time and T20, capped at `T20 - 60 minutes` (`tipoff - 80 minutes`). When a 60-minute separation is possible, an observation before the calculated target is rejected. When it is not possible, any distinct observation after Snapshot 1 and by the latest target can be recorded with its actual time.
3. Call `collect(run_id, 2, board)` with a fresh M4 board in the Snapshot 2 collection window. If a projection is unavailable before the latest target, the attempt is receipted and may be retried with a new legitimate board observation. At or after the latest target, call `mark_snapshot_2_missed(run_id, event_id)` for any remaining Snapshot 1 lines. The ledger and receipt use `SNAPSHOT_2_MISSED`; later attempts cannot backfill that slot.
4. Snapshot 3 targets the event-specific T-25 to T-20 window. Call `collect(run_id, 3, board)` with a fresh M4 board in that window. If a projection is unavailable from T-25 until tipoff, its attempt is receipted and another legitimate board observation may be collected before tipoff. A successful collection after T-20 but before tipoff is recorded as late with actual source retrieval and system recording times; it never substitutes a fabricated T-20 timestamp. At or after tipoff the missing observation is recorded as `PROJECTION_OBSERVATION_MISSED` and cannot be reconstructed.
5. Snapshot 3 is accepted only after Snapshot 1 and either an accepted Snapshot 2 or a recorded missed Snapshot 2. Out-of-order attempts are receipted and rejected. A duplicate `(run, slot, platform, player, category, direction, event)` returns the persisted record and adds an idempotent duplicate receipt.

`SnapshotWorkflow.read(run_id)` returns persisted snapshots; `read_missed(run_id)` returns missed-slot records. Both use the shared M5 ledger decoder. Supporting-source refreshes do not use this API and do not create projection snapshots. There is no backfill operation or fourth snapshot.

## Evidence and Stop Conditions

Every accepted observation keeps its platform, canonical player, category, projection, direction, event, source update time, system retrieval time, and snapshot number. Its provenance keeps source ID, access method, source timestamp, retrieval time, event reference, and payload hash. The structured source excerpt comes only from the accepted `SourceProjection`; it is not reconstructed from a hash or labeled as a raw payload. Each accepted snapshot and missed marker has its existing M5 receipt in the same run store.

M6 LIVE validation resolves `snapshot_run_id` under the application-owned root via `read_application_snapshot_ledger()`; callers cannot provide a `RunStore`, workflow, or reader to choose the authoritative LIVE source. It reuses the M5 ledger decoder/order validator and requires the corresponding accepted/missed receipts and exact record/provenance equality. Fixture cases remain explicitly offline and do not use this LIVE path.

The frozen design requires recorded source provenance, payload hashes, and receipts; it does not require cryptographic signatures or tamper-proof storage. The current boundary does not defend against an actor with direct write access to the application data directory. Filesystem access controls or cryptographically authenticated manifests are future hardening if Joseph expands that threat model, not part of M6.

If identity, authorization, source provenance, timestamps, or ledger contents are invalid, M5 fails closed. If a required slot is missed, retain the miss receipt and ledger marker; do not backfill or treat fewer observations as three. M5 does not authorize automatic finalization. Joseph remains Governance Zero.

## M8 Finalization and Joseph Approval

`SnapshotWorkflow.collect()` records each validated M4 event board and receipt. The first board, bound to the run's start timestamp and payload hash, pins the slate date in `America/Chicago`. M8 counts unique event IDs from that board whose commencement date matches the pinned Chicago date. Later board observations do not change the slate boundary. A missing or unverifiable run manifest blocks finalization.

LIVE finalization requires `application_run_store()` for the M4 manifest, M5 ledger, M7 reviews, and resulting final artifacts. Offline finalization may use an injected store only when the M4 run and all supplied M6/M7 evidence are explicitly `FIXTURE`; M4 boards or candidate/review records that mix LIVE and FIXTURE fail closed. Fixture records remain offline evidence and are not a path to authorize a LIVE decision.

`finalize_slate()` accepts M6 `CandidateCase` records and prior/current M7 case pairs; callers cannot supply a game count, slate classification, ranked result, or review result. It reproduces M6 ranking internally, validates M7 review records against their receipts and the supplied candidate audits, and records exclusions in `audit.json`. The ceiling pool is frozen from the M6 ranking before M7 removals: zero games recommends exactly `NO ENTRY RECOMMENDED TODAY.`, one through four games use HALF with a maximum of four, and five or more use FULL with a maximum of five. M7 removals, duplicate players, or fewer qualified candidates leave slots empty; M8 never promotes a replacement from below the frozen pool.

M8 writes a compact `final.json`, detailed `audit.json`, and a proposal receipt. A proposal, including a no-entry recommendation, remains `AWAITING_JOSEPH`; it is not Joseph's official final state. Use `fifth-pick decide --run-id RUN_ID` to review the displayed proposal and enter exactly `APPROVE`, `REJECT`, or `MODIFY`. REJECT requires a reason. MODIFY accepts only candidate keys already displayed, records a new slate version, and requires a later explicit decision. Modifying an empty no-entry proposal preserves `NO ENTRY RECOMMENDED TODAY.` and a `NO_ENTRY` proposal receipt so Joseph can make the next decision. Only the interactive `decide` flow can write a Joseph-attributed state; lower-level mutation is internal. The application receipt is persisted before an APPROVE or REJECT state is written. No action logs in to a platform, submits selections, wagers, or moves money.

M7 review records are required only when at least one in-slate candidate is in the frozen M6 ceiling pool. A malformed, unreadable, or receipt-invalid M7 ledger blocks such a candidate and records the reason in `audit.json` and `receipts.jsonl`. If there are no games or no ranked candidate requiring T-20 review, M8 does not require an M7 ledger to preserve the no-entry outcome.

M8 acceptance uses offline fixtures. Do not make a live API request for implementation or review, and do not begin M9 result grading until the independent M8 reviewer returns PASS and Joseph has reviewed the work.

## M9 Result Settlement and Grading

M9 records a settlement only for a `candidate_key` in a receipt-verified `APPROVED_BY_JOSEPH` final state. `AWAITING_JOSEPH`, MODIFY awaiting re-approval, REJECTED, BLOCKED, and NO ENTRY states cannot be graded. The result record retains the approved slate version and exact selection entry; the associated M8 audit remains the source for its T-20 projection and review reference.

Use `fifth-pick result record --run-id RUN_ID --selection SELECTION_ID` with the candidate key displayed in `official_final`. M9 accepts an already-classified M2 `ResultStatus`; it does not retrieve player results or calculate HIT/MISS from a numeric statistic. Determinate outcomes require selection-specific provenance, a minimal source excerpt, and explicit human confirmation that the excerpt itself supports the displayed player, platform, category/direction/line, event, and entered outcome. The confirmation prompt names each value. A YES is an operator attestation, not independent source authentication. M9 computes SHA-256 from the exact stored excerpt; the source reference and digest remain in M2 provenance. A digest proves excerpt integrity only, not external-source authenticity. Deterministic results use the explicit `synthetic-fixture` source and access method and are marked as fixtures.

M9 writes result records to `results.json` and a `RESULT_RECORDED` event to `receipts.jsonl`. DNP, VOID, and PUSH remain distinct and are never remapped to MISS. Do not use team scores as player results or invent platform PUSH/VOID/stat-correction behavior. If no trustworthy settlement exists, record `RESULT UNAVAILABLE` with `RESULT_UNAVAILABLE`; do not infer HIT or MISS. Conflicting duplicate results fail closed; no correction/overwrite process is defined here.

M9 does not fetch results automatically. The plan supports a legitimately available platform-settled result, manual entry with provenance and receipt, or deterministic fixture data. For `RESULT UNAVAILABLE`, evidence may be absent; optional lookup-attempt evidence is retained only with its excerpt/hash and explicit confirmation that it concerns the exact approved player, platform, category/direction/line, and event. That confirmation does not establish a settlement outcome. Missing or unconfirmed settlement evidence remains `RESULT UNAVAILABLE`. M10 must not begin until M9 tests pass and the independent read-only M9 reviewer returns PASS.

## M9 Result Recording

M9 records outcomes only for a selection in a receipt-verified `APPROVED_BY_JOSEPH` final slate. Use the exact `candidate_key` from `approval.official_final`; a display name, proposed selection, rejected slate, or MODIFY awaiting re-approval is not sufficient. The result record retains the M8 slate version and approved selection details, with a reference to its M7 T-20 audit.

Use the existing `fifth-pick result record --run-id RUN_ID --selection SELECTION_ID` command to record an already-classified settlement status. M9 does not retrieve player results. A platform-settled result may be recorded only when legitimately available; manual entries require source provenance, an excerpt/hash match, explicit confirmation, and a receipt. `results.json` stores the excerpt alongside the M2 provenance reference and digest; `RESULT_RECORDED` binds the digest and confirmation. Deterministic fixture results remain explicitly marked as fixtures. A digest is not proof that an external source is authentic.

Accepted statuses use M2's closed `ResultStatus` vocabulary. `DNP` and `VOID` are not `MISS`; do not remap PUSH, VOID, DNP, or stat corrections using an invented rule. Do not treat team scores as player results. If the result, source, or documented settlement rule cannot be trusted, record `RESULT UNAVAILABLE` with `RESULT_UNAVAILABLE`; never claim HIT or MISS without trustworthy evidence.

M9 tests use deterministic offline fixtures and manual typed results only. No player-result source is fetched automatically, no paid or unofficial provider is added, and no M10 work begins until M9's independent read-only reviewer returns PASS.
