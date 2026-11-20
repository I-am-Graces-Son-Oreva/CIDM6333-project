# M9 Result Grading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record a trustworthy settlement result for only a selection in Joseph's receipt-verified approved slate, preserving the distinction between prediction outcome and unavailable settlement.

**Architecture:** M9 consumes the existing M2 `Result`, `ResultStatus`, `Provenance`, `Receipt`, and `RunStore` types. It first reads the exact M8-approved final state, then validates and persists a result tied to a selected `candidate_key`, with a result receipt and run-scoped `results.json`. M9 does not retrieve player results or create another scoring methodology; a platform or manual source supplies an already-classified settlement status, while deterministic fixtures exercise the same record path offline.

**Tech Stack:** Python 3.11+, `uv`, `ruff`, `ty`, standard-library JSON and `unittest`; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-13-fifth-pick-design.md` (Part II Section 63, A16, D6, E12, E14).

## Global Constraints

- Preserve Evolution 00–08 and all frozen methodology, authorization, identity, ranking, ceiling, and M8 approval behavior.
- Do not automate player-result retrieval. Use a legitimately available platform-settled result, a manually recorded result with provenance and receipt, or a deterministic fixture.
- Never use the Odds API scores endpoint, team scores, scraping, or an unofficial endpoint as an adjudicated player result.
- Use only the existing result vocabulary: `HIT`, `MISS`, `PUSH`, `VOID`, `DNP`, and `RESULT UNAVAILABLE`.
- Never record `HIT` or `MISS` without trustworthy result evidence. DNP, VOID, or equivalent platform cancellation is never `MISS`; uncertainty fails closed to `RESULT UNAVAILABLE`.
- Do not invent platform PUSH/VOID/stat-correction rules. Use documented source settlement; if its rule is ambiguous, preserve `RESULT UNAVAILABLE` and surface the ambiguity to Joseph.
- Results must bind to the exact approved M8 selection and slate version. No grading of a proposed, modified-but-not-approved, rejected, blocked, or no-entry slate.
- Manual result entries require provenance and a receipt. Fixture results must be deterministic and explicitly marked as fixtures.
- Result grading must preserve process/selection evidence separately from settlement availability; do not make hit-rate or methodology claims from unavailable results.
- No wager, login, submission, money movement, M10 work, or live network request.
- Use `uv`, `ruff`, `ty`, and `unittest`, not pytest. All four required gates must pass before M9 is claimed complete.
- The read-only reviewer returns `PASS`, `FAIL`, or `CONCERNS`; malformed verdicts fail closed. One correction after FAIL is allowed, then Joseph. Do not begin M10 until M9 tests and reviewer PASS.

## Joseph-Approved Evidence Amendment

Joseph explicitly approved this narrow M9 amendment after review identified that `Provenance.payload_hash` could not be checked against retained source evidence.

- Keep the M2 `Result` and `Provenance` types unchanged. Each M9 result row adds nullable `evidence_excerpt` and `evidence_confirmation` fields; its existing serialized provenance supplies the source reference and SHA-256 digest.
- For `HIT`, `MISS`, `PUSH`, `VOID`, and `DNP`, require a non-empty excerpt, provenance whose `payload_hash` equals SHA-256 of the exact stored UTF-8 excerpt, and the exact human confirmation `SETTLEMENT_CONFIRMED`. The CLI displays and explicitly names the approved player, platform, category/direction/line, event, and entered outcome in its confirmation prompt, and states that the human must check the excerpt itself. A YES is an operator attestation, not independent source authentication.
- For `RESULT UNAVAILABLE`, no excerpt or provenance is required. Optional lookup-attempt evidence is retained only when its excerpt/hash match and the operator confirms it concerns the exact approved player, platform, category/direction/line, and event with `LOOKUP_ATTEMPT_CONFIRMED`; the prompt states this does not establish a settlement outcome.
- Missing or unconfirmed determinate evidence becomes `RESULT UNAVAILABLE`, never an inferred result. Existing or tampered result rows fail closed when their excerpt, digest, provenance reference, or confirmation do not agree.
- Bind the confirmation value and excerpt digest through the `RESULT_RECORDED` receipt. A matching digest proves only that the retained excerpt is unchanged; it does not prove external-source authenticity. M9 performs no retrieval, scraping, or external validation.
- This amendment does not change the frozen design, M2 models, M1-M8 behavior, result vocabulary, or M10 boundary.

## Planning Assumptions

- M2 `Result` contains an already-classified `ResultStatus`, subject, source, recorded time, optional reason, and optional provenance; it has no raw final-stat value. This plan therefore has M9 validate and record a trustworthy settled status rather than derive HIT/MISS from a raw number. If Joseph wants numerical adjudication, the result data model and exact platform settlement rules need a separate decision before implementation; this plan does not invent either.
- The existing proposed CLI surface in the MVP plan includes `fifth-pick result record --run-id ID --selection ID`. M9 will implement that already-listed command interactively, with `--selection` identifying the M8 `candidate_key`, never a player name. This reconciles the proposed CLI surface with the M9 subsection's shorter expected-file list.
- M8's `_read_final()` already validates the proposal/decision receipt. M9 should consume that validation through a small read-only public accessor rather than duplicate M8 receipt parsing or call its private writer.
- M8 tests explicitly assert that `results.json` is absent before M9. M9 will create that run-scoped result record while keeping receipts in the existing append-only `receipts.jsonl`.

## File Map

- Modify `src/fifth_pick/approval.py` to expose read-only `load_approved_final(store, run_id)`, returning only a receipt-validated `APPROVED_BY_JOSEPH` record. It must not write or alter M8 state.
- Modify `tests/test_approval.py` to test the read-only approved-state boundary.
- Create `src/fifth_pick/results.py` for approved-selection binding, result validation, provenance serialization, result persistence, and result-receipt creation.
- Create `tests/test_results.py` for settlement, selection-integrity, provenance, idempotency, fixture, and fail-closed behavior.
- Modify `src/fifth_pick/cli.py` to add only the already-proposed interactive `result record` command.
- Modify `docs/fifth-pick/runbook.md` to document M9 entry, source/provenance requirements, artifacts, receipts, and stop conditions.
- Do not modify `src/fifth_pick/models.py`; M9 uses the existing typed `Result`/`ResultStatus`/`Provenance` contract. If that contract proves insufficient for Joseph's intended grading input, stop and get a separate design decision rather than silently extending it.

## Review Focus

1. **No approved final state:** `AWAITING_JOSEPH`, MODIFY awaiting re-approval, REJECTED, BLOCKED, or NO ENTRY cannot be graded; only the receipt-verified `APPROVED_BY_JOSEPH` state passes.
2. **Wrong selection or slate version:** a player name, game ID, candidate not in `approval.official_final`, or stale slate version fails closed; result subject is the exact `candidate_key`.
3. **Untrustworthy HIT/MISS:** missing provenance, team-score-only data, conflicting source, or unavailable settlement never produces `HIT`/`MISS`; record or require `RESULT UNAVAILABLE` with a named reason.
4. **Settlement edge cases:** DNP remains distinct and never becomes MISS; PUSH/VOID remain source-classified; uncertain platform or stat-correction behavior becomes `RESULT UNAVAILABLE` and is disclosed.
5. **Retry/fixture integrity:** identical deterministic fixture submissions are marked as fixtures and idempotent; conflicting duplicate results fail closed; receipt/artifact retries preserve the persisted receipt timestamp.

---

### Task 1: Expose the Receipt-Verified Approved Selection

**Files:**
- Modify: `src/fifth_pick/approval.py`
- Test: `tests/test_approval.py`

**Interface:**
- Produces `load_approved_final(store: RunStore, run_id: str) -> dict[str, object]`.
- It reuses `_read_final()` and returns only when the record is `APPROVED_BY_JOSEPH`, action is `APPROVE`, `official_final` matches the approved proposal, and the matching Joseph decision receipt validates. It is read-only.

- [ ] **Step 1: Write tests** `test_load_approved_final_returns_exact_official_final`, `test_load_approved_final_requires_approved_receipt`, and `test_load_approved_final_rejects_nonapproved_states`. Assert that a valid approval returns the exact `official_final` and `slate_version`; awaiting, modified-but-unapproved, rejected, blocked, forged, and receipt-mismatched states are rejected without mutation.
- [ ] **Step 2: Run the tests to verify RED.** Run: `uv run python -m unittest tests.test_approval`. Expected: the accessor is absent and the new API tests fail.
- [ ] **Step 3: Implement `load_approved_final` in `approval.py`.** Reuse `_read_final()` validation; do not duplicate receipt parsing or add a decision-writing API.
- [ ] **Step 4: Run the tests to verify GREEN.** Run: `uv run python -m unittest tests.test_approval`.

### Task 2: Validate and Persist a Result for an Approved Selection

**Files:**
- Create: `src/fifth_pick/results.py`
- Test: `tests/test_results.py`

**Interface:**
- Produces `record_result(store: RunStore, run_id: str, selection_id: str, result: Result, *, evidence_excerpt: str | None, evidence_confirmation: str | None) -> Path`.
- `selection_id` is an M8 `candidate_key`; `result.subject` must equal it. When no trustworthy settlement exists, the CLI records an M2 `Result` with `ResultStatus.RESULT_UNAVAILABLE` and `ReasonCode.RESULT_UNAVAILABLE`; it does not synthesize settlement provenance. The service reads the approved state through `load_approved_final` and does not accept caller-supplied selections or M6 ranking results.
- `results.json` stores the run ID, approved slate version and decision receipt key, the exact approved selection record (including its original projection/line and a reference to the matching M8 T-20 audit), the typed result/status, source, timestamps, reason, provenance, nullable evidence excerpt, and evidence confirmation. A `fixture: true` marker is derived only when result provenance uses the explicit `synthetic-fixture` source and access method; it is not caller-controlled.
- M9 consumes an already-classified settlement `ResultStatus`; it does not calculate HIT/MISS from a raw numeric statistic or introduce a new threshold.
- A supplied HIT/MISS/PUSH/VOID/DNP requires player-selection-specific provenance, an excerpt whose SHA-256 matches that provenance, and explicit selection/market/outcome confirmation; a determinate status without them is rejected and cannot be persisted. The interactive command offers `RESULT UNAVAILABLE` with `ReasonCode.RESULT_UNAVAILABLE` when no trustworthy settlement is available.
- The service verifies the excerpt/hash and the status-appropriate confirmation before persistence and whenever it reads an existing row. Unavailable results may omit excerpt, provenance, and confirmation; if lookup evidence is retained, all three must be present and consistent.
- Append a `RESULT_RECORDED` receipt through M2 `RunStore`; bind its event key to run, slate version, selection key, evidence digest, and confirmation. The receipt records outcome/source/time and a compact provenance reference; `results.json` contains full `Provenance` and the exact excerpt. Reuse `AppendResult.receipt.timestamp` on retries. Same-record retries are idempotent; conflicting duplicate outcomes fail closed. Do not overwrite results to handle a stat correction without a documented policy.

- [ ] **Step 1: Write tests** for the existing settlement, selection, fixture, and retry cases, plus `test_determinate_result_requires_verified_excerpt_hash_and_confirmation`, `test_result_evidence_excerpt_and_hash_are_persisted`, `test_tampered_result_excerpt_fails_closed_on_retry`, `test_missing_determinate_evidence_fails_closed`, and `test_unavailable_result_without_evidence_is_preserved`. Verify the result receipt binds the evidence digest/confirmation and that no hash is treated as proof of source authenticity.
- [ ] **Step 2: Run the tests to verify RED.** Run: `uv run python -m unittest tests.test_results`. Expected: result-recording API and artifact are absent.
- [ ] **Step 3: Implement `results.py`.** Serialize only the existing M2 `Result` fields and validated M8 selection snapshot. Never fetch a result source, infer an outcome from team scores, apply new methodology, or invent a platform PUSH/VOID/stat-correction rule.
- [ ] **Step 4: Run the tests to verify GREEN.** Run: `uv run python -m unittest tests.test_results`.

### Task 3: Wire the Existing Result Command and Document the Flow

**Files:**
- Modify: `src/fifth_pick/cli.py`
- Modify: `tests/test_results.py`
- Modify: `docs/fifth-pick/runbook.md`

**Interface:**
- Adds only the existing proposed command `fifth-pick result record --run-id RUN_ID --selection SELECTION_ID`.
- It loads and displays the exact M8-approved selection before prompting for an already-settled `ResultStatus`. Determinate outcomes require source metadata, stable reference, a minimal evidence excerpt, its computed hash, and explicit human confirmation that it supports the displayed player, platform/market, and outcome. `RESULT UNAVAILABLE` requires the named unavailable reason; optional lookup-attempt evidence is retained only with a matching excerpt/hash and explicit selection-bound lookup confirmation. Missing, ambiguous, or unconfirmed settlement evidence remains unavailable. The selection ID is the displayed `candidate_key`. Unsupported inputs, non-approved states, and selection IDs outside `official_final` fail closed. The command makes no network request and does not change M8 final state.

- [ ] **Step 1: Write CLI tests** for exact command parsing, rejected unsupported inputs, approved selection display/binding, excerpt/hash capture, exact human confirmation, unconfirmed-result fallback to `RESULT UNAVAILABLE`, and unavailable lookup evidence. Assert `health` and `decide` behavior remain unchanged; no submit/login/wager command is introduced.
- [ ] **Step 2: Run the CLI tests to verify RED.** Run: `uv run python -m unittest tests.test_results`.
- [ ] **Step 3: Wire the command to `record_result` and document** manual/platform-settled result provenance, `results.json`, `RESULT_RECORDED`, fixture marking, no automatic result retrieval, and the no-MISS rule for DNP/VOID in the runbook.
- [ ] **Step 4: Run result tests to verify GREEN.** Run: `uv run python -m unittest tests.test_results`.

### Task 4: M9 Acceptance and Independent Review

**Files:**
- Verify the M9 files above; do not edit the frozen design or Evolution 00–08.

- [ ] **Step 1: Run all four required gates:** `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, and `uv run python -m unittest discover -s tests`. All must exit `0`.
- [ ] **Step 2: Request one independent mechanically read-only M9 review.** It checks exact approved-selection integrity, trustworthy result/provenance, DNP/VOID/PUSH/unavailable behavior, fixture labeling, receipt idempotency, no fabricated results, and M8/no-M9 boundary preservation.
- [ ] **Step 3: Stop on reviewer PASS for Joseph's review.** On FAIL, apply at most one Joseph-authorized correction cycle; a second failure stops and escalates to Joseph. Do not begin M10 until M9 tests and reviewer PASS.

## Dependencies and Risks

- **Dependencies:** M2 `Result`/`ResultStatus`/`Provenance`/`Receipt`/`RunStore`; completed M8 finalization and Joseph `APPROVE` receipt; M8 independent reviewer PASS and Joseph's review. The M8-approved-selection reader is a read-only bridge, not a state transition.
- **Settlement interpretation:** The existing M2 `Result` carries an already-classified outcome but no raw final-stat value. This plan therefore validates and records source/manual settlement status. It does not calculate HIT/MISS from raw numeric statistics. If Joseph expects numeric-stat grading, the result schema and exact classification rules need an additional decision before implementation.
- **Platform rules:** Frozen A16 leaves platform PUSH/VOID/stat-correction behavior to actual documented rules. M9 must preserve the source's settled status; ambiguity yields `RESULT UNAVAILABLE`, not a locally invented conversion. Conflicting corrections remain blocked until their authority/version semantics are specified.
- **CLI/file-list reconciliation:** The M9 subsection lists `results.py`, `test_results.py`, and runbook; the same MVP plan's proposed CLI surface includes `result record`. This plan includes `cli.py` and the read-only approval bridge so the existing command and approved-selection integrity are actually implemented.
- **Source gap:** No automated player-result provider or player-stat endpoint is authorized. The MVP path is manual provenance-bearing settlement or deterministic fixture; no team score is a player result.
