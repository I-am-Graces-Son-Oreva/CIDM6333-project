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
