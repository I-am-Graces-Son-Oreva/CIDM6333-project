# Synthetic Odds API Fixtures

These files are **synthetic fixtures**. They are shaped from the official The Odds
API v4 documentation to exercise the M4 source adapter offline.

- They are **not** live evidence.
- They were **not** captured from a live request.
- No API key, credential, or real response body is present.
- All team names, event IDs, and player projections are invented for determinism.

The event IDs are stable strings so that the per-event odds files can be resolved
by name: `odds-<eventId>.json`.

The approved M4 request uses the free events endpoint and the per-event odds
endpoint:

```text
GET /v4/sports/basketball_nba/events
GET /v4/sports/basketball_nba/events/{eventId}/odds?markets=...&bookmakers=prizepicks,underdog
```

`events.json` is a JSON array of event objects. Each `odds-<eventId>.json` is a
JSON object with a `bookmakers` array. A `player_threes` market is intentionally
included in one fixture to prove the adapter never projects an unapproved market.
