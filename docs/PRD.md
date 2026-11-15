# Product Requirements Document

## Product: Fifth Pick — An NBA Fantasy Selection & Discipline Experiment

## System

The Fifth Pick is a human-governed NBA fantasy-selection CLI. It applies Joseph's approved selection methodology, evidence standards, T-20 review, and discipline ceilings.

## User

Joseph Edafiadhe, operating as Governance Zero. Joseph is the sole authority for methodology, the approved player universe, final approval, and any exception.

## Problem

Manual NBA fantasy selection is inconsistent, time-sensitive, and vulnerable to impulse. Projection movement, late injury news, role changes, and confirmation bias create avoidable errors.

## Product Goal

Provide a disciplined, auditable decision-support process that:

- retrieves the approved board;
- restricts analysis to the approved universe;
- gathers trustworthy evidence;
- applies Joseph's methodology without changing it;
- compares three legitimate projection observations;
- performs the T-20 review;
- applies no-entry discipline;
- produces ranked recommendations or `NO ENTRY RECOMMENDED TODAY.`;
- records enough evidence to audit the process separately from the outcome.

The Fifth Pick never submits entries, places wagers, logs in, or moves money.

## Frozen Design and Source Constraints

These constraints are part of the approved design and supersede conflicting earlier text.

- The Odds API is the approved MVP board source. PrizePicks and Underdog data are retrieved through `us_dfs`.
- Verified live markets are `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, and `player_rebounds_assists`.
- `THREE_POINT_ATTEMPTS` remains part of Joseph's methodology but is outside the live MVP. The system must not substitute threes made or fabricate attempts.
- Alternate markets are not queried by default. Multiplier data is optional metadata and is never required for a valid projection.
- PrizePicks and Underdog lines remain platform-specific. The system must never combine them into one artificial line.
- A local canonical player registry is required. DFS responses do not provide stable player IDs. Name-only or ambiguous matches fail closed.
- Authorization comes from Joseph's approved universe. Trust tiers do not create authorization; a trust-derived category is eligible only if Joseph explicitly includes it.
- Malik Monk remains in the registry but has no approved category or direction. He is unselectable until Joseph resolves both.
- Missing evidence fails closed with a named reason. The system must not invent projections, injuries, roles, movement, availability, or confidence.
- The system must record evidence provenance, retrieval time, platform, event, player, category, projection, and direction.
- Three legitimate projection observations are required. Snapshot 3 is T-20. Supporting-source refreshes do not count. Missed snapshots are recorded as missed and never backfilled.
- The T-20 review is mandatory. Conclusions are `STILL STRONG`, `DOWNGRADED`, or `REMOVE RECOMMENDED`; unavailable evidence produces `T20_CHECK_UNAVAILABLE`.
- DNP and void are not MISS. The system must not mark HIT or MISS without a trustworthy final result and must use `RESULT UNAVAILABLE` otherwise.
- Game totals and spreads are analytical evidence only, not automatic prediction rules.

## Acceptance Criteria

1. The system provides a CLI for analyzing a slate, ranking candidates, producing a final slate, performing a T-20 review, and showing an audit trail.
2. The system applies only Joseph's approved player universe and authorized categories and directions.
3. The system retrieves current fantasy projections from an approved source and never depends on Joseph manually supplying the board.
4. The system never submits entries, places wagers, logs in, or moves money.
5. The system gathers supporting evidence from approved sources and records source identity, retrieval time, source timestamp, access method, and relevant provenance.
6. The system evaluates candidates using Joseph's approved methodology, including:
   - projection and movement;
   - last-8 performance;
   - same-season H2H where available;
   - role, minutes, and usage;
   - injuries and teammate absences;
   - matchup;
   - game total and spread;
   - blowout risk;
   - Senior status;
   - category trust;
   - foul-trouble annotations where applicable;
   - conflicting evidence.
7. The system assigns confidence as HIGH, MEDIUM, or LOW according to Joseph's approved criteria.
8. The system produces a ranked final slate, or `NO ENTRY RECOMMENDED TODAY.`.
9. The system applies the stop gate:
   - HALF SLATE, 1–4 NBA games: maximum 4 selections;
   - FULL SLATE, 5+ NBA games: maximum 5 selections;
   - ceilings are not targets;
   - zero is valid;
   - slots are never filled merely to reach a ceiling.
10. The system performs a T-20 review and can retain, downgrade, or remove a candidate.
11. The system provides a durable, reviewable audit trail that distinguishes process quality from outcome.
12. The system never guarantees wins and never claims a hit-rate advantage without evidence.
13. The system uses Standard Technical English in human-facing output and defines specialized terms.
14. The system uses The Odds API `us_dfs` as the approved MVP board source for PrizePicks and Underdog data, unless Joseph explicitly changes the source.
15. The system retrieves only the approved live markets: `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, and `player_rebounds_assists`.
16. The system does not retrieve or evaluate `THREE_POINT_ATTEMPTS` in the live MVP and does not substitute threes made or fabricate attempts.
17. The system keeps PrizePicks and Underdog projections platform-specific and never synthesizes a combined line.
18. The system uses a local canonical player registry and fails closed on unknown or ambiguous identity.
19. The system enforces authorization before methodology and ranking; trust tiers never create authorization.
20. The system records Malik Monk as in-registry but unselectable until Joseph defines both category and direction.
21. The system emits a named missing-evidence reason when required evidence is unavailable and does not proceed on invention.
22. The system records exactly three legitimate projection observations per relevant candidate, with Snapshot 3 at T-20, and never backfills a missed observation.
23. The system blocks finalization when T-20 review is unavailable and records `T20_CHECK_UNAVAILABLE`.
24. The system treats multiplier data as optional metadata and remains able to evaluate a valid projection when no multiplier is available.
25. The system never marks HIT or MISS without a trustworthy result; DNP and void are not MISS; unavailable settlement produces `RESULT UNAVAILABLE`.
26. The system does not query alternate markets by default and tracks API usage against a configurable budget.
27. The system distinguishes live evidence from deterministic fixtures and never presents fixture data as live evidence.
28. The system requires Joseph's explicit `APPROVE`, `REJECT`, or `MODIFY` decision before any official finalization.
29. The system exposes `fifth-pick health` as a mechanical health check.
30. The system passes all four required mechanical gates before implementation is claimed complete.
31. The system distinguishes verified current information from uncertainty and discloses missing, outdated, or conflicting evidence rather than treating it as verified.
32. The system records reasons for important recommendations, exclusions, and stop decisions.
33. If a late change removes a candidate, the system does not automatically replace that candidate merely to maintain the previous selection count.
34. The system follows a bounded execution process: it stops when it reaches a final recommendation, a no-entry decision, or cannot obtain required information, rather than continuing unnecessary tool calls.

## Course and Harness Constraints

- The implementation must be a Python CLI named `fifth-pick`; no website or GUI.
- Development must follow Superpowers discipline and Standard Technical English.
- `AGENTS.md` must use exactly four sections and remain under the course's 4,000-character ceiling.
- Project skills must cover candidate evaluation, evidence validation, final-slate review, and T-20 review.
- The design must include a planner/builder/reviewer separation and a Reviewer that cannot edit Builder work.
- Reviewer verdicts are `PASS`, `FAIL`, or `CONCERNS`. Malformed or unknown verdicts fail closed. A `FAIL` permits exactly one correction attempt; a second failure escalates to Joseph. `CONCERNS` never auto-`PASS`.
- OpenCode permissions, hooks, or plugins must mechanically support the read-only Reviewer control where required.
- The assurance table must pair each risk with a real control and evidence; prompt statements are not enforcement.
- Required gates:

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

- All four gates must exit `0`. Use Python, `uv`, `ruff`, `ty`, and `unittest`, not pytest.
- No Fifth Pick implementation is authorized until Joseph explicitly authorizes implementation.

## Governance and Decision Rights

- Joseph owns the methodology, approved universe, category/direction map, and final slate.
- The system may recommend `NO ENTRY RECOMMENDED TODAY.` and may recommend fewer selections than a ceiling.
- The system must not expand the universe, add categories, relax confidence thresholds, or fill slots to make a slate look complete.
- The system must not change Joseph's methodology, even when the change appears useful.
- The system must not promote a LOW-confidence candidate without Joseph's explicit approval.
- The system must escalate unresolved source, identity, evidence, authorization, or result questions to Joseph rather than guessing.

## Data and Evidence Requirements

- Every observation must retain platform, player, category, projection, direction, event, source update time, system retrieval time, and snapshot identity.
- Every exclusion must retain a reason, rule identifier, universe version, timestamp, and run identifier where applicable.
- The system must preserve raw payloads or excerpts sufficient for audit without exposing secrets.
- The system must not log API keys, tokens, cookies, or credentials.
- Missing-evidence reasons include:
  - `PLAYER_IDENTITY_UNRESOLVED`
  - `CATEGORY_NOT_AUTHORIZED`
  - `PROJECTION_UNAVAILABLE`
  - `PROJECTION_OBSERVATION_MISSED`
  - `AVAILABILITY_UNRESOLVED`
  - `ROLE_OR_MINUTES_UNRESOLVED`
  - `T20_CHECK_UNAVAILABLE`
  - `SOURCE_CONFLICT_UNRESOLVED`
  - `INSUFFICIENT_SUPPORTING_EVIDENCE`

## Boundaries

- This phase is design and documentation only. No Fifth Pick implementation may begin without Joseph's explicit authorization.
- Remove all website, GUI, bankroll-management, guaranteed-prediction, and automatic-submission features.
- Remove all scraping, login automation, cookie reuse, and unofficial endpoint use.
- Remove all invented data, fallback sources, and silent source substitutions.
- Remove all expansion of the approved universe or category set to fill a slate.
- Remove all automatic HIT or MISS claims without a trustworthy result.
- Do not treat a win as proof of good process or a loss as proof of bad process.

## Attestation

I, Joseph Edafiadhe, attest that this PRD represents the intended user, problem, boundaries, and acceptance criteria for The Fifth Pick.

Attested: 2026-11-11

## Post-Checkpoint Authorization Addendum (2026-11-14)

The design-phase statements above remain as historical checkpoint evidence. After that checkpoint, Joseph explicitly authorized M1 implementation. The current authorization is limited to M1 and, for the present remediation, the five findings in the final M1 review. It does not authorize M2, domain functionality, or a commit.
