# Fifth Pick MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a course-sized Python CLI that applies Joseph's frozen Fifth Pick methodology to The Odds API board, enforces deterministic authorization and snapshot integrity, records auditable receipts, and requires Joseph's final approval.

**Architecture:** A deterministic Python core owns configuration, identity, authorization, normalization, snapshots, ceilings, receipts, and result rules. The CLI exposes a linear workflow from board retrieval through T-20, finalization, Joseph's decision, and result grading. OpenCode roles and skills provide planner/builder/read-only-reviewer discipline, while Python and harness controls enforce what prompts cannot.

**Tech Stack:** Python 3.11+, `uv`, `ruff`, `ty`, `unittest`, standard-library HTTP (`urllib.request`), PyYAML for authoritative config, JSON/JSONL artifacts, OpenCode project-local agents/skills/permissions/hooks.

**Spec:** `docs/superpowers/specs/2026-11-13-fifth-pick-design.md`

**Authority:** Frozen design Part III D/E, `AGENTS.md`, `docs/PRD.md`, and the verified Odds API findings. No implementation is authorized until Joseph explicitly approves it.

## Global Constraints

- Preserve `evolution-00` through `evolution-08` untouched. No edits, rewrites, moves, or normalization.
- Python CLI only. No website, GUI, database server, bankroll system, or wagering submission path.
- No entry submission, wager placement, login automation, cookie reuse, scraping, or money movement.
- Use `uv`, `ruff`, `ty`, and `unittest`. Never use pytest.
- Required gates and expected exit code `0`:
  - `uv run ruff check`
  - `uv run ruff format --check`
  - `uv run ty check`
  - `uv run python -m unittest discover -s tests`
- Record at least one genuine gate failure before claiming the gates as evidence.
- `AGENTS.md` remains the four-section control map and stays under 4,000 characters.
- Runtime artifacts go under gitignored `var/fifth-pick/`.
- Secrets come only from `THE_ODDS_API_KEY`. Never print, log, receipt, commit, or serialize the key.
- The Odds API source is `us_dfs`; PrizePicks and Underdog observations remain separate.
- Live MVP markets: `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, `player_rebounds_assists`.
- `THREE_POINT_ATTEMPTS` is outside live MVP. Never substitute threes made or fabricate attempts.
- No alternate markets by default. Multipliers are optional metadata and never required.
- Never use NBA.com statistical endpoints or treat them as approved APIs. Supporting evidence must come from an approved source with provenance.
- Canonical player registry is mandatory. No name-only matching. Ambiguous identity fails closed.
- Trust tiers affect evaluation only. They never expand authorization.
- Exactly three legitimate projection observations; Snapshot 3 is T-20. No backfilling.
- DNP/void are never MISS. Use `RESULT UNAVAILABLE` when settlement is untrustworthy.
- Ceilings: HALF 1–4 games / max 4; FULL 5+ games / max 5. Ceilings are not targets.
- No official finalization without Joseph's explicit `APPROVE`, `REJECT`, or `MODIFY`.
- M1 establishes the planner/builder/read-only-reviewer baseline and narrow permissions before domain implementation.
- Reviewer cannot edit Builder work. Malformed verdicts fail closed. One correction attempt, then Joseph.
- Assurance requires a real control and evidence per risk. A prompt statement is not enforcement.
- No commits during this planning stage. Future commits require Joseph's implementation authorization.

## Frozen Decisions Incorporated

These are resolved inputs, not implementation questions. The plan must encode them and must not reopen them.

### Snapshot Policy

- Snapshot 1 is the first legitimate successful board observation when a usable board is available.
- Snapshot 2 is the calculated midpoint between Snapshot 1 and the first T-20 review.
- Use a minimum 60-minute separation where possible.
- The latest intended Snapshot 2 target is 60 minutes before T-20.
- If Snapshot 2 is missed, record `SNAPSHOT_2_MISSED`.
- Never backfill or fabricate a projection observation.
- Snapshot 3 is the T-20 observation, targeting the T-25 to T-20 window.
- Late Snapshot 3 execution is recorded honestly with actual timestamps and provenance.

### Confidence and Ranking

- Do not invent numerical confidence weights or a fake objective scoring formula.
- High, Medium, and Low use the frozen evidence-based definitions.
- Senior status gives genuine priority among qualifying candidates.
- Evidence orders candidates within the Senior group.
- Non-Seniors rank by overall evidence.
- Approximately equal non-Senior candidates may be resolved by agent discretion with an explanation and audit evidence.

### Odds API Verification

- Live verification on 2026-11-14 succeeded.
- Provider: The Odds API.
- Region: `us_dfs`.
- Bookmakers: `prizepicks`, `underdog`.
- Verified live markets: `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, `player_rebounds_assists`.
- DFS outcomes do not expose stable player IDs; a canonical local registry is required.
- `THREE_POINT_ATTEMPTS` remains outside the live MVP.
- Verification began with 500 credits and 495 remained after verification.
- `THE_ODDS_API_KEY` is supplied only through the environment.
- Never store, log, print, commit, or place the API key in receipts.
- The live secret key itself is not an implementation artifact or blocker.

### Authorization Universe

- Joseph's existing approved player/category/direction universe is authoritative.
- Implementation may encode that frozen universe directly.
- Trust lists never create authorization.
- Unknown or ambiguous identity mappings fail closed.
- Malik Monk remains registered but unselectable because category and direction are unresolved.

### Result Authority

- Prefer a legitimately available platform-settled outcome.
- Support `HIT`, `MISS`, `PUSH/VOID`, and `RESULT UNAVAILABLE`.
- DNP/void is never `MISS`.
- If automated authoritative settlement is unavailable, manual result entry with provenance and receipt is allowed.
- If a trustworthy outcome cannot be established, use `RESULT UNAVAILABLE`.
- This is not an unresolved blocker.

## Review Focus

These are the inputs most likely to break the system even when the happy path passes. Each gets a dedicated test in the owning milestone.

1. **Ambiguous provider names:** two players normalize to the same registry candidate, or a known player appears under a new spelling. Expected behavior: fail closed with `PLAYER_IDENTITY_UNRESOLVED`; never guess.
2. **Missing or exposed API key:** `THE_ODDS_API_KEY` absent, malformed, echoed in logs, or embedded in a receipt URL. Expected behavior: fail closed; key never appears in output or persisted evidence.
3. **Duplicate or late snapshots:** repeated collection for the same slot, out-of-order slots, or a missed midpoint. Expected behavior: idempotent duplicate handling; missed slots recorded, never reconstructed.
4. **T-20 boundary and late news:** T-20 check too early, unavailable, or materially changed by a late scratch. Expected behavior: refuse false T-20 completion; emit `T20_CHECK_UNAVAILABLE` or downgrade/remove without forced replacement.
5. **Unavailable or non-player results:** DNP, void, postponed game, team score only, or no trustworthy settlement. Expected behavior: `RESULT UNAVAILABLE` or `PUSH/VOID`; never `MISS` and never infer from team scores.

## Proposed Project Structure

```text
CIDM6333-project/
├── pyproject.toml
├── uv.lock
├── AGENTS.md
├── config/
│   └── fifth-pick/
│       ├── approved-universe.yaml
│       ├── trust-tiers.yaml
│       ├── methodology.yaml
│       ├── governance.yaml
│       ├── category-map.yaml
│       └── approved-sources.yaml
├── src/
│   └── fifth_pick/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── controller.py
│       ├── config.py
│       ├── models.py
│       ├── errors.py
│       ├── receipts.py
│       ├── storage.py
│       ├── registry.py
│       ├── identity.py
│       ├── authorization.py
│       ├── snapshots.py
│       ├── evidence.py
│       ├── methodology.py
│       ├── ranking.py
│       ├── t20.py
│       ├── finalization.py
│       ├── approval.py
│       ├── results.py
│       └── sources/
│           ├── __init__.py
│           ├── base.py
│           ├── transport.py
│           ├── odds_api.py
│           ├── normalize.py
│           ├── quota.py
│           └── fixtures.py
├── tests/
│   ├── fixtures/
│   └── test_*.py
├── docs/
│   ├── adr/
│   │   └── ADR-2-fifth-pick-mvp.md
│   └── fifth-pick/
│       ├── architecture.md
│       ├── gates.md
│       ├── harness.md
│       ├── source-verification.md
│       ├── assurance.md
│       └── runbook.md
├── .opencode/
│   ├── agents/
│   │   ├── fifth-pick-planner.md
│   │   ├── fifth-pick-builder.md
│   │   └── fifth-pick-reviewer.md
│   ├── skills/
│   ├── commands/
│   │   └── fifth-pick-review.md
│   └── plugin/
└── var/
    └── fifth-pick/          # gitignored runtime artifacts
        └── runs/<run_id>/
            ├── run.json
            ├── receipts.jsonl
            ├── snapshots/
            ├── evidence/
            ├── candidates.json
            ├── final.json
            └── audit.json
```

`config/fifth-pick/` is required by spec Section 55 even though it was not in the short structural list. It holds authoritative input, not code.

## Proposed CLI Surface

- `fifth-pick health`
- `fifth-pick universe validate`
- `fifth-pick snapshot --slot 1|2|3 --slate-date YYYY-MM-DD [--live]`
- `fifth-pick analyze --run-id ID`
- `fifth-pick t20 --run-id ID`
- `fifth-pick final --run-id ID`
- `fifth-pick decide --run-id ID --action approve|reject|modify`
- `fifth-pick result record --run-id ID --selection ID`
- `fifth-pick audit show --run-id ID`

Fixture mode is the default for tests and demonstrations. `--live` requires `THE_ODDS_API_KEY`, an approved quota budget, and Joseph's live-call authorization.

## Milestones

### M1 — Foundation, Control Plane, and Gate Harness

**Goal:** Establish the smallest trustworthy foundation: a runnable package, the four mechanical gates, a narrow OpenCode permission scope, and the planner/builder/read-only-reviewer control model. M1 must not build Fifth Pick domain functionality.

**Acceptance criteria:**
- `uv sync` succeeds and the `fifth-pick` console script resolves.
- `fifth-pick health` prints deterministic JSON with version, package status, and no network or secret access; exits `0`.
- Usage errors exit `2`; blocked or operational failures exit `1`.
- The four gates run and exit `0` after a recorded baseline failure.
- OpenCode permits only `uv sync`, `uv lock`, `uv run fifth-pick health`, the four gate commands, and existing `git status`, `git diff`, and `pwd`; destructive shell commands remain denied.
- Project-local planner, builder, and reviewer role definitions exist.
- The reviewer role denies file edits/writes, shell commands, and subagent dispatch, and cannot change Builder work.
- The reviewer role declares the frozen verdict contract: `PASS`, `FAIL`, or `CONCERNS`.
- Gate and permission model is documented as the real control, not merely a prompt statement.
- No Fifth Pick domain, source, snapshot, methodology, finalization, or result code exists in M1.
- No Evolution directory changes.
- `var/fifth-pick/` is ignored.
- If repo-wide gate failures come from historical Evolution code, stop and ask Joseph instead of editing that history or adding unapproved exclusions.

**Files expected:**
- Create `pyproject.toml`
- Create `uv.lock` through `uv lock`
- Modify `.gitignore`
- Modify `opencode.json` only for the approved gate/control-plane allowlist
- Create `.opencode/agents/fifth-pick-planner.md`
- Create `.opencode/agents/fifth-pick-builder.md`
- Create `.opencode/agents/fifth-pick-reviewer.md`
- Create `.opencode/commands/fifth-pick-review.md`
- Create `src/fifth_pick/__init__.py`
- Create `src/fifth_pick/__main__.py`
- Create `src/fifth_pick/cli.py`
- Create `tests/test_cli.py`
- Create `tests/test_control_plane.py`
- Create `docs/adr/ADR-2-fifth-pick-mvp.md`
- Create `docs/fifth-pick/gates.md`
- Create `docs/fifth-pick/harness.md`

**Tests expected:**
- `test_health_returns_structured_json_and_exit_zero`
- `test_unknown_command_returns_usage_exit_code`
- `test_health_does_not_read_api_key_or_network`
- `test_console_entry_point_is_declared`
- `test_reviewer_role_denies_edit_write_bash_and_task`
- `test_reviewer_role_declares_pass_fail_concerns`
- `test_gate_permission_scope_is_narrow`

**Evidence/receipts expected:**
- `docs/fifth-pick/gates.md` records the pre-implementation failing gate and the post-M1 passing outputs.
- `docs/fifth-pick/harness.md` records role boundaries, reviewer denial, and the gate/permission model.
- ADR records packaging, Python floor, dependency policy, and gate permission scope.
- A deliberate unauthorized reviewer edit/write is denied and recorded as evidence.
- `git status --short` confirms no Evolution changes.

**Reviewer checkpoint:** The read-only reviewer reviews M1 under its own restrictions: package layout, gate evidence, permission scope, role separation, and evolution preservation. PASS required.

**Stop condition:** Do not start M2 until all four gates pass, the reviewer returns PASS, Joseph accepts the gate/control-plane permission scope, and no Evolution files changed.

---

### M2 — Domain Model, Receipts, and Run Storage

**Goal:** Establish the typed vocabulary and append-only evidence store used by every later milestone.

**Acceptance criteria:**
- Typed models cover observations, candidates, snapshots, evidence, decisions, results, and reason codes.
- Reason codes include all frozen fail-closed states, `RESULT UNAVAILABLE`, and `SNAPSHOT_2_MISSED`.
- Receipts use JSON Lines with timestamp, event, result, subject, source, reason, and run ID.
- Writes are atomic and idempotent for the same run/event key.
- Secret redaction is centralized and tested.
- No network access in this milestone.

**Files expected:**
- Create `src/fifth_pick/models.py`
- Create `src/fifth_pick/errors.py`
- Create `src/fifth_pick/receipts.py`
- Create `src/fifth_pick/storage.py`
- Create `tests/test_models.py`
- Create `tests/test_receipts.py`
- Create `tests/test_storage.py`
- Update `docs/fifth-pick/architecture.md`

**Tests expected:**
- `test_receipt_requires_core_fields`
- `test_receipt_redacts_api_key_and_url_query`
- `test_duplicate_event_is_idempotent`
- `test_atomic_write_leaves_no_partial_file`
- `test_reason_codes_are_complete`
- `test_run_directory_layout_is_deterministic`

**Evidence/receipts expected:**
- Sample JSONL receipt schema in `docs/fifth-pick/architecture.md`.
- Test-created run directory under a temporary path; no committed runtime artifacts.

**Reviewer checkpoint:** Reviewer checks schema completeness, idempotency, redaction, and absence of network/secret access.

**Stop condition:** Do not start M3 or M4 until receipt/storage tests pass and the reviewer returns PASS.

---

### M3 — Config, Canonical Registry, Identity, and Authorization

**Goal:** Enforce Joseph's universe before any methodology runs.

**Acceptance criteria:**
- Load and validate six authoritative YAML configs with version/effective-date metadata.
- Encode Joseph's existing approved player/category/direction universe directly.
- Preserve universe provenance and version; do not infer authorization from trust tiers or config defaults.
- Unknown, duplicate, or ambiguous player identity fails closed.
- No name-only matching is sufficient; provider names require a canonical mapping.
- Authorization is exact on player, category, and direction.
- Trust tiers never add authorization.
- Malik Monk remains in the registry but is unselectable.
- `THREE_POINT_ATTEMPTS` is denied for live MVP evaluation.
- One player can never occupy two final selections.
- Outside-universe candidates are rejected before evidence analysis.

**Files expected:**
- Create `src/fifth_pick/config.py`
- Create `src/fifth_pick/registry.py`
- Create `src/fifth_pick/identity.py`
- Create `src/fifth_pick/authorization.py`
- Create `config/fifth-pick/*.yaml` from the frozen authoritative universe
- Create `tests/fixtures/registry/` test registry and provider-name fixtures
- Create `tests/test_config.py`
- Create `tests/test_identity.py`
- Create `tests/test_authorization.py`
- Update `docs/fifth-pick/architecture.md`

**Tests expected:**
- `test_missing_required_config_fails_closed`
- `test_unknown_player_is_denied`
- `test_ambiguous_provider_name_is_unresolved`
- `test_name_only_match_is_insufficient`
- `test_trust_tier_does_not_authorize`
- `test_malik_monk_is_registered_but_denied`
- `test_three_point_attempts_is_outside_live_mvp`
- `test_unauthorized_direction_is_denied`
- `test_one_player_one_slot_constraint`

**Evidence/receipts expected:**
- Authorization receipts for allow and deny cases, including reason codes.
- A registry report seeded from the frozen authoritative universe, plus deny receipts for unknown and ambiguous identities.

**Reviewer checkpoint:** Reviewer checks that no trust path, name fallback, or config default can expand authorization.

**Stop condition:** Do not start live identity resolution until registry fixtures pass, every ambiguous provider mapping fails closed, and the reviewer returns PASS.

---

### M4 — Source Adapter, Live Client, Redaction, and Quota

**Goal:** Retrieve and normalize approved board data without leaking the key or exceeding budget.

**Acceptance criteria:**
- Source adapter uses The Odds API `us_dfs` with bookmakers `prizepicks` and `underdog`, and keeps their observations separate.
- Only the five verified live markets are requested: `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, `player_rebounds_assists`.
- `THREE_POINT_ATTEMPTS` and alternate markets are never requested by default.
- The adapter tolerates DFS outcomes without stable player IDs and hands identity resolution to the canonical registry.
- `THE_ODDS_API_KEY` is read from the environment only.
- URLs, receipts, errors, and logs redact the key.
- Response provenance includes source update time, system retrieval time, raw payload hash, and request timestamp.
- `x-requests-remaining`, `x-requests-used`, and `x-requests-last` are captured when present.
- The 2026-11-14 verification baseline is recorded: 500 credits at start, 495 after verification.
- Missing key, unauthorized response, malformed payload, and quota exhaustion fail closed.
- Live smoke is opt-in, requires an explicit credit budget, and cannot run in unit tests.

**Files expected:**
- Create `src/fifth_pick/sources/base.py`
- Create `src/fifth_pick/sources/transport.py`
- Create `src/fifth_pick/sources/odds_api.py`
- Create `src/fifth_pick/sources/normalize.py`
- Create `src/fifth_pick/sources/quota.py`
- Create `src/fifth_pick/sources/fixtures.py`
- Create `tests/fixtures/odds_api/` from a redacted verified payload
- Create `tests/test_odds_api.py`
- Create `tests/test_normalize.py`
- Create `tests/test_quota.py`
- Create `docs/fifth-pick/source-verification.md`

**Tests expected:**
- `test_missing_api_key_fails_without_echo`
- `test_url_redaction_removes_key`
- `test_us_dfs_markets_are_exact`
- `test_prizepicks_and_underdog_remain_separate`
- `test_threes_market_is_rejected`
- `test_alternate_markets_are_not_requested`
- `test_quota_headers_are_recorded`
- `test_quota_budget_exhaustion_blocks_request`
- `test_malformed_payload_fails_closed`
- `test_live_mode_is_not_used_by_tests`

**Evidence/receipts expected:**
- `docs/fifth-pick/source-verification.md` records redacted URL, timestamp, status, bookmakers, markets, event IDs, redacted headers, payload hash, quota, and the 500 → 495 verification baseline.
- Fixture hash and retrieval provenance for deterministic tests; the live secret key is not an artifact.
- Missing key or missing live-call budget fails closed before a request.

**Reviewer checkpoint:** Reviewer checks key non-exposure, market exactness, platform separation, quota control, and live-test exclusion.

**Stop condition:** Do not run a live request until `THE_ODDS_API_KEY` is present, live smoke is explicitly authorized, and a credit budget is configured. Do not substitute another provider.

---

### M5 — Snapshot Workflow and Idempotent Collection

**Goal:** Collect exactly three legitimate observations with T-20 as Snapshot 3.

**Acceptance criteria:**
- Snapshot 1 is the first legitimate successful board observation when a usable board is available.
- Snapshot 2 is the calculated midpoint between Snapshot 1 and the first T-20 review.
- Snapshot 2 uses a minimum 60-minute separation where possible; the latest intended target is 60 minutes before T-20.
- A missed Snapshot 2 is recorded as `SNAPSHOT_2_MISSED`, never reconstructed.
- Snapshot 3 is the T-20 observation, targeting the T-25 to T-20 window.
- Late Snapshot 3 execution is recorded honestly with actual timestamps; it never fabricates a T-20 time.
- Duplicate collection for the same run/slot/key returns the existing observation.
- Out-of-order or missed slots are recorded, never reconstructed.
- No backfill command exists.
- Each snapshot retains platform, player, category, projection, direction, event, source time, retrieval time, snapshot number, and provenance hash.
- Supporting-source refreshes never create extra projection snapshots.

**Files expected:**
- Create `src/fifth_pick/snapshots.py`
- Create `tests/test_snapshots.py`
- Update `docs/fifth-pick/runbook.md`

**Tests expected:**
- `test_snapshot_1_uses_first_legitimate_success`
- `test_snapshot_2_is_midpoint_with_60_minute_floor_where_possible`
- `test_snapshot_2_latest_target_is_60_minutes_before_t20`
- `test_snapshot_2_missed_records_reason_code`
- `test_duplicate_snapshot_is_idempotent`
- `test_missed_slot_is_recorded_not_backfilled`
- `test_out_of_order_slot_is_rejected`
- `test_snapshot_3_uses_t25_to_t20_window`
- `test_late_snapshot_3_is_recorded_honestly`
- `test_supporting_refresh_does_not_add_snapshot`
- `test_snapshot_provenance_is_complete`

**Evidence/receipts expected:**
- Snapshot ledger under `var/fifth-pick/runs/<run_id>/snapshots/`.
- Receipt for accepted, duplicate, missed, late, and rejected snapshots.

**Reviewer checkpoint:** Reviewer checks idempotency, no-backfill guarantee, Snapshot 1/2 targets, T-25 to T-20 Snapshot 3 target, honest late recording, and provenance.

**Stop condition:** Do not start methodology evaluation until snapshot policy tests pass and the reviewer returns PASS.

---

### M6 — Evidence, Methodology, Confidence, and Ranking

**Goal:** Apply the frozen methodology only after authorization and snapshot integrity are established.

**Acceptance criteria:**
- Stages are explicit: board retrieval, identity, authorization, matchup/context, role/minutes, Senior priority, non-Senior showoff heuristic, category trust, foul-trouble caution, confidence, ranking.
- Considers last-8 performance, same-season H2H where available, game totals/spreads, blowout risk, and approved supporting evidence with provenance.
- Missing evidence yields a named fail-closed reason and cannot be converted into confidence.
- High, Medium, and Low use the frozen evidence-based definitions; no numerical weight or fake objective score is introduced.
- Senior status is a genuine ranking tier, not a small bonus.
- Evidence orders candidates within the Senior group; non-Seniors rank by overall evidence.
- Approximately equal non-Senior candidates may be resolved by agent discretion with an explanation and audit evidence.
- Senior LOWER requires strong contextual support and at least MEDIUM confidence.
- Foul trouble is a caution signal, not an automatic MEDIUM cap.
- Trust tiers affect evaluation only.
- Ranking never adds unauthorized candidates or fills slots.
- Every candidate has an audit record with evidence, exclusions, rules, and ranking reason.
- The system can output zero qualified candidates.

**Files expected:**
- Create `src/fifth_pick/evidence.py`
- Create `src/fifth_pick/methodology.py`
- Create `src/fifth_pick/ranking.py`
- Create `tests/fixtures/evidence/`
- Create `tests/test_evidence.py`
- Create `tests/test_methodology.py`
- Create `tests/test_ranking.py`
- Update `docs/fifth-pick/architecture.md`

**Tests expected:**
- `test_missing_evidence_produces_named_reason`
- `test_last8_h2h_and_game_environment_are_recorded`
- `test_supporting_evidence_requires_approved_source_and_provenance`
- `test_nba_stats_endpoint_is_rejected`
- `test_senior_priority_beats_ordinary_non_senior`
- `test_evidence_orders_candidates_within_senior_group`
- `test_senior_lower_requires_support`
- `test_foul_trouble_is_not_automatic_medium_cap`
- `test_no_numeric_confidence_weights_are_required`
- `test_near_tie_non_senior_discretion_requires_explanation`
- `test_trust_tier_affects_ranking_not_authorization`
- `test_ranking_cannot_add_unauthorized_player`
- `test_zero_qualified_candidates_is_valid`
- `test_candidate_audit_trail_is_complete`

**Evidence/receipts expected:**
- Candidate audit records with evidence, rules, exclusions, confidence, and ranking.
- `candidates.json` for fixture runs.

**Reviewer checkpoint:** Reviewer checks methodology fidelity, no invented evidence or numeric weights, Senior priority, evidence ordering, audited near-tie discretion, trust isolation, and no-fill behavior.

**Stop condition:** Do not start T-20 until methodology tests pass and the reviewer returns PASS. Do not add a numerical confidence formula or fake objective score.

---

### M7 — T-20 Review

**Goal:** Perform the mandatory final pregame review and block stale or unavailable finalization.

**Acceptance criteria:**
- T-20 rechecks projection, movement, availability, role, teammate absences, game environment, and blowout risk.
- Conclusions are only `STILL STRONG`, `DOWNGRADED`, or `REMOVE RECOMMENDED`.
- Unavailable T-20 evidence produces `T20_CHECK_UNAVAILABLE`.
- A removed candidate never triggers forced replacement.
- Joseph remains final authority.
- T-20 receipt captures what changed and why.

**Files expected:**
- Create `src/fifth_pick/t20.py`
- Create `tests/test_t20.py`
- Update `docs/fifth-pick/runbook.md`

**Tests expected:**
- `test_t20_requires_snapshot_three`
- `test_t20_unavailable_blocks_finalization`
- `test_t20_can_downgrade_candidate`
- `test_t20_can_remove_candidate_without_replacement`
- `test_t20_conclusion_vocabulary_is_closed`
- `test_late_scratch_produces_removal_or_unavailable`

**Evidence/receipts expected:**
- T-20 receipt with before/after state, evidence sources, and conclusion.
- Updated candidate audit trail.

**Reviewer checkpoint:** Reviewer checks mandatory T-20, closed vocabulary, no false completion, and no forced replacement.

**Stop condition:** Do not start finalization until T-20 tests pass and the reviewer returns PASS.

---

### M8 — Finalization, Ceilings, and Joseph Approval

**Goal:** Produce a ranked final slate or no-entry result and require Joseph's explicit decision.

**Acceptance criteria:**
- Ceilings: HALF 1–4 / max 4; FULL 5+ / max 5.
- No player appears twice.
- No slot is filled merely to reach a ceiling.
- Zero qualified candidates produces exactly `NO ENTRY RECOMMENDED TODAY.`
- Finalization is blocked without a valid T-20 review.
- Joseph must issue `APPROVE`, `REJECT`, or `MODIFY` through the explicit `fifth-pick decide` path.
- Approval receipt records decision, timestamp, run ID, and slate version.
- Final output is compact; audit output is detailed.
- No submission or wagering path exists.

**Files expected:**
- Create `src/fifth_pick/finalization.py`
- Create `src/fifth_pick/approval.py`
- Update `src/fifth_pick/cli.py`
- Create `tests/test_finalization.py`
- Create `tests/test_approval.py`
- Update `docs/fifth-pick/runbook.md`

**Tests expected:**
- `test_half_slate_maximum_is_four`
- `test_full_slate_maximum_is_five`
- `test_zero_candidates_outputs_exact_no_entry`
- `test_finalization_blocked_without_t20`
- `test_one_player_cannot_occupy_two_slots`
- `test_approval_is_required_before_official_final`
- `test_reject_and_modify_are_recorded`
- `test_final_output_contains_no_secret_or_raw_payload`

**Evidence/receipts expected:**
- `final.json`, approval receipt, and audit trail.
- Gate evidence updated.

**Reviewer checkpoint:** Reviewer checks ceilings, no-fill discipline, one-player-one-slot, T-20 dependency, and approval gate.

**Stop condition:** Do not start result grading until finalization and approval tests pass, the approval receipt matches the frozen `APPROVE`/`REJECT`/`MODIFY` contract, and the reviewer returns PASS.

---

### M9 — Result Grading

**Goal:** Grade outcomes only when trustworthy results exist.

**Acceptance criteria:**
- Outcomes are `HIT`, `MISS`, `PUSH/VOID`, or `RESULT UNAVAILABLE`.
- DNP/void is never `MISS`.
- Team scores are never treated as player results.
- Manual result entry requires provenance and receipt.
- Fixture results are deterministic and marked as fixtures.
- Grading compares against the exact selection state Joseph approved.
- Missing result evidence fails closed.

**Files expected:**
- Create `src/fifth_pick/results.py`
- Create `tests/test_results.py`
- Update `docs/fifth-pick/runbook.md`

**Tests expected:**
- `test_hit_and_miss_require_trustworthy_result`
- `test_dnp_is_not_miss`
- `test_void_is_push_or_void`
- `test_team_score_is_not_player_result`
- `test_manual_result_requires_provenance`
- `test_missing_result_is_unavailable`
- `test_grading_uses_approved_selection_state`

**Evidence/receipts expected:**
- Result receipt with source, timestamp, provenance, and outcome.
- Audit trail distinguishes prediction quality from settlement availability.

**Reviewer checkpoint:** Reviewer checks outcome vocabulary, DNP/void handling, provenance, and no fabricated settlement.

**Stop condition:** Do not start harness integration until result tests pass and the reviewer returns PASS.

---

### M10 — Harness Hardening, Feature-Specific Skills, and Hooks

**Goal:** Harden the M1 control plane with defense-in-depth enforcement, feature-specific skills, and the mechanical review loop. M10 does not create the initial role model; M1 does.

**Acceptance criteria:**
- The M1 planner/builder/read-only-reviewer baseline remains in force.
- Reviewer returns one typed verdict: `PASS`, `FAIL`, or `CONCERNS`.
- Malformed or unknown verdicts fail closed.
- Exactly one correction attempt is allowed after `FAIL`; second failure escalates to Joseph.
- `CONCERNS` never auto-`PASS`.
- Hooks and permissions block shell-write bypasses equivalent to edit bypasses.
- Project-local skills cover evaluation, evidence validation, final-slate review, and T-20 review.
- Assurance table pairs each risk with a real control and evidence.
- AGENTS.md continues to name real enforcers, not prompts.

**Files expected:**
- Update `.opencode/agents/fifth-pick-planner.md` only for hardening
- Update `.opencode/agents/fifth-pick-builder.md` only for hardening
- Update `.opencode/agents/fifth-pick-reviewer.md` only for hardening
- Update `.opencode/commands/fifth-pick-review.md`
- Create `.opencode/skills/evaluate-candidate/SKILL.md`
- Create `.opencode/skills/validate-evidence/SKILL.md`
- Create `.opencode/skills/final-slate-review/SKILL.md`
- Create `.opencode/skills/t20-review/SKILL.md`
- Modify `.opencode/plugin/` with the approved read-only/review-loop control
- Modify `opencode.json` for approved hardened Fifth Pick permissions
- Create `src/fifth_pick/review.py`
- Create `tests/test_review_loop.py`
- Create `docs/fifth-pick/assurance.md`
- Update `docs/fifth-pick/harness.md`
- Update `AGENTS.md` only to point at the new real enforcers

**Tests expected:**
- `test_reviewer_cannot_edit`
- `test_malformed_verdict_fails_closed`
- `test_concerns_does_not_pass`
- `test_one_correction_then_escalation`
- `test_shell_write_bypass_is_denied`
- `test_assurance_table_has_control_and_evidence_per_risk`

**Evidence/receipts expected:**
- Reviewer verdict receipts.
- Correction counter and escalation receipt.
- Assurance table in `docs/fifth-pick/assurance.md`.

**Reviewer checkpoint:** Reviewer checks that every claimed control is mechanical and that no permission bypass remains.

**Stop condition:** Do not declare the harness complete until a deliberately malformed verdict fails closed and a deliberately unauthorized edit/write is denied.

---

### M11 — Course Closeout, Demo, and Assurance

**Goal:** Prove the MVP is complete, bounded, reproducible, and honest about what is live versus fixture.

**Acceptance criteria:**
- All four gates pass from a clean checkout.
- A deterministic fixture run demonstrates board → identity → authorization → snapshots → methodology → T-20 → final → approval → result.
- A limited live pilot is run only if Joseph authorizes it and quota allows; live and fixture evidence are clearly separated.
- `docs/adr/ADR-2-fifth-pick-mvp.md` records final architecture decisions and deviations.
- `docs/fifth-pick/assurance.md`, `gates.md`, `source-verification.md`, and `runbook.md` are complete.
- Evolution 00–08 are untouched.
- No secrets, credentials, or raw key-bearing URLs are committed.
- No submission, wager, login, or money-movement capability exists.

**Files expected:**
- Update `docs/adr/ADR-2-fifth-pick-mvp.md`
- Update `docs/fifth-pick/architecture.md`
- Update `docs/fifth-pick/gates.md`
- Update `docs/fifth-pick/source-verification.md`
- Update `docs/fifth-pick/assurance.md`
- Update `docs/fifth-pick/runbook.md`
- Create `docs/fifth-pick/demo.md`
- Update `tests/` only for final integration gaps
- Update `AGENTS.md` only if a real enforcer changed

**Tests expected:**
- `test_end_to_end_fixture_workflow`
- `test_no_live_call_without_explicit_flag_and_key`
- `test_gate_evidence_matches_current_commit`
- `test_evolution_directories_are_unmodified`
- `test_runtime_artifacts_are_gitignored`
- `test_no_secret_material_in_tracked_files`

**Evidence/receipts expected:**
- Final gate output, demo receipt, assurance table, live-pilot evidence if authorized, and reviewer verdict.
- A final `git status --short` with only intended files and no runtime artifacts.

**Reviewer checkpoint:** Full read-only review against PRD, frozen spec, AGENTS.md, and course requirements. PASS required.

**Stop condition:** Stop and report to Joseph. Do not commit unless Joseph explicitly requests it.

## Milestone Order

1. M1 — Foundation, control plane, permissions, gates
2. M2 — Domain, receipts, storage
3. M3 — Config, registry, identity, authorization
4. M4 — Source adapter, live client, redaction, quota
5. M5 — Snapshot workflow
6. M6 — Evidence, methodology, confidence, ranking
7. M7 — T-20 review
8. M8 — Finalization, ceilings, approval
9. M9 — Result grading
10. M10 — Harness hardening, feature skills, hooks
11. M11 — Course closeout, demo, assurance

## Dependency Order

```text
M1 -> M2
M2 -> M3
M2 -> M4
M3 + M4 -> M5
M5 -> M6
M6 -> M7
M7 -> M8
M8 -> M9
M1 -> M10 (hardening may begin after M1; final integration after M9)
M9 + M10 -> M11
```

M1 establishes the control plane before any domain implementation. M3 and M4 may run in parallel after M2. M10 may harden the M1 controls in parallel, but it must not weaken them and its final integration waits for M9. M11 is last.

## Exact First Milestone

**M1 — Foundation, Control Plane, and Gate Harness.**

**Scope:** Packaging, mechanical gates, narrow permissions, minimum planner/builder/read-only-reviewer model, documentation, and preservation checks. No Fifth Pick domain functionality.

**Files expected:**
- Create `pyproject.toml`
- Create `uv.lock`
- Modify `.gitignore`
- Modify `opencode.json` for the approved gate/control-plane allowlist only
- Create `.opencode/agents/fifth-pick-planner.md`
- Create `.opencode/agents/fifth-pick-builder.md`
- Create `.opencode/agents/fifth-pick-reviewer.md`
- Create `.opencode/commands/fifth-pick-review.md`
- Create `src/fifth_pick/__init__.py`
- Create `src/fifth_pick/__main__.py`
- Create `src/fifth_pick/cli.py`
- Create `tests/test_cli.py`
- Create `tests/test_control_plane.py`
- Create `docs/adr/ADR-2-fifth-pick-mvp.md`
- Create `docs/fifth-pick/gates.md`
- Create `docs/fifth-pick/harness.md`

**Acceptance criteria:**
- `uv sync` succeeds and `fifth-pick health` returns deterministic JSON without network or secret access.
- All four gates exit `0` after the baseline failure is recorded.
- `opencode.json` allows only `uv sync`, `uv lock`, `uv run fifth-pick health`, the four gates, and existing `git status`, `git diff`, and `pwd`.
- Reviewer role denies edit/write, bash, and subagent dispatch; reviewer cannot change Builder work.
- Reviewer role declares `PASS`, `FAIL`, or `CONCERNS`.
- Gate and permission model is documented as a real control.
- No Fifth Pick domain, source, snapshot, methodology, finalization, or result code exists.
- Evolution 00–08 are unchanged; `var/fifth-pick/` is ignored.
- No secret, network, submission, wager, login, or money-movement path exists.

**Reviewer checkpoint:** The M1 reviewer, operating under its read-only role, checks package layout, gate evidence, permission scope, role separation, and evolution preservation. PASS required.

**M1 stops immediately after:** gates pass, reviewer PASS, Joseph accepts the gate/control-plane permission scope, and `git status --short` shows no Evolution changes. No domain, source, snapshot, or methodology work starts before that stop.

## Remaining Genuine Blockers

Only these currently prevent M1.

1. **Implementation authorization:** Joseph has not authorized implementation. The revised M1 scope and permission change must be explicitly authorized before execution.
2. **Repo-wide gate baseline:** The four required commands may still fail on historical Evolution code after the root package exists. Joseph must approve a narrow reconciliation if that occurs. Editing Evolution 00–08 to make gates pass is prohibited.

No snapshot, confidence/ranking, Odds API, authorization-universe, or result-authority question blocks implementation; those are frozen in this plan.

Course deadline, grading, and presentation details remain administrative items. They do not block M1 unless a concrete technical dependency appears. Live-call quota and explicit live-smoke authorization are M4 operational gates, not M1 design blockers.

## Scope Guard

Do not add: user accounts, web UI, database server, payments, odds shopping, automated wagering, alternate-market expansion, paid data providers, machine-learning models, or a general-purpose betting platform. The MVP is a disciplined, auditable CLI for Joseph's frozen methodology.

## Stop

Plan only. No production code, tests, permissions, hooks, OpenCode configuration, agents, or commits were created or changed by this planning step. Stop for Joseph's review.

## Post-Checkpoint Authorization Addendum (2026-11-14)

After the checkpoint recorded above, Joseph explicitly authorized proceeding with M1 implementation. Joseph's subsequent instruction authorizes only the five bounded M1 reviewer remediations and final M1 review in the current task. This later authorization supersedes the earlier authorization status in `Remaining Genuine Blockers` and the earlier design-phase status in `docs/PRD.md`; it does not authorize M2, domain functionality, or a commit. The earlier checkpoint records are retained as historical evidence.

## M2 Authorization Addendum (2026-11-15)

After M1 passed its independent reviewer checkpoint and commit `8c7d01e` was created, Joseph explicitly authorized M2 only: domain models, typed errors, receipts, and run storage. This supersedes the M1-only authorization above for M2 and does not authorize M3 or later work, changes to Evolution 00–08 or the frozen design specification, or a commit. The M1 checkpoint and authorization records remain unchanged.

## M3 Authorization Addendum (2026-11-15)

Joseph explicitly authorizes M3 only: configuration loading, canonical registry, identity resolution, and authorization validation. The existing approved player universe in frozen-design Part II 9.1 is version `v1`, effective `2026-11-15`; its entries must not be changed. Apply Part III A1/A2 direction rules and E4/E5 authorization rules. This supersedes the M2-only authorization above for M3. It does not authorize M4 or later work, Evolution changes, frozen-spec changes, or a commit.
