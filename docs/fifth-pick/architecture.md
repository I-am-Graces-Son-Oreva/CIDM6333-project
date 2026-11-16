# Fifth Pick Architecture

## Scope

This document describes the M2 domain model, receipts, and run storage; the M3 configuration, registry, identity, and authorization layers; and the M4 source adapter, live client, quota control, and redaction. Later milestone artifacts are listed as reserved and are not implemented here.

M2 provides typed vocabulary and an append-only evidence store. M3 provides versioned authoritative configuration, a canonical player registry, exact identity resolution, and exact player/category/direction authorization. M4 provides an offline-testable The Odds API `us_dfs` adapter that produces platform-scoped, provenance-bearing boards and hands identity resolution to the M3 registry. None provides snapshot scheduling, methodology, ranking, T-20 review, finalization, approval, or result grading.

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
| `src/fifth_pick/sources/base.py` | Pre-snapshot source projections, events, boards, board provenance, and fail-closed source errors. |
| `src/fifth_pick/sources/transport.py` | Minimal `Transport` protocol, `HttpResponse`, an explicit live `UrllibTransport`, and `TransportError`. |
| `src/fifth_pick/sources/quota.py` | Credit budget, quota-header capture, and request-cost estimation. |
| `src/fifth_pick/sources/odds_api.py` | Approved The Odds API `us_dfs` request shape, response parsing, provenance, and fail-closed retrieval. |
| `src/fifth_pick/sources/normalize.py` | Exact market/direction mapping and fail-closed identity binding to the M3 registry. |
| `src/fifth_pick/sources/fixtures.py` | Synthetic offline fixture transport that never reaches the network. |

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

`BoardProvenance` records the source id, region, bookmakers, markets, request timestamp, retrieval time, the maximum market `last_update` as the source update time (or `None` when absent), the SHA-256 of the concatenated raw response bodies, the redacted request URL, and the captured `QuotaSnapshot`. Redaction reuses the M2 `redact_text()` helper, so exact secrets and sensitive query parameters become `[REDACTED]`. The key is read only from `THE_ODDS_API_KEY` in the injected environment and is never logged, stored, or written to a receipt.

### Identity handoff

M4 does not resolve identity. `normalize.resolve_board()` binds each `SourceProjection` to the M3 registry using `IdentityResolver.resolve_provider()` only. A canonical display name is not treated as a provider alias, and unknown or ambiguous provider names fail closed with `PLAYER_IDENTITY_UNRESOLVED` while preserving the projection. M4 adds no production provider aliases.

### Offline testing

The client depends only on the `Transport` protocol. Tests inject a fake transport or the synthetic `FixtureTransport` in `tests/fixtures/odds_api/`, so no unit test reaches the network. `UrllibTransport` exists for explicit live use and is never constructed by default. Live smoke remains opt-in and requires separate explicit authorization and an explicit credit budget; no live request was made during M4 implementation.

## Reserved Later Milestones

- M5: snapshot collection and missed-snapshot recording.
- M6: evidence, methodology, confidence, and ranking.
- M7: T-20 review.
- M8: finalization, ceilings, and Joseph approval.
- M9: result grading.
- M10: harness hardening and hooks.
- M11: closeout, demo, and assurance.

Those milestones consume the M2 vocabulary and storage but are not implemented here.
