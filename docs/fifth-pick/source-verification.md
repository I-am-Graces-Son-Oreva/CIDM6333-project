# M4 Source Verification

This document records what is known about The Odds API source for the Fifth Pick MVP, and
what is not. It separates Joseph-reported live verification evidence from the M4 offline
implementation. This documentation update makes no live request.

## Status and authority

- Joseph's 2026-11-15 instruction authorizes M4 implementation only: the approved
  The Odds API `us_dfs` source adapter, live-client implementation, redaction, quota
  controls, deterministic fixtures, and this verification evidence.
- That instruction does not authorize a live API request. **No live request was made
  during M4 implementation.** The separate 2026-11-16 smoke evidence below was supplied
  after implementation; it is recorded as reported evidence, not as a request made in this
  documentation session.
- The live verification described below was performed by Joseph on 2026-11-14, before M4
  implementation, and is recorded here from the frozen design
  (`docs/superpowers/specs/2026-11-13-fifth-pick-design.md`, Part III D1 and E1) and the
  implementation plan (`docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md`).
- The live secret key is supplied only through `THE_ODDS_API_KEY` in the environment. It
  is never stored, logged, printed, committed, or placed in a receipt.

## 2026-11-14 live verification baseline

Reported outcome: The Odds API `us_dfs` returned both `prizepicks` and `underdog` board
data, and the free-plan credit counter moved from 500 to 495, a cost of 5 credits.

Design Part III D1 requires the verification record to preserve several fields. Not all of
them survived into this repository, so each field is stated as either its known value or
`NOT CAPTURED`. No value below is reconstructed, guessed, or invented.

| Field (D1 requirement) | Recorded value |
|---|---|
| Date | 2026-11-14 |
| Provider | The Odds API |
| Region | `us_dfs` |
| Bookmakers returned | `prizepicks`, `underdog` (both present) |
| Markets verified | `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, `player_rebounds_assists` |
| `THREE_POINT_ATTEMPTS` | Outside the live MVP; `player_threes` is never mapped to it |
| Credits at start | 500 |
| Credits after verification | 495 |
| Credits consumed | 5 |
| Request URL (key redacted) | `NOT CAPTURED` |
| Request timestamp | `NOT CAPTURED` |
| HTTP status | `NOT CAPTURED` |
| Returned event IDs | `NOT CAPTURED` |
| `x-requests-remaining` | `NOT CAPTURED` (the 500 → 495 delta is reported; the raw header was not retained) |
| `x-requests-used` | `NOT CAPTURED` |
| `x-requests-last` | `NOT CAPTURED` |
| Raw response hash | `NOT CAPTURED` |

Because the raw live response was not retained, the M4 test fixtures are **not** derived
from it. They are synthetic, as described below.

## 2026-11-16 live smoke evidence

The following successful smoke evidence was supplied by Joseph. It records one event-list
request and one odds request; this entry does not retain response bodies or credentials.

| Field | Recorded value |
|---|---|
| Timestamp | `2026-11-16T01:39:48.150144+00:00` |
| Provider | The Odds API |
| Region | `us_dfs` |
| Total requests | 2 (1 event-list, 1 odds) |
| Maximum authorized budget | 5 credits |
| Event-list URL (key redacted) | `https://api.the-odds-api.com/v4/sports/basketball_nba/events` |
| Event-list HTTP status | 200 |
| Event-list quota (`remaining` / `used` / `last`) | 495 / 5 / 0 |
| Selected event ID | `78f61a78b70b9d79f38eb7648eac1a08` |
| Odds URL (key redacted) | `https://api.the-odds-api.com/v4/sports/basketball_nba/events/78f61a78b70b9d79f38eb7648eac1a08/odds?markets=player_points,player_assists,player_rebounds,player_points_rebounds_assists,player_rebounds_assists&bookmakers=prizepicks,underdog` |
| Odds HTTP status | 200 |
| Odds quota (`remaining` / `used` / `last`) | 491 / 9 / 4 |
| Bookmakers returned | `prizepicks` |
| Bookmakers not returned | `underdog` |
| Markets requested | `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, `player_rebounds_assists` |
| Combined payload SHA-256 | `3aadbb7b7d24d8505fddc68c33ddef16cbcb8c4ec985d650fd1e396631ddf956` |

The reported quota counters show four credits consumed during this smoke (`used` 5 to 9;
`remaining` 495 to 491), within the five-credit maximum budget. The key is not included in
this record.

## M4 offline verification

M4 is verified offline. The client depends only on an injected `Transport`; tests inject a
fake transport or a synthetic `FixtureTransport`, so no unit test can reach the network.

### Synthetic fixtures

`tests/fixtures/odds_api/` contains hand-written synthetic bodies shaped from The Odds API
v4 documentation:

```text
tests/fixtures/odds_api/events.json
tests/fixtures/odds_api/odds-evt-bos-nyk-20261115.json
tests/fixtures/odds_api/odds-evt-lal-dal-20261115.json
tests/fixtures/odds_api/README.md
```

These are deterministic fixtures. They are not live evidence, were not captured from a live
request, and contain no credential or real response body. All event IDs, team names, and
projections are invented. `events.json` is a two-event array; each `odds-<eventId>.json`
holds a `bookmakers` array. One fixture deliberately includes a `player_threes` market to
prove the adapter never projects an unapproved market.

The provenance `payload_sha256` for a fixture board is computed at runtime by
`OddsApiClient._hash_payload()` over the concatenated response bodies in sorted event-id
order. No live payload hash is recorded.

### Verified offline behavior

- The approved request is the quota-free events endpoint plus one per-event odds endpoint:
  `GET /v4/sports/basketball_nba/events` and
  `GET /v4/sports/basketball_nba/events/{eventId}/odds?markets=<five>&bookmakers=prizepicks,underdog`.
- The request omits `regions` and never places the key in the URL; the key travels only in
  the `x-api-key` header.
- PrizePicks and Underdog projections stay separate; identical players on both platforms
  produce distinct projections rather than one combined line.
- Only the five approved live markets are requested and projected. Alternate markets,
  `player_threes`, and `THREE_POINT_ATTEMPTS` are never requested or projected.
- Quota headers `x-requests-remaining`, `x-requests-used`, and `x-requests-last` are
  captured when present.
- Missing key, unauthorized response, malformed payload, quota exhaustion, and an
  over-budget estimate all fail closed before spending further credits.
- Live retrieval requires explicit authorization and a positive credit budget.

## Redaction and key handling

- The key is read only from `THE_ODDS_API_KEY` in the environment.
- The key is sent only in the `x-api-key` request header. It is never added to a request
  URL, so there is no key in any URL to leak.
- `fifth_pick.receipts.redact_text()` redacts exact supplied secrets and sensitive query
  parameter values (including `apiKey` and `api_key`) with the fixed marker `[REDACTED]`.
  The client redacts the recorded request URL through that helper, and tests prove that a
  key-bearing URL is redacted and that no error message echoes the key.
- No receipt or log written by M4 contains the key.

## Official documentation

The adapter follows the documented The Odds API v4 request shape:

- The Odds API home and plan information: <https://the-odds-api.com/>
- The Odds API v4 API guide (endpoints, `x-api-key` header, quota headers, `us_dfs`
  region, and the `prizepicks`/`underdog` bookmakers):
  <https://the-odds-api.com/liveapi/guides/v4/>

No other provider is substituted. If a future verification fails, the project returns to
Joseph rather than silently changing the source.

## November 18 public availability check

The official November 18, 2026 index exposed a [9:00 p.m. Eastern NBA Injury Report](https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-18_09_00PM.pdf).
The edition was inspected by 8:21 p.m. Central. This records its source and
publication time only. Tonight's fresh Snapshot 1 windows had closed, and
the report was not attached to a candidate or treated as a T-20 refresh.
Automated ingestion and current LIVE supporting-source validation remain
unavailable. The 12-game public schedule does not supply a full provider-ID
manifest.

## BALLDONTLIE NBA ALL-STAR documentation check

The provider lists NBA ALL-STAR at USD 9.99 monthly and 60 requests per minute.
Game Player Stats, Active Players, and Player Injuries are included. The
documented stats contract supplies exact provider IDs, calendar dates, P/R/A,
minutes, final status, postponed status, and cursor pagination. The game-detail
start timestamp does not establish the completion or correction time. Missing
rows do not identify DNP, and a complete cursor chain does not prove that all
appearances were delivered. Official availability remains a separate source.

The bounded history client and date-level selection are exercised with injected
responses. Real transports are disabled until an independently verified
provider identity binding is available. They do not confer M6 evidence
authority. Account entitlement, actual
season coverage, crosswalks, and correction freshness remain unverified. Public
terms permit lawful analysis and retention of lawfully obtained data, subject
to their applicable restrictions. No purchase or provider request was made.

See the [NBA API documentation](https://docs.balldontlie.io/) and
[provider terms](https://www.balldontlie.io/terms.html).

### NBA trial authentication isolation

The existing pilot sends the environment credential as the raw `Authorization`
header to `/v1/players/115`, then uses `/v1/stats` only after verifying the player
record. The provider documents Players and Teams for every NBA tier, and Game
Player Stats for ALL-STAR and GOAT. Trial access uses the same header. HTTP 401
alone does not distinguish credential acceptance from entitlement.

The separately confirmed diagnostic `fifth-pick bdl-validate --auth-only
--confirm` calls only `/v1/teams` with zero retries. Success reports HTTP 200
and the request count. Failure reports a sanitized stage and HTTP status or
transport category. A 200 confirms credential acceptance for Teams only. A 401
on Teams leaves the credential, account and request path to resolve before
trying Player Stats. Neither command prints the key or response body. Do not
run either diagnostic until authenticated access is explicitly approved.

**Observed NBA trial result, reported by Joseph from his VS Code terminal.**
The authenticated Teams probe completed successfully and printed
`{"http_status":200,"mode":"AUTH_VALIDATION_ONLY","request_count":1}`.
This verifies credential acceptance on `GET /v1/teams` at the time of that
request. The earlier two HTTP 401 reports did not identify whether the
identity or stats stage returned the error. Their cause remains unresolved.
**Observed player identity result, reported by Joseph from his VS Code terminal.**
The separate Players request returned HTTP 200 and corroborated
`stephen-curry` (NBA ID 201939) with BALLDONTLIE player ID 115. The reported
identity payload SHA-256 was
`23b3529d34ff3c37184732f5c6c631bcbb0b93353ab7e0e409b1a7c9307f1612`.
References are the [NBA profile](https://www.nba.com/player/201939/stephen-curry)
and [BALLDONTLIE player record](https://api.balldontlie.io/v1/players/115).

The next diagnostic is `bdl-validate --stats-only --confirm`. It uses the
documented identity binding for this diagnostic only and makes one
`GET /v1/stats` request. The request is scoped to player 115, the current
season start year, full-game stats, and dates before the current Chicago
date, with up to 100 rows. It stops on a cursor and rejects rows outside
scope or without completed-game status. A valid response establishes Stats
access for that request. It does not establish history coverage, correction
freshness, or LIVE M6 evidence authority. Obtain explicit approval first.

**Observed Stats result, reported by Joseph from his VS Code terminal.**
The approved one-request Stats-only validation stopped with
`BALLDONTLIE history returned HTTP 401`. The request was for player 115.
The earlier Teams and Players 200 results remain verified for those
endpoints. No Stats payload or history receipt was admitted.

The [Stats contract](https://docs.balldontlie.io/#get-all-stats) confirms
the NBA v1 path and the player, season, inclusive end date, period zero,
and page-size parameters used by this request. All three requests use the
same raw Authorization header builder and HTTPS transport. The client
checks the HTTP status before parsing any history. The [tier and trial
documentation](https://docs.balldontlie.io/#account-tiers) lists Stats for
NBA ALL-STAR and GOAT, including the NBA GOAT trial. No separate Stats
add-on is documented. Current evidence points to a Stats-specific access
issue. The provider has not confirmed the actual account entitlement or
the cause of the rejection. Confirm NBA GOAT trial provisioning with the
provider before another separately approved Stats request. No credential
rotation or request change is indicated by the current evidence.

### Production source integration checkpoint

The direct injury-document adapter is disabled by the current source
registry. It requires an explicitly approved direct PDF delivery method,
terms approval, and operator authorization. It records attempts and document
digests for an exact edition. The local `pdftotext -layout` interface and
row validator check edition, matchup, scheduled time, team, and an independently
verified player label. Missing and duplicate rows do not establish availability.
Tests replay synthetic document bytes and representative extracted layouts.
Poppler `pdftotext` is unavailable in this checkout's environment. Actual PDF
extraction and official delivery have not been verified here.

The game-lines adapter requires an explicit run, event, bookmaker, approved
phases, and credit ceiling. It reserves an attempt before transport, reconciles
the two-market charge against supplied quota counters, and binds successful
spreads and totals to exact-match receipts. Tests inject the transport.
There is no production CLI issuer for a game-lines grant at this checkpoint.
No live bookmaker was selected and no Odds API request was made.

The remaining implementation work is to connect the authorized source
issuers and durable evidence records to M6 and LIVE T-20. That includes
binding the current NBA injury edition and normalized rows to a receipt,
admitting historical coverage only with corroborated completion and correction
evidence, and supplying a receipt-backed prior quota to the game-lines
adapter. The LIVE analysis gate remains closed. The fixture CLI uses synthetic
injury document text and lines, three snapshots, a synthetic Controller verdict,
and Joseph's explicit decision. This does not verify native NBA review or a
real settlement.

### Local injury extraction and game-lines grant checkpoint

On macOS, the injury extractor can use system PDFKit through the local
`osascript` command when Poppler is unavailable. Both extraction paths
run with a bounded input, timeout, and credential-free subprocess
environment. The macOS test extracts text from valid synthetic PDF bytes.
The existing representative layout tests check row identity and edition.
Actual official document acquisition and extraction remain unverified.

The game-lines CLI records authorization independently of acquisition.
For a run with a receipt-bound LIVE Snapshot 1, Joseph can prepare a
two-phase, four-credit ceiling using this command with his own identifiers.

```zsh
uv run --offline --no-sync fifth-pick game-lines-grant --run-id RUN_ID \
  --event-id EVENT_ID --bookmaker BOOKMAKER_KEY \
  --phase analysis --phase t20 --max-credits 4
```

The command displays the exact scope and requires `AUTHORIZE GAME LINES`.
For one phase, use one `--phase` and `--max-credits 2`. The authorization
receipt is immutable for the run and does not dispatch. Acquisition refuses
to create its own authorization and requires a matching prior receipt and
separate request authorization. Authentication, bookmaker scope, reliable
quota, source review, and LIVE admission remain distinct controls.

### Receipt issuer and LIVE orchestration checkpoint

The history issuer validates captured provider-shaped pages, exact player and
season scope, page digests, chronology, and separately identified NBA
corroboration before persisting the request, response, and corroboration. It
makes no request. The controlled test verifies readback, tamper rejection,
missing corroboration, insufficient coverage, and rejection of a Stats-provider
URL presented as independent corroboration. Actual NBA reference content and
the production source approval remain external prerequisites.

LIVE T-20 can reopen both assessment receipt times and source states and route
qualified cases through the existing M7 review and M8 finalization functions.
A prior LIVE assessment uses the Snapshot 2 projection and movement. The
controlled run verified that a recorded refreshed assessment without a prior
assessment cannot create a review or proposal. It did not reach a positive
proposal. Current production sources supply neutral facts. There is no
receipt-bound assessment producer for aligned or adverse evidence
interpretation, and no admitted current role/minutes or teammate-absence
input for positive M7 readiness. These are implementation gaps.

All four quality gates passed with 629 tests. The focused run passed 17 tests.
No authenticated provider requests or LIVE acceptance were performed.
