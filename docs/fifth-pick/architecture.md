# Fifth Pick Architecture

## Scope

This document describes the M2 domain model, receipts, and run storage; the M3 configuration, registry, identity, and authorization layers; the M4 source adapter, live client, quota control, and redaction; the M5 snapshot workflow; and the M6 evidence, methodology, confidence, and ranking core. M7 and later artifacts are reserved and are not implemented here.

M2 provides typed vocabulary and an append-only evidence store. M3 provides versioned authoritative configuration, a canonical player registry, exact identity resolution, and exact player/category/direction authorization. M4 provides an offline-testable The Odds API `us_dfs` adapter that produces platform-scoped, provenance-bearing boards and hands identity resolution to the M3 registry. M5 records authorized projection snapshots, missed slots, and receipts. M6 validates provenance-bearing evidence, evaluates typed methodology judgments only after snapshot integrity and authorization, produces candidate audits, and ranks eligible candidates without numerical scoring or slate finalization.

## Module Map

| Module | Responsibility |
|---|---|
| `src/fifth_pick/models.py` | Closed enums and typed dataclasses for observations, candidates, snapshots, provenance, evidence, decisions, results, and reason codes. |
| `src/fifth_pick/errors.py` | Typed validation, receipt, storage, unsafe-run-id, and receipt-conflict errors. |
| `src/fifth_pick/receipts.py` | Receipt schema and centralized redaction. |
| `src/fifth_pick/storage.py` | Injected-root run layout, atomic receipt writes, and event-key idempotency. |
| `src/fifth_pick/config.py` | Load and validate the six authoritative YAML configs, their schema and owner metadata, and their closed value sets. |
| `src/fifth_pick/registry.py` | Build canonical player IDs, exact name/alias/ID indexes, grants, and narrow one-player-one-slot uniqueness. |
| `src/fifth_pick/identity.py` | Resolve exact canonical names, registered aliases, and explicit provider aliases; ambiguous or unknown identity fails closed. |
| `src/fifth_pick/authorization.py` | Authorize exact player, category, and direction grants inside the live MVP; expose exact market mapping. |
| `src/fifth_pick/sources/base.py` | Pre-snapshot source projections, events, boards, live/fixture/unknown evidence mode, board provenance, and fail-closed source errors. |
| `src/fifth_pick/sources/transport.py` | Minimal `Transport` protocol, `HttpResponse`, an explicit live `UrllibTransport`, and `TransportError`. |
| `src/fifth_pick/sources/quota.py` | Credit budget, quota-header capture, and request-cost estimation. |
| `src/fifth_pick/sources/odds_api.py` | Approved The Odds API `us_dfs` request shape, response parsing, provenance, and fail-closed retrieval. |
| `src/fifth_pick/sources/normalize.py` | Exact market/direction mapping and fail-closed identity binding to the M3 registry. |
| `src/fifth_pick/sources/fixtures.py` | Synthetic offline fixture transport that never reaches the network. |
| `src/fifth_pick/snapshots.py` | M5 three-slot timing, identity and authorization checks, idempotent collection, missed slots, provenance, and receipts. |
| `src/fifth_pick/evidence.py` | M6 fixture evidence validation/redaction, canonical history-context records, and deterministic last-8/H2H summaries. |
| `src/fifth_pick/methodology.py` | M6 CandidateCase canonicalization, snapshot and authorization gates, qualitative confidence validation, Senior LOWER safeguards, and canonical audit production. |
| `src/fifth_pick/ranking.py` | M6 case-only ranking/persistence boundary with internal methodology evaluation, eligible-candidate ranking, Senior HIGHER priority, qualitative evidence ordering, constrained non-Senior near-tie decisions, and ranking serialization. |

M2 modules are standard-library only. M3 `config.py` uses PyYAML for local file loading; M3 modules do not import network libraries, read environment variables, log, or write to `var/fifth-pick/`. M4 `transport.py` uses only the standard library and `urllib`; `odds_api.py` reads the API key from the injected environment mapping (defaulting to `os.environ`) and performs no write, log, or receipt side effect. No M4 module writes to `var/fifth-pick/`.

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

Storage receives an injected root. M2 writes receipts; M5 adds the snapshot ledger:

```text
<injected-root>/
└── runs/
    └── <run_id>/
        ├── receipts.jsonl
        └── snapshots/
            └── ledger.jsonl
```

Run IDs must match `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. The resolved run path must remain under the injected root; traversal, separators, absolute paths, and symlink escapes fail closed.

The following plan artifacts remain reserved and are not created or implemented in M5:

```text
run.json
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

## M3 Configuration

The six files under `config/fifth-pick/` are authoritative and are loaded together:

```text
approved-universe.yaml
trust-tiers.yaml
methodology.yaml
governance.yaml
category-map.yaml
approved-sources.yaml
```

Every file has `schema_version: 1`. Only `approved-universe.yaml` is owner-versioned metadata: `content_version: "v1"`, `effective_date: "2026-11-15"`, and provenance naming Part II 9.1 and the 2026-11-15 authorization. The other five files must set `content_version` and `effective_date` to null; they do not infer dates or versions from document dates or schema version. Every file carries provenance.

The loader rejects missing files, non-mapping documents, duplicate or non-string YAML keys, missing/unknown keys, malformed values, duplicate player names/categories/aliases, and non-canonical enum values. It validates the exact five market mappings and the exact live-category set. `approved-universe.yaml` is the sole source of player/category/direction grants; `trust-tiers.yaml` is evaluation classification only and never grants authorization.

`approved-universe.yaml` entry content is additionally pinned by digest. After YAML duplicate-key parsing and exact owner-metadata validation, the loader canonicalizes the parsed `entries` list to deterministic UTF-8 JSON (`sort_keys`, compact separators, preserved list order) and compares its SHA-256 against the hard-coded `APPROVED_UNIVERSE_ENTRIES_SHA256` for the authorized `v1` / `2026-11-15` snapshot. Any added, removed, or altered player, category, direction, alias, or foul-trouble value changes the digest and fails closed with `ConfigError`. A caller-supplied `config_dir` that retains `v1` metadata therefore cannot be treated as the authorized universe, even though `load_configs(config_dir=...)` remains available for isolated validation tests. The digest covers only `entries`; the loader does not hash the other five config files, read the frozen specification at runtime, or add a signature or dependency.

`approved-sources.yaml` records only the frozen approved sources and restrictions. Fields not fixed by the frozen design, such as access method, freshness policy, and terms-review status, remain null. No source retrieval or network behavior exists in M3.

## M3 Registry and Identity

`Registry.from_universe()` derives a deterministic local `player_id` by lowercasing the canonical display name and replacing non-alphanumeric runs with hyphens. IDs are only stable local identifiers; they are never used to match caller input.

The registry enforces unique player IDs, unique canonical names, unique aliases, and aliases that do not shadow canonical names. A player with no grants, including `Malik Monk`, remains registered but cannot be authorized. Grants are exact `(category, direction)` pairs.

Identity resolution has two explicit paths:

- `resolve_canonical()` accepts only an exact canonical display name or an exact registered alias. It does not trim, case-fold, remove punctuation, normalize diacritics, or perform fuzzy matching.
- `resolve_provider()` accepts only an explicitly registered provider alias. A canonical display name is not a provider alias, and an unknown or ambiguous provider alias is not retried against the canonical registry.

Unresolved or ambiguous identity returns `PLAYER_IDENTITY_UNRESOLVED`; Luka Dončić is the only additional registered name variant. Provider aliases are synthetic test fixtures and are not approved production mappings.

## M3 Authorization

`AuthorizationGate` constructs its own `ConfigBundle` from the fixed default authoritative config directory. It derives the registry, category map, universe version, effective date, and live-category set from that validated bundle. Its constructor accepts no arguments, so callers cannot inject a registry, category map, live-category set, universe metadata, or an alternate config path. `load_configs(config_dir=...)` remains available for isolated validation tests but is not reachable through the authorization gate. `LIVE_MVP_CATEGORIES` is always used internally. The gate is immutable after construction: normal attribute reassignment fails, and its registry ID/name/alias indexes and category-map mappings are read-only, so nested policy data cannot be mutated through the gate.

`AuthorizationGate.authorize()` accepts one player ID, one `Category`, and one `Direction`.

- Unknown or outside-universe player IDs are denied with `PLAYER_IDENTITY_UNRESOLVED` before any evidence analysis.
- Non-canonical values, non-live categories, and missing exact grants are denied with `CATEGORY_NOT_AUTHORIZED`.
- `THREE_POINT_ATTEMPTS` remains canonical data where the frozen universe lists it, but is outside `LIVE_MVP_CATEGORIES` and therefore denied live. It is never mapped from `player_threes`.
- Trust tier, Senior status, and foul-trouble annotation are never consulted as authorization.
- Allowed and denied decisions carry the approved-universe version and effective date.

`validate_one_player_one_slot()` is a narrow uniqueness validator: a repeated canonical player ID is rejected rather than filling two candidate or final slots. It is not M8 finalization and does not implement ceilings, ranking, or approval.

M3 does not write receipts in production. Tests use the M2 `RunStore` with temporary injected roots to prove that allow and deny decisions can be recorded as evidence.

## M4 Source Adapter

M4 retrieves the approved The Odds API `us_dfs` board for PrizePicks and Underdog and stops at the boundary of the M2 `Observation`/M5 `Snapshot` store. It produces a `SourceBoard` of `SourceProjection` values with provenance timestamps but no snapshot number, no canonical identity, and no M5+ record. Nothing in M4 backfills evidence or fabricates a T-20 snapshot.

### Approved request shape

`OddsApiSourceConfig` fixes the region `us_dfs`, the bookmakers `("prizepicks", "underdog")`, and the five approved live markets `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, and `player_rebounds_assists`. Any deviation fails closed with `SourceError`. The request uses the quota-free events endpoint `GET /v4/sports/basketball_nba/events` and one per-event odds endpoint `GET /v4/sports/basketball_nba/events/{eventId}/odds?markets=<five>&bookmakers=prizepicks,underdog`. `regions` is omitted, the key is sent only in the `x-api-key` header, and the key never appears in a URL.

### Fail-closed retrieval

`OddsApiClient.fetch_board(live_authorized=..., budget=...)` requires an injected `Transport`, an explicit `live_authorized=True`, and a positive `QuotaBudget`. It fails closed, before any further call, on a missing key (`MissingApiKeyError`), a rejected credential (`UnauthorizedResponseError` for 401/403), an exhausted quota (`QuotaExhaustedError` for `x-requests-remaining: 0`, or 402/429), a malformed payload (`MalformedPayloadError`), and an estimate above budget (`BudgetExceededError`). The events endpoint is quota-free; the estimated cost is one credit per market per event. There is no retry, fallback, or provider substitution.

### Platform separation and market exactness

PrizePicks and Underdog projections are kept separate; the same player on both platforms yields two distinct `SourceProjection` values and is never combined. Only the five approved markets are projected. An unapproved market key in a payload (for example `player_threes`) is skipped and never becomes a `SourceProjection`; `THREE_POINT_ATTEMPTS` is never mapped from `player_threes`. Only exact `Over`/`Under` outcome names become directions.

### Provenance and redaction

`BoardProvenance` records the source id, region, bookmakers, markets, request timestamp, retrieval time, the maximum market `last_update` as the source update time (or `None` when absent), the SHA-256 of the concatenated raw response bodies, the redacted request URL, the captured `QuotaSnapshot`, and `evidence_mode`. The built-in `UrllibTransport` is marked `LIVE`; `FixtureTransport` is marked `FIXTURE`; custom/unmarked transports remain `UNKNOWN`. M5 rejects unknown mode and persists the mode with each snapshot so synthetic boards cannot be reported as live evidence. Redaction reuses the M2 `redact_text()` helper, so exact secrets and sensitive query parameters become `[REDACTED]`. The key is read only from `THE_ODDS_API_KEY` in the injected environment and is never logged, stored, or written to a receipt.

### Identity handoff

M4 does not resolve identity. `normalize.resolve_board()` binds each `SourceProjection` to the M3 registry using `IdentityResolver.resolve_provider()` only. A canonical display name is not treated as a provider alias, and unknown or ambiguous provider names fail closed with `PLAYER_IDENTITY_UNRESOLVED` while preserving the projection. M4 adds no production provider aliases.

### Offline testing

The client depends only on the `Transport` protocol. Tests inject a fake transport or the synthetic `FixtureTransport` in `tests/fixtures/odds_api/`, so no unit test reaches the network. `UrllibTransport` exists for explicit live use and is never constructed by default. Live smoke remains opt-in and requires separate explicit authorization and an explicit credit budget; no live request was made during M4 implementation.

## M5 Snapshot Workflow

`SnapshotWorkflow` accepts only an M4 `SourceBoard`, a `RunStore`, an exact `IdentityResolver`, and the authoritative `AuthorizationGate`. It rechecks the approved `us_dfs` source, bookmakers, and five markets; every projection must resolve to the exact configured registry player and pass exact category/direction authorization. PrizePicks and Underdog are separate snapshot keys and records.

Snapshot 1 records the first accepted projection observation before tipoff. Snapshot 2 targets the midpoint between Snapshot 1's source retrieval time and T-20 (`tipoff - 20 minutes`), capped at `tipoff - 80 minutes`. When a 60-minute separation is achievable, collection does not accept an earlier observation. If it is not achievable, a distinct observation after Snapshot 1 and before the latest target is allowed. If no valid target remains, or the latest target expires without Snapshot 2, the ledger records `SNAPSHOT_2_MISSED` and later collection cannot backfill it. An unavailable projection before the deadline is receipted and may be retried before the deadline.

Snapshot 3 targets the `tipoff - 25 minutes` through `tipoff - 20 minutes` window. If a projection is unavailable from T-25 until tipoff, the attempt is receipted and a new legitimate board observation may be collected before tipoff. A successful collection after T-20 but before tipoff is retained with its actual source retrieval and system recording timestamps and a `late` marker; after tipoff the slot is recorded as `PROJECTION_OBSERVATION_MISSED`. A missing Snapshot 2 is recorded before Snapshot 3 proceeds. Out-of-order requests are receipted and rejected.

Collection is idempotent for `(run_id, snapshot number, platform, canonical player, category, direction, event)`: a duplicate returns the persisted record. Missed markers prevent later reconstruction. There is no backfill operation, supporting-source refresh API, snapshot-four path, methodology evaluation, or finalization path in M5.

Each `snapshots/ledger.jsonl` entry stores the typed `Snapshot`/`Observation`, canonical player ID, `evidence_mode` (`LIVE` or `FIXTURE`), event tipoff, target and late state, `Provenance`, and a structured projection excerpt copied from the M4 `SourceProjection`. The excerpt is not represented as a raw payload; the M4 combined raw-payload SHA-256 is retained unchanged. `RunStore` receipts record accepted, duplicate, missed, late, and rejected collection events. The application-owned `application_run_store()` root is `var/fifth-pick/`; M5 tests may inject temporary roots and synthetic boards. M5 performs no API or network request.

## M6 Evidence, Methodology, Confidence, and Ranking

M6 accepts raw typed `CandidateCase` values built from M5 `SnapshotEvidence`; it does not retrieve boards or supporting sources. `rank_candidates()` is the trust transition: it accepts only candidate cases, invokes the methodology evaluator internally for each case, and immediately ranks the resulting local canonical audits. `write_candidates()` uses that same path before serializing; neither boundary accepts an audit batch or reusable methodology result from a caller. Before inspecting supporting evidence, evaluation requires exactly one each of Snapshots 1, 2, and 3, the approved board source and event-bound reference, a consistent canonical player/platform/category/direction/event/key and event start, a provider-player excerpt matching the canonical player or registered alias, strictly increasing source retrieval and record times, and Snapshot 2's exact M5 midpoint target derived from Snapshot 1. A case containing any `LIVE` snapshot must name its M5 `snapshot_run_id`; M6 resolves it under the application-owned `application_run_store()` root through M5's `read_application_snapshot_ledger()` path, requiring matching ledger records, source provenance, and accepted/missed receipts. The LIVE M6 API accepts no caller-selected store, workflow, or reader. Fixture cases retain the explicit offline path. The shared M5 ledger reader decodes and validates available snapshots and missed markers, including marker identity, slot uniqueness, event continuity, and recorded-time relationships, before an authorized incomplete case can return. Missing slots produce `INSUFFICIENT EVIDENCE` with the recorded missed reason or `PROJECTION_OBSERVATION_MISSED`; unauthorized identity/grants are blocked before caller-supplied gaps are disclosed; inconsistent authorized records raise `MethodologyError`. Snapshot 3 supplies the projection line for history summaries. Canonical audits retain the full validated snapshot sequence, provenance, Snapshot 3 late state, and the M5 run ID for LIVE inputs.

`EvidenceItem` requires candidate-scoped provenance, an excerpt, payload hash, source/retrieval timestamps, and explicit `LIVE` or `FIXTURE` mode. `validate_evidence_items()` disallows NBA statistical endpoints, rejects all `LIVE` supporting evidence because M6 has no supporting-source retrieval boundary, redacts every serialized evidence text field (including IDs, fact keys/values, and sample text), rejects repeated history-context kinds, and returns evidence in canonical ID order. Deterministic fixtures use the explicit `synthetic-fixture` source and remain labeled as fixtures. M6 performs no network access.

Last-8 summaries use the latest eight canonical game samples; same-season H2H summaries include only samples for the current season and opponent. Sample identity is `(played_at, opponent, season)`: identical duplicate rows collapse to one, while conflicting values for one game identity fail closed before summary computation. Both history summaries report counts relative to the Snapshot 3 line and authorized direction; they do not calculate a score or probability. Missing H2H and incomplete last-8 data are disclosed as minor gaps by default, per frozen A9; callers mark the gap critical when the recommendation materially depends on that missing evidence. Game total, point spread, matchup, role/minutes, availability, teammate absences, blowout risk, and other evidence remain separately identified with provenance and qualitative effects.

`MethodologyJudgment` is a structured, evidence-citing assessment. HIGH requires at least two distinct cited IMPORTANT supporting signals and no major concern or unresolved meaningful gap; duplicate underlying evidence does not count twice even if the caller relabels its `EvidenceKind` or ID. MEDIUM requires sufficient evidence and a cited meaningful risk/conflict or a disclosed meaningful gap. LOW remains analysis-only and is never ranked. Critical gaps fail closed with their named reason. Foul trouble is disclosed as a caution, not an automatic confidence cap. Senior status and category trust are read from authoritative configuration only after exact authorization; neither can grant authorization. Senior LOWER requires cited meaningful blowout/reduced-minutes support, at least MEDIUM confidence, and a disclosure. The non-Senior scoring showoff heuristic is recorded as a methodology stage and is not a deterministic rejection rule. Gaps are redacted, canonicalized by kind/reason, and preserve the strongest significance for each profile.

`CandidateAudit.to_dict()` records the candidate, authorization and methodology stages, evidence and provenance, history summaries, gaps, exclusions, confidence, rules, rationale, and full validated snapshot path. Ranking rejects caller-supplied `CandidateAudit` values and result-shaped wrappers because its input contract is only `tuple[CandidateCase, ...]`; it does not trust or accept a caller-held methodology result. Senior HIGHER candidates form the priority tier; Senior LOWER does not. Within tiers, candidates compare confidence first, then qualitative evidence dominance: stronger support, fewer/less significant concerns and disclosed gaps, and better comparable history. A candidate ranks ahead only when its evidence is no worse on each comparable dimension and strictly better on at least one; cross-dimensional or incomplete comparisons preserve stable order. No numeric score or weighted formula is used. An optional non-Senior near-tie decision must cite evidence, explain the preference, apply to matching confidence and the complete recorded candidate projection/context, evidence claims/excerpts/provenance/facts/raw samples, full validated snapshot sequence/provenance/late state and LIVE M5 run ID, summarized history, and every gap detail, state that one slot remains, and may reorder only an adjacent pair. `RankingResult.to_dict()` includes ranks, reasons, all canonical audits, and a valid zero-qualified outcome. `write_candidates()` accepts only candidate cases and atomically writes `candidates.json` after the same internal methodology/ranking path under the injected `RunStore` run directory. M6 does not expose an analyze CLI command, perform T-20, fill slate slots, finalize, or request Joseph's approval; those workflows remain outside this milestone.

## Reserved Later Milestones

- M7: T-20 review.
- M8: finalization, ceilings, and Joseph approval.
- M9: result grading.
- M10: harness hardening and hooks.
- M11: closeout, demo, and assurance.

Those milestones consume the M2 vocabulary and storage but are not implemented here.

## Course closeout product path

The terminal demo uses the provider-response fixtures through the M4 adapter,
M5 ledger, M6 evaluation, M7 review, M8 exact proposal approval, and M9
settlement. The demo and LIVE CLI share the domain controls while keeping
their evidence modes separate. The LIVE collector saves provider discovery
and uses one scoped run, exact identity bindings, and receipt-backed credit
reservations. LIVE analysis reads only application-owned, receipt-verified
observations and stops with a named reason while supporting-evidence
ingestion is unavailable. It creates no positive review or proposal under
that condition. The approved November 18 amendment governs event-local
timing and one frozen pool. See the runbook and source-verification record.
