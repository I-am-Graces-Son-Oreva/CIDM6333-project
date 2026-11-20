# M6 Trust-Boundary Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the three latest independent M6 review recommendations without changing methodology or entering M7.

**Architecture:** Ranking and persistence accept only `CandidateCase` tuples and invoke the existing methodology evaluator internally, consuming its local canonical audits immediately. Remove the reusable result type/seal entirely. Require LIVE cases to identify an M5 run and resolve it under application-owned `APPLICATION_STORAGE_ROOT` through M5's `read_application_snapshot_ledger()` path, including exact source records and accepted/missed receipts. No caller workflow, RunStore root, or reader is accepted for LIVE authentication. Keep the fixture path explicit and offline. Canonicalize history by `(played_at, opponent, season)`, deduplicating identical rows and rejecting conflicting values.

**Tech Stack:** Python, `uv`, Ruff, `ty`, and `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-13-fifth-pick-design.md`; M5/M6 acceptance details are in `docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md`.

## Global Constraints

- Preserve approved M1-M6 behavior and Governance Zero.
- Do not modify Evolution 00-08 or the frozen design.
- Do not make live network/API calls or begin M7.
- Do not add finalization, wagering, login, submission, or autonomous replacement.
- Do not commit or push.
- Use offline `unittest`; do not use pytest.
- Run `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, and `uv run python -m unittest discover -s tests` before the single final reviewer.

## Review Focus

- Caller-created audit batches or result-shaped objects must not reach ranking or `candidates.json`; ranking and persistence accept cases only.
- LIVE snapshots with fabricated provenance or a mismatching M5 run ledger must fail closed; fixture cases retain the explicit offline path.
- Repeated records for one historical game must not count twice; conflicting values for the same game identity must fail closed.
- Existing forged status, confidence, authorization, evidence, history, gaps, provenance, and snapshot-path cases must remain outside the ranking trust boundary.
- No source calls, methodology changes, M7 paths, or changes to frozen/history documents may occur.

---

### Task 1: Adversarial Regressions

**Files:**
- Modify: `tests/test_ranking.py`
- Modify: `tests/test_methodology.py`
- Modify: `tests/test_evidence.py`

**Interfaces:** Use the current M6 ranking/evidence APIs to demonstrate each gap before production changes.

- [ ] Add tests proving extracted fields from a legitimate methodology output and caller-created result-shaped wrappers cannot make forged audits rankable or persistable.
- [ ] Add LIVE cases with well-formed but fabricated provenance and with records that do not match an existing M5 run; assert fail-closed behavior while fixture cases still work.
- [ ] Add exact duplicate and conflicting duplicate history-sample cases; assert duplicates cannot change history summaries or relative ranking.
- [ ] Run the focused `unittest` modules and confirm each new regression fails for the intended defect.

### Task 2: Internal Methodology Evaluation and M5 Origin

**Files:**
- Modify: `src/fifth_pick/methodology.py`
- Modify: `src/fifth_pick/ranking.py`
- Modify: `tests/test_methodology.py`
- Modify: `tests/test_ranking.py`

**Interfaces:** Keep `CandidateCase.snapshot_run_id: str | None`; ranking accepts case tuples only, and persistence's `RunStore` is for output only. LIVE storage root is the application-owned `APPLICATION_STORAGE_ROOT`; `read_application_snapshot_ledger(run_id)` internally constructs the M5 store and validates ledger plus receipts. Fixture snapshots need no ledger.

- [ ] Remove `MethodologyResult`, its seal, and the result factory; no caller-held result type is part of the ranking API.
- [ ] Have `rank_candidates()` invoke `evaluate_candidate()` internally for each case, and have `write_candidates()` use that same path.
- [ ] Resolve LIVE cases by `snapshot_run_id` through M5-owned application storage; require ledger records, provenance, and receipts; reject absent/mismatched runs. No caller-selected store/root reaches this read path.
- [ ] Run focused methodology, ranking, and snapshot tests.

### Task 3: Performance-Sample Canonicalization

**Files:**
- Modify: `src/fifth_pick/evidence.py`
- Modify: `tests/test_evidence.py`
- Modify: `tests/test_ranking.py`

**Interfaces:** Historical sample identity is `(played_at, opponent, season)`. Identical repeated rows collapse to one; repeated identity with differing values raises `EvidenceError` before any summary is computed.

- [ ] Canonicalize samples at the immutable `EvidenceItem` boundary so direct summaries and methodology evaluation share the behavior.
- [ ] Verify duplicate samples preserve summary and ranking; verify conflicting duplicates fail closed.
- [ ] Run focused evidence and ranking tests.

### Task 4: M6 Records and Full Verification

**Files:**
- Modify: `docs/fifth-pick/architecture.md`
- Modify: `docs/fifth-pick/gates.md`

- [ ] Update the mutable architecture description to match the final result, ledger-origin, and sample-identity boundaries.
- [ ] Run all four required gates, recording their actual exit status and the full unittest count before reviewer dispatch.
- [ ] Inspect changed paths and verify Evolution 00-08 and the frozen design are untouched; do not commit or push.

### Task 5: Final Independent Review

**Files:** Read-only review; no edits expected.

- [ ] Dispatch exactly one broad independent read-only M6 reviewer after all gates pass.
- [ ] Require review of the three latest structural recommendations and all historical M6 findings.
- [ ] On PASS, report the verdict, acceptance criteria, gate outputs, test count, worktree status, diff stat, changed files, and scope confirmations, then stop for Joseph.
- [ ] On FAIL, make no further edits; report the exact issue, contract status, and recommended structural solution, then stop.

## Execution Ledger

- Ruling: Keep execution in the current shared worktree — the authorized M6 implementation is already present as uncommitted and untracked work, so creating an isolated worktree would separate this remediation from the work the request says to continue; cost if wrong: concurrent edits could interleave, so only the scoped M6 files will be changed.
- Pre-flight: Task 1 produces tests consumed by Tasks 2 and 3; no implementation changes are made until its expected RED is observed. Task 4 consumes the final APIs from Tasks 2 and 3. Task 5 consumes the gate and worktree evidence from Task 4.
- Task 1 RED: `uv run python -m unittest discover -s tests` ran 293 tests and failed 31 tests, reproducing result self-registration, bypass mutation, LIVE snapshot acceptance, duplicate history strengthening, and caller-wrapped forged audit fields. No production code had been changed.
- Ruling: Keep the methodology result seal in the result factory's closure rather than a module-level private constant — an additional regression demonstrated that a caller could import the global seal and self-certify a forged result; the closure-local seal preserves the minimal immutable boundary without adding a general-purpose capability system; cost if wrong: deliberate Python reflection can still inspect closures, but no supported constructor or mutable registration path can authenticate caller data.
- Follow-up RED: After adding the module-global-seal attack, `uv run python -m unittest discover -s tests` ran 294 tests and failed 1 test. Moving result creation and validation into the private result factory closure made the suite pass at 294 tests.
- Final gates: `uv run ruff check` passed; `uv run ruff format --check` reported 79 files already formatted; `uv run ty check` passed; `uv run python -m unittest discover -s tests` ran 294 tests and passed. No live API/network call occurred.
- Ruling: Supersede the prior sealed-result design per the final independent review — transferable capabilities cannot prove methodology ownership, so ranking/persistence now accept cases only and consume internal evaluations; cost if wrong: the ranking API changes to case inputs, but no current authorized CLI exposes this API.
- Latest remediation RED: `uv run python -m unittest discover -s tests` ran 295 tests and failed 28 tests with 21 errors while ranking and persistence still required caller-held methodology results. The recovered-seal ranking and persistence regressions both reproduced the reviewer finding.
- Latest remediation GREEN: `uv run python -m unittest discover -s tests` ran 295 tests and passed after removing `MethodologyResult` and evaluating `CandidateCase` inputs inside ranking/persistence.
- Ruling: Do not accept `SnapshotWorkflow` as the M6 ledger authority — the latest reviewer showed instance method/read-state overrides can forge it; M6 now supplies only the storage locator to the M5-owned static ledger parser, and the M5 workflow delegates to that same parser; cost if wrong: the injected `RunStore` root remains the storage boundary, but no caller reader behavior is trusted.
- M5 reader RED: `uv run python -m unittest discover -s tests` ran 300 tests and failed 3 tests when overridden `read()`, `read_missed()`, and `_read_entries` could influence M6's LIVE origin check.
- Ruling: Use application-owned `var/fifth-pick` as the only LIVE M6 root and verify existing accepted/missed receipts alongside the M5 ledger — the frozen design specifies provenance, payload hashes, and receipts but no cryptographic signature; direct malicious filesystem write access is future hardening, not a new M6 signing system; cost if wrong: local filesystem authorship attacks remain outside the frozen threat model.
- Storage-ownership RED: `uv run python -m unittest discover -s tests` ran 305 tests and failed 4 tests, reproducing caller-selected RunStore authority, missing application-root resolution, external schema-valid ledger acceptance, and missing receipt rejection.
- Contract assessment: The frozen design specifies source-specific provenance, payload hashes, and receipts; the frozen M5 contract specifies the application run root and ledger/receipts, but neither requires cryptographic signing. Direct write access to the app data directory remains future OS/filesystem hardening, not an M6 signature mechanism.
