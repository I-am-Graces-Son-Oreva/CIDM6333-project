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

## Product CLI fixture workflow

Use a fresh run ID and three explicitly selected fixture directories. Run each command
separately. Use the exact candidate key returned by `final` for settlement.

```sh
fifth-pick health
fifth-pick analyze --run-id RUN_ID --snapshot 1 --fixture SNAPSHOT_1_DIRECTORY
fifth-pick analyze --run-id RUN_ID --snapshot 2 --fixture SNAPSHOT_2_DIRECTORY
fifth-pick candidates --run-id RUN_ID
fifth-pick t20 --run-id RUN_ID --fixture SNAPSHOT_3_DIRECTORY
fifth-pick final --run-id RUN_ID
fifth-pick decide --run-id RUN_ID
fifth-pick result record --run-id RUN_ID --selection CANDIDATE_KEY
fifth-pick audit --run-id RUN_ID
```

Each directory contains `events.json`, the corresponding `odds-<eventId>.json`
files in the existing M4 fixture format, and a `stage.json` descriptor with these fields.

| Field | Input |
| --- | --- |
| `mode` | The literal `"fixture"` |
| `observed_at` | The timestamp of that synthetic observation in timezone-aware ISO 8601 |
| `aliases` | The same explicit provider-name-to-canonical-ID-list mapping at every stage |
| `evidence` | An object keyed by the exact M5 candidate keys from `candidates`. Use `{}` at Snapshot 1 or when supporting evidence is unavailable. |

Each evidence value contains `items` and `judgment`. An item supplies
`evidence_id`, `kind`, `effect`, `significance`, `claim`, and `excerpt`.
Include `samples` for history or `facts` for structured context as required by
the existing M6 evidence types. A sample supplies `played_at`, `value`, `opponent`,
and `season`. The judgment is either `null` or the existing
`MethodologyJudgment` fields, with citations represented as arrays. The selected
stage time is the simulated evidence retrieval time. Supply the actual rows of
the synthetic observation, and leave unavailable evidence absent.

Snapshot 2 is the prior evidence state. Until Snapshot 3, `candidates` shows a
provisional watchlist. The `t20` command collects Snapshot 3, ranks against the
prior supporting evidence, and reviews the current evidence using the same
three legitimate snapshots. Use the event's T-20 target for a positive review.
The fixture CLI takes one board and one observation time per stage. Events with
different T-20 targets cannot all receive a positive review in that fixture run.

The commands use local fixture transport. An identical stage replay returns
the recorded checkpoint without changing receipts. Conflicting replays,
unfinished stages, and mismatched receipts stop the run. Preserve its artifacts
and use a fresh run ID if a new fixture scenario is needed. `candidates` and
`audit` are read-only views and `final` reuses an existing verified proposal.
After explicit approval, use `synthetic-fixture` for the result source. If
providing settlement provenance, use a `fixture:` reference containing the exact
candidate key and confirm the supplied excerpt against the reviewed selection.

For the reproducible synthetic success and failure paths, run
`uv run python -m unittest tests.test_fixture_cli`. The suite builds the
fixture directories in a temporary location from the accepted synthetic
test data and uses a separate run store.

### Interactive terminal Demo Mode

From the project directory, launch `uv run fifth-pick menu`. A fresh run ID appears
in the header. To reopen its evidence, launch
`uv run fifth-pick menu --run-id RUN_ID` with the same ID. The menu uses the
bundled synthetic fixture and a macOS or Linux terminal.

Use **↑ / ↓** to move, **Enter** to select, **Esc** to cancel or go back,
and **Q** to exit from a menu or results screen. In a text form, type your
answer and press Enter, or press Esc to cancel. Confirmation screens start on
**Cancel**. To continue, select **Continue** explicitly.

1. Choose **Analyze NBA Slate** twice, confirming Snapshot 1 and then Snapshot 2.
2. Open **View Candidates and Rankings** for the provisional watchlist.
3. Choose **Run T-20 Review**, then **View Final Recommendations**. Confirm
   creation of the proposal the first time you open final recommendations.
4. Try **Record Results** before approval to see settlement blocked.
5. Open **Approve / Reject / Modify**. Joseph reviews the displayed selection
   and types his decision explicitly.
6. Inspect **View Audit and Receipts**. The screen shows the receipt trail and
   gives the command for the full evidence.

To demonstrate settlement after approval, select the approved pick under
**Record Results**. The synthetic example uses outcome `HIT`, source
`synthetic-fixture`, timestamp `2026-11-15T20:00:00+00:00`, and a
`fixture:results/CANDIDATE_KEY` reference with the displayed candidate key.
The fixture excerpt is `Synthetic PrizePicks Luka Doncic Assists Higher 9.5 settled HIT.`
Review the excerpt against the displayed pick before entering `YES`.

The fixture is bundled under `final-project/src/fifth_pick/demo/` and uses the same synthetic
inputs as the deterministic CLI integration tests.

### Product evidence and live board preparation

Launch with `uv run --offline --no-sync fifth-pick menu`. Demo stays the default.
**L Open Live Mode** shows saved slate timing and offers the quota-free preflight.
It requires the exact `PREFLIGHT` confirmation before sending a request. Paid
collection uses the separate owner confirmation in `board-collect`.
See the [product coverage and decisions](product-completion.md) for live source
and timing decisions.

After creating a fixture proposal, the following read-only commands use
the same persisted evidence.

```sh
fifth-pick schedule --run-id RUN_ID
fifth-pick review-material --run-id RUN_ID
fifth-pick review-status --run-id RUN_ID
fifth-pick evaluate --run-id RUN_ID
```

`review-material` emits the JSON argument object for the existing
`/fifth-pick-review` command in OpenCode. The artifact SHA-256 binds the exact
proposal and audit material. `review-status` reads matching M10 controller
receipts. A status obtained from the fixture bridge test is test evidence.
It does not constitute a native review of a production NBA run. After approval
and settlement, `evaluate` reports process checks and outcomes separately.

### Personal live preflight and collection

With `THE_ODDS_API_KEY` set securely in the process environment, run
`uv run fifth-pick board-preflight` and confirm with `PREFLIGHT`. It calls the
NBA events endpoint once, verifies that the provider reports zero credits
charged, and atomically saves the sanitized report to
`var/fifth-pick/preflight/YYYY-MM-DD.json`. It creates no LIVE slate or snapshots.
Use `fifth-pick board-status` to recompute the current timing classifications
offline from the saved report. Confirm the full official slate and verified
roster scope before requesting paid collection. The Python transport uses the
macOS system CA file if its default CA paths are missing and no explicit CA
override is configured. Keep the API key in the process environment.

The personal forecast uses exact canonical roster IDs and existing grants. It
shows both the complete official slate count and eligible collection scope.
It omits from a fresh three-snapshot budget any event whose first observation
can no longer precede the last valid Snapshot 2 time.

The run-wide LIVE collector accepts a separate owner grant at the application
boundary. The grant binds the run, policy digest, verified full-slate provider
IDs, exact event/team/tipoff and roster scope, allowed slots, and expiry. It uses
the application clock and storage, verifies provider quotas, reserves up to five
credits before each event observation, and makes no automatic retry. It checks
the selected event and window before paid dispatch. Source responses are hashed,
and verified in-scope grants are filtered before projection parsing and before
snapshot output or retention. A scoped response cannot mark another game's
observations missing. The public CLI supplies no paid grant by default.

`board-collect --run-id RUN_ID --scope FILE` reads the saved preflight for the
current Chicago date. Use `--preflight FILE` to reuse an existing successful
response saved elsewhere. The reviewed scope must contain the exact
selected `event` row, `slate_game_count`, canonical `player_ids`, and verified
provider `aliases` (provider label to canonical ID) with a matching
`alias_evidence` reference for each label. It previews the scope and waits
for Joseph's exact terminal confirmation before creating a slot-1-only grant.
It does not run a separate preflight before confirmation. After confirmation the
collector performs its required quota-free schedule and quota check before odds.
The odds response receipt records approved provider-reported market pairs and
quota counters. Collected coverage and accepted observation counts are separate.

An explicitly approved one-event validation can add `--series --snapshot 1`
and use the same run, scope, saved manifest and `--series` flag for slots 2 and 3.
For new LIVE series, save the complete, independently verified official
NBA slate for the Chicago date. Its earliest scheduled tipoff sets a single
clock for all events. Snapshot 1 and Snapshot 2 retain their existing spacing
rules relative to that clock. Snapshot 3 opens 25 minutes before the first
game and closes 20 minutes before it. The T−20 review opens at that common
target and retains its existing five-minute LIVE grace period. Final LIVE
approval must precede the first official game. Each request still must match
the provider event ID, teams, and recorded provider tipoff. Provider tipoff,
the selected game's official tipoff, and the shared slate clock remain
separate in the collection receipts. Existing runs keep their recorded clocks.


The first paid LIVE verification is a separately approved board-only smoke for
one verified event, with at most one free discovery request and one event-odds
request, five credits maximum, and zero retries. A completed board smoke does
not establish player-history access, compliant T-20 review, or a live proposal.

## Approved LIVE review and identity preparation

The [November 18 operational amendment](live-operational-amendment.md)
defines the review window and staggered release policy. `schedule` displays
the event-local close time. `audit` and `evaluate` read receipt-verified
product evidence without changing it.

`board-collect` can join separately verified identity inputs using
`--roster FILE --board-identities FILE`. Roster rows carry `stable_id`,
`canonical_id`, `team`, and `reference`. Board identity rows carry
`stable_id`, `provider_label`, `event_id`, `team`, and `reference`.
The terminal displays the scoped result for Joseph's review. The inputs
must come from corroborated sources approved for this purpose. The collector
does not infer a stable ID from a name or enable a new endpoint.

The native Controller dispatch command remains the sole Builder launch
authority. After its fresh revision-attempt confirmation and a Builder
correction specifying removals, the Controller records the bounded correction:

```sh
fifth-pick review-correct --run-id RUN_ID --remove CANDIDATE_KEY --reason REASON
```

Submit the returned revision-1 envelope to the native Reviewer. Inspect
`review-status` before making a decision. An exact corrected PASS permits
Joseph's decision. Original CONCERNS require explicit acknowledgement and
reason, with the displayed findings bound to the decision receipt. A second
FAIL stops without another correction.

For a known upcoming Chicago-date slate, pass `--date YYYY-MM-DD` and
`--expected-games COUNT` to `board-preflight`. It still makes exactly one
quota-free request and saves only that date. A count mismatch leaves any
existing manifest intact. Use `board-status --date YYYY-MM-DD` offline to
display the saved event IDs, quota and deadlines. Snapshot 2's actual opening
depends on the recorded Snapshot 1 timestamp. The date-level view reports
only its latest permitted time.

When a verified official schedule record exists, preflight reconciles the
returned matchups against that schedule by Chicago date. The report keeps
the official game count separate from provider event coverage and never
infers player or market coverage from event discovery. Partial or conflicting
coverage saves a sanitized report under `var/fifth-pick/preflight-coverage/`.
It does not replace a complete collection manifest. An off-date provider
matchup is shown separately and cannot satisfy the official slate. Paid
collection and LIVE finalization still require the verified full slate.

### November 21, 2026 one-event pilot

On the Chicago slate date, compare the complete official slate with the
provider's event IDs, matchups, and tipoffs. The commands below assume six
games only after that count is verified. Have Joseph review the exact event,
canonical player grants, and independent alias evidence before preparing the
scope file. Keep the credential in the invoking process environment.

After separate authorization for quota-free discovery:

```sh
.venv/bin/fifth-pick board-preflight --date 2026-11-21 --expected-games 6
.venv/bin/fifth-pick board-status --date 2026-11-21
```

Enter `PREFLIGHT` at the prompt. Stop on unmatched or incomplete slate
coverage. Use one verified event, a fresh run ID, and the same files throughout.
After Joseph authorizes the one-event series and up to 15 board credits:

```sh
RUN=nba-2026-11-21-board-pilot
SCOPE=/path/to/reviewed-event-scope.json
PREFLIGHT=var/fifth-pick/preflight/2026-11-21.json

# Chicago slate date, before T−80, with time for a distinct Snapshot 2.
.venv/bin/fifth-pick board-collect --run-id "$RUN" --scope "$SCOPE" --preflight "$PREFLIGHT" --series --snapshot 1
.venv/bin/fifth-pick schedule --run-id "$RUN"

# Only at the due time shown by schedule, through T−80.
.venv/bin/fifth-pick board-collect --run-id "$RUN" --scope "$SCOPE" --preflight "$PREFLIGHT" --series --snapshot 2
.venv/bin/fifth-pick analyze --run-id "$RUN" --snapshot 2

# T−25 through T−20, allowing time for the response before the cutoff.
.venv/bin/fifth-pick board-collect --run-id "$RUN" --scope "$SCOPE" --preflight "$PREFLIGHT" --series --snapshot 3
.venv/bin/fifth-pick audit --run-id "$RUN"
```

Joseph types the displayed `APPROVE <event-id> SNAPSHOTS 1-3 15` at each
slot. Skip a missed window. The CLI uses actual application and provider
times. Keep the complete slate for the five-selection ceiling when the slate
has six games.

Optional totals and spreads use a separate grant. Only after explicit approval
for one bookmaker and up to four additional credits, record the two-phase
grant after Snapshot 1. Substitute the verified event ID and bookmaker key.

```sh
.venv/bin/fifth-pick game-lines-grant --run-id "$RUN" --event-id "$EVENT_ID" --bookmaker "$BOOKMAKER" --phase analysis --phase t20 --max-credits 4
# After a timely Snapshot 2 and before T−20.
.venv/bin/fifth-pick game-lines-collect --run-id "$RUN" --phase analysis
# After a timely Snapshot 3, from T−20 through T−15.
.venv/bin/fifth-pick game-lines-collect --run-id "$RUN" --phase t20
```

Joseph types `AUTHORIZE GAME LINES` to record the grant and
`COLLECT GAME LINES` to authorize each collection. Each collection calls the
quota-free discovery endpoint once, checks the exact scheduled event, then
allows one two-credit request with no retry. The CLI requires the game lines
to be no more than ten minutes old. The combined board and optional
game-lines ceiling is 19 credits. These commands grant no spending authority.

Use `t20 --run-id "$RUN"` during T−20 through T−15 when phase-specific sources
and Controller assessments have been recorded. Its candidate `blockers` and
`history_note` fields identify missing inputs. For a board-only experiment,
end with `audit`. Game context and any cited moving facts must be current
for LIVE review. The [November 21 methodology revision](methodology-revision-2026-11-21.md)
makes player availability, injury, teammate absence, and role/minutes optional. History needs approved production access
and corroborated timing, coverage, and corrections. Follow the independent
review workflow and Joseph's pre-tipoff decision only if the CLI releases a
receipt-bound proposal.

### Controller assessment at Snapshot 2 and Snapshot 3

The human Controller previews the exact candidate and stage in the
application-owned LIVE ledger. Use Snapshot 2 after its timely capture and
before T−20. Use Snapshot 3 after its timely capture, from T−20 through
T−15. The command reopens receipts as of the application clock. It displays
the evidence and a scope digest only after stage validation succeeds.

```sh
.venv/bin/fifth-pick controller-assess --run-id "$RUN" --event-id "$EVENT_ID" --candidate-key "$KEY" --snapshot 2
```

Prepare a local judgment file with the preview's `run_id` and
`scope_sha256`, and the Controller's own `judgment` object. The existing
judgment fields are `disposition`, `confidence`, `rationale`,
`supporting_evidence_ids`, `meaningful_risk_ids`, and
`sufficient_evidence`. Optional fields are `major_unresolved_concern`,
`senior_lower_support_ids`, and `senior_lower_disclosure`. Use exact evidence
IDs from the preview. Evidence labels and authority come from the existing
validation rules. Keep credentials out of the judgment file.

```sh
.venv/bin/fifth-pick controller-assess --run-id "$RUN" --event-id "$EVENT_ID" --candidate-key "$KEY" --snapshot 2 --judgment-file "$ASSESSMENT_FILE"
# Repeat preview and submission for --snapshot 3 with its own judgment file.
```

The Controller types the displayed
`RECORD CONTROLLER ASSESSMENT <scope_sha256>` in an interactive terminal.
The command checks the scope again under the run lock. Re-preview changed
evidence. A missing or stale evidence record is grounds to stop. The CLI
records an assessment input. Continue with the existing `t20` command,
independent review of any released proposal, and Joseph's final decision.

The offline context validator accepts separately preserved source bytes,
attributed facts, and a capture receipt. Current registry entries do not
authorize a new delivery method. Before integrating a real source, obtain
explicit approval for its exact source ID, access method, and data kinds.
Independently verify the publisher and event roster, retain exact source
excerpts and hashes, and set an approved freshness limit. The validator
supplies no LIVE evidence on its own.

See the [November 21 methodology revision](methodology-revision-2026-11-21.md)
for the read-only `history-compare` command and the executable synthetic rehearsal.

### Tatum points pilot after separate approvals

Verify the complete official slate and the event roster. The collector applies
the existing grants across all 156 players, independent of Senior tier. The
confirmation preview lists any scoped players who lack bound board labels.
Resolve them through the identity crosswalk. The CLI authorizes one event
series per run.

Confirm written DunkAPI raw-retention permission, a fresh free-only balance,
and exclusive account use before approving capture. Supply an independently
corroborated Tatum provider ID and team label. If the ID cannot be found
offline, omit `--expected-provider-id` and add `--identity-only` to a separately
approved one-credit discovery. Corroborate the resulting
`discovered_unverified` ID before a history run. Supply the credential
privately in the process environment.

```sh
.venv/bin/python -B final-project/scripts/dunkapi_evaluation.py \
  --player-id jayson-tatum --team-label "$VERIFIED_TEAM_LABEL" \
  --identity-reference "$INDEPENDENT_IDENTITY_REFERENCE" \
  --expected-provider-id "$TATUM_PROVIDER_ID" --market POINTS --direction HIGHER \
  --season-end-year 2027 --authorize-live-free-only "$CONFIRMED_FREE_BALANCE" \
  --archive-dir "$NEW_PRIVATE_DIRECTORY_OUTSIDE_REPO" \
  --retention-approval-reference "$RETENTION_APPROVAL_ID"
```

Expect `matched_operator_pin`, terminal history with at least eight played
games, and exactly six verified credits if both requests succeed. Stop on an
unexpected response or next page. The opt-in capture retains exact bytes and
receipt metadata. Bind the history used to independent actual start and
completion, exact game and teams, separate coverage, and dated correction
evidence. Seal and pin each Stage 3 package before the board snapshot retrieval
time used for comparison.

After separate zero-credit discovery approval and event-series approval, use
the board collection commands and schedule above. With an eligible Tatum
Points line, attach the package to the first timely snapshot.

```sh
.venv/bin/fifth-pick analyze --run-id "$RUN" --snapshot 1 \
  --history-candidate-key "$KEY" --history-archive "$PACKAGE_DIR" "$PINNED_SHA256"
```

Repeat `--history-archive DIRECTORY SHA256` for additional packages. Expect
`historical_comparison.status=ANALYSIS_ONLY`. The outer LIVE view can still
return `BLOCKED` with exit code 1. Continue through the three genuine
snapshots, current game context, Controller assessments, independent review,
and Joseph's pre-tipoff decision only when each existing LIVE gate passes.

### November 21 Boston–Sacramento Snapshot 1 with label quarantine

Use the saved provider preflight and the separately corroborated timing record.
The grant preserves the provider's 9:10 p.m. Central timestamp, records the
official 9:00 p.m. Central tipoff, and expires at 7:40 p.m. Central. Complete
both capture and identity review before that cutoff.

```sh
.venv/bin/fifth-pick board-collect \
  --run-id nba-2026-11-21-bos-sac-s1 --snapshot 1 --quarantine-labels \
  --preflight var/fifth-pick/preflight/2026-11-21.json \
  --timing-file var/test-evidence/2026-11-21-bos-sac-timing.json \
  --roster var/test-evidence/2026-11-21-bos-sac-roster.json
```

Confirm the event and five-credit ceiling, then enter
`APPROVE b754a1bf84af81d45d4a3a16398daa44 SNAPSHOT 1 5`. The command first
makes the existing zero-credit schedule and quota check, then at most one
event-odds request. A paid response can be retained as quarantine even
when review is cancelled or no player can be verified.

After the command lists the captured labels, supply an independent
board-identity JSON file. Each record uses `stable_id`, `provider_label`,
`event_id`, `team`, and `reference` as described above. The file must bind
the actual provider label to the roster's NBA ID using corroborated
evidence. A name resemblance alone is insufficient. With a reviewed match,
type `VERIFY SNAPSHOT 1 IDENTITIES`. Unmatched labels stay in the quarantine
receipt. If no bindings can be verified in time, press Enter to stop.
Do not change the run ID to retry a stopped or completed paid attempt.

Use `.venv/bin/fifth-pick audit --run-id nba-2026-11-21-bos-sac-s1` to reopen
local records. Look for the odds response's quota, label quarantine receipt,
identity-review receipt, and completed slot. An unfinished reservation or
quarantine receipt does not establish a completed Snapshot 1.

An interrupted collection may have receipts before the first slate manifest or
`run.json` is written. The audit command opens these attempts as
`RECEIPTS_ONLY`. `COLLECTION_STOPPED` means a stop receipt exists.
`COLLECTION_INCOMPLETE` means the attempt lacks a completed slate record.
This output is diagnostic and grants no eligibility for analysis or later
snapshots. An event-odds receipt records the payload digest, quota and
provenance. It cannot restore the original bytes. For an attempt that ended
before identity verification, retain the receipts and close out the attempt.
Do not reuse the payload digest as evidence or retry the paid operation.
A first collection can also stop after writing some M4 or M5 artifacts.
Without the matching collection completion receipt, the audit remains
diagnostic and M5 rows for the reserved slot are excluded from the operational
ledger. Preserve the files for inspection.

### Inspect retained provider captures without spending credits

For future authorized LIVE board collections, the successful, quota-validated
event-odds response is saved before the identity prompt as
`var/fifth-pick/runs/<run-id>/dfs-board-<slot>-<event-id>-odds.body`.
The file uses private permissions and stays in the ignored run store.
The Odds API permits internal storage and restricts redistribution of raw
data. Keep these archives local.
[The Odds API terms](https://the-odds-api.com/terms-and-conditions.html)

Start with the saved slate and capture report. Both commands are offline.

```sh
.venv/bin/fifth-pick board-status --date 2026-11-21
.venv/bin/fifth-pick board-inspect \
  --run-id nba-2026-11-21-bos-sac-s1 \
  --event-id b754a1bf84af81d45d4a3a16398daa44
```

That capture predates raw retention. Its report contains quota, provider
market coverage and quarantined labels, with `ORIGINAL_RESPONSE_NOT_RETAINED`
and no lines. The original payload cannot be recovered from the digest.

For a future retained capture, use its actual run, event and slot. Add
`--roster FILE --board-identities FILE` using the same independent identity
crosswalk described above. The command checks the receipt digest and exact
event identity before showing each verified authorized line with its platform,
direction, source time and identity references. Add
`--line-number N --archive DIRECTORY SHA256` to compare one displayed line
with supplied history packages. Repeat `--archive` for additional games.

Every report is `PRELIMINARY_ONLY`. Archive replay checks internal consistency
and reports descriptive counts from the supplied games. It does not authenticate
external history or establish complete last-eight coverage. Inspection is
read-only and can happen after cutoff. It cannot write snapshots, turn a stopped
capture into a completed run, or release a recommendation. For an official
three-snapshot attempt, use the existing independently verified scope and
separately approved series budget from the start.

### Open the LIVE workflow from the terminal menu

Run `.venv/bin/fifth-pick menu` in an interactive terminal and press **L**.
Choose **View saved slate** or **Inspect retained board** to work offline.
The LIVE panel also opens scoped and quarantine collection, analysis, T-20,
Controller assessment, the independent review handoff, and Joseph's decision.
Collection shows its existing event, timing, and credit confirmation before any
paid request. Opening the panel itself makes no request. Use **Esc** to return
to the main menu.
