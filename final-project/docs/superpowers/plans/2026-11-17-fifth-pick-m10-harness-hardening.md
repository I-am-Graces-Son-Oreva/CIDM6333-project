# M10 Harness Hardening Implementation Plan

The opening status, phased authorizations, and original denial experiment describe historical checkpoints. For the current evidence status and remaining acceptance step, see [Task 7](#task-7-m10-acceptance-and-independent-review--accepted-with-qualification) and the dated OpenCode 1.18.20 addendum below.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement only the authorized Phase 1 tasks. Phase 2 remains blocked until Joseph separately authorizes it and the runtime evidence requirements below are satisfied.

**Goal:** Harden the existing Fifth Pick M1 control plane with a fail-closed review loop, the four approved project-local skills, and risk-to-control assurance evidence without changing M1-M9 behavior.

**Architecture:** OpenCode native permissions remain the sole authority for tool isolation. A deterministic Python review module parses typed verdicts and applies the bounded correction state machine. A narrowly scoped OpenCode plugin may support review lifecycle integration and receipts only; it must not replace, override, or weaken native permission decisions. Plugin discovery, actual activation, the supported Python bridge, and actual write-denial evidence remain blocked pending separate verification and authorization.

**Tech Stack:** Python 3.11+, `uv`, `ruff`, `ty`, built-in `unittest`, existing OpenCode configuration and plugin package. Do not add dependencies or use pytest for Fifth Pick tests.

**Specification:** `docs/superpowers/specs/2026-11-13-fifth-pick-design.md`, especially Part II Sections 49-60, Part III A18, B8/B12 research disposition, and applicable frozen governance boundaries. **Milestone roadmap:** `docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md`, M1 and M10.

**Status:** Phase 1 implementation is authorized by Joseph. Plugin integration, runtime write-denial testing, and final M10 acceptance remain **BLOCKED** pending separate authorization and required evidence.

## Joseph's Reviewed Corrections

This additive amendment records Joseph's M10 plan review. It changes only the draft interpretations and sequencing called out below; it does not change the frozen design or authorize implementation, runtime testing, package installation, commits, pushes, or external actions.

- **Plugin responsibility approved in principle:** A narrowly scoped, non-authoritative lifecycle and receipt adapter is acceptable in principle. OpenCode native permissions remain the sole authority for tool isolation. The plugin must never grant access, override a native denial, weaken native permissions, or replace Reviewer isolation. This principle does not verify or authorize a particular plugin API or implementation.
- **Host-version evidence supplied by Joseph:** Joseph independently verified from his terminal that the active `opencode` command resolves to `/usr/local/opt/opencode/bin/opencode` and reports version `1.18.20`. This is user-supplied terminal evidence, not a command run or independently verified by OpenCode. It establishes the reported host path/version only. Plugin discovery, actual activation, and the supported Python bridge remain separately unverified.
- **Denial evidence remains a strict runtime gate:** PASS requires an actual Reviewer write attempt, a correlated native permission-denied event for that attempt, and evidence that both the disposable sentinel and the entire disposable workspace remain unchanged. Missing or unavailable tools, no observed request, timeout, configuration inspection, or an unchanged file without the correlated denial are not PASS. Never weaken production permissions to manufacture evidence.
- **Review-cycle contract approved for Phase 1:** Joseph approved the deterministic identifier, M2 receipt/run binding, explicit review events, and one-correction/escalation state machine. The OpenCode/Python bridge and plugin implementation remain unapproved and blocked.
- **Sequencing:** Phase 1 is authorized, including the pure parser/state machine, approved receipt behavior, four project skills, and evidence-backed documentation. Plugin integration, actual denial testing, and final M10 acceptance remain blocked as specified below.

## Joseph's Phase 1 Authorization

Joseph authorized Phase 1 only and approved the review-cycle contract for this phase. Phase 1 covers `review.py`, its regression tests and M2-compatible receipt use, the four named project skills, and assurance/harness documentation limited to implemented and tested controls. This supersedes earlier draft statements that Phase 1 and its receipt contract were awaiting authorization. It does not authorize plugin work, a Python/OpenCode bridge, the runtime denial experiment, final M10 acceptance, M11, package installation, commits, or pushes. Native Reviewer permissions and M1-M9 behavior remain unchanged.

After Phase 1 implementation, obtain an independent mechanically read-only assessment against this plan and the frozen specification. That Phase 1 assessment is not the blocked final M10 acceptance review and does not satisfy the runtime-denial gate.

Joseph authorized one additional bounded Phase 1 correction cycle for STOPPED terminal enforcement, M2 receipt-event validation before append, and assurance evidence validation. No other Phase 1 scope, Phase 2 work, plugin work, runtime denial experiment, or final M10 acceptance is authorized by this addendum.

## Global Constraints

- Do not begin M10 until M9 has reviewer PASS and Joseph's review; then obtain the separate M10 implementation authorization described below.
- Preserve M1-M9 and Evolution 00-08. Do not alter Joseph's methodology, approved universe, evidence rules, slate decisions, or settlement behavior.
- OpenCode native permissions remain the authoritative Planner/Builder/Reviewer isolation boundary. No plugin may grant permissions, override a native deny, or become a substitute authorization system.
- A plugin may act only as a non-authoritative lifecycle and receipt adapter; native OpenCode permissions remain the sole authority for tool isolation and Reviewer read-only enforcement.
- Keep separate Planner, Builder, and mechanically read-only Reviewer roles.
- Accept only typed `PASS`, `FAIL`, or `CONCERNS`. Malformed, unknown, incomplete, or unsupported output fails closed.
- A first `FAIL` permits exactly one Builder correction attempt. A second `FAIL` escalates to Joseph. `CONCERNS` routes to Joseph and never becomes `PASS` automatically.
- No reviewer edit, Bash, task-delegation, MCP-write, shell-write, submission, login, wager, money movement, live player-result retrieval, or other unauthorized external action.
- Do not claim write-denial PASS from permission text, a missing or unavailable tool, a timeout, configuration inspection, or an unchanged file without an actual Reviewer write attempt correlated to a native denial and evidence that the sentinel and complete disposable workspace remain unchanged.
- The four required gates are `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, and `uv run python -m unittest discover -s tests`; all must exit `0` before M10 acceptance.
- No commit or push unless Joseph separately authorizes it.

## M10 Scope From the Roadmap

The MVP roadmap requires the M1 roles to remain in force; typed, fail-closed verdicts; the one-correction/escalation rule; no auto-PASS for `CONCERNS`; shell-write protection equivalent to edit protection; four project-local skills; an assurance table with real controls and evidence; and `AGENTS.md` pointing to actual enforcers. Its M10 scope and expected files/tests are in `docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md:625-672`.

M10 is harness hardening only. M11 course closeout, new basketball methodology, new data sources, M8/M9 changes, or execution features are outside scope.

## B8/B12 Research Findings and Blockers

### BLOCKED — Runtime and Plugin Loading

- `.opencode/package.json` pins the plugin SDK `@opencode-ai/plugin` to `1.18.20`; the SDK pin alone does not identify the active OpenCode host/runtime version.
- The repository's `opencode.json` has no explicit plugin registration entry. The existing `.opencode/plugin/tp4-readonly-gate.ts` is E8-specific, gated by `E8_TP4_GATE`, and exports a V1-style named plugin function.
- Official OpenCode v1.18.20 source/docs describe local discovery under `plugin/` and `plugins/` and support legacy function exports. However, that tagged runtime does not dispatch the declared `permission.ask` callback used by the existing TP4 plugin.
- Current OpenCode V2 docs use the `@opencode/plugin` API and `Plugin.define`; a V1 `@opencode-ai/plugin` implementation is not a V2 implementation. V2 permission evaluation hooks run for allow/ask decisions, not explicit configured denies.
- Joseph independently reports that his terminal resolved the active `opencode` command to `/usr/local/opt/opencode/bin/opencode` and that it reported version `1.18.20`. This is user-supplied terminal evidence, not a command executed or independently verified by OpenCode. It supersedes the draft's statement that the host version was unknown, but does not establish plugin discovery, actual activation, or a supported Python invocation bridge. Do not bypass the current Bash allowlist or change permissions for this plan.

**Plugin responsibility approved in principle:** The plugin is a narrow OpenCode lifecycle/receipt adapter for review events. It may pass structured lifecycle observations to the deterministic review controller, but it must not make authorization decisions, grant tools, override native permission results, weaken native permissions, or replace Reviewer isolation. Whether an available, supported plugin API can perform this limited role remains unverified.

**Resolution required before plugin implementation:** verify plugin discovery and actual activation under the reported host, verify a supported plugin entrypoint and local Python bridge, and obtain separate authorization to implement. If these facts cannot be verified, keep plugin integration **BLOCKED** and return to Joseph. The proposed Python/OpenCode bridge and receipt contract below also require Joseph's approval before implementation.

### Plugin Research References

- Repository SDK pin: `.opencode/package.json` (`@opencode-ai/plugin` 1.18.20).
- OpenCode v1.18.20 plugin discovery: [plugin loader](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/config/plugin.ts), [config paths](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/config/paths.ts), and [SDK hook declarations](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/plugin/src/index.ts).
- OpenCode v1.18.20 permission evaluation: [permission implementation](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/permission/index.ts).
- Current OpenCode V2 plugin API and loading: [plugin configuration and discovery](https://opencode.ai/docs/plugins/), [server plugin hooks](https://opencode.ai/docs/build/plugins/server), and [V1 migration guide](https://opencode.ai/docs/build/plugins/migrate-v1).
- The repository's actual host/runtime version was not observed by OpenCode. Joseph's terminal evidence reports `/usr/local/opt/opencode/bin/opencode` version `1.18.20`; this establishes only the reported host identity. The references establish version-specific contracts, not local plugin discovery, activation, or bridge support.

### BLOCKED — Runtime Denial Evidence

**Proposed test design:** Only after separate authorization, use a disposable temporary workspace with a clean baseline and record the sentinel file's exact bytes and SHA-256 plus the complete workspace state/diff. Invoke the actual Fifth Pick Reviewer with a bounded instruction to change only that sentinel through the normal edit tool, then separately challenge an equivalent shell-write route while retaining the production native permission rules. Each required attempt must be an actual Reviewer write request correlated to a native permission-denied result. Verify the sentinel bytes/hash and complete workspace remain unchanged, and preserve sanitized event evidence. Clean only the temporary workspace after recording results.

**Pass criteria:** The actual Reviewer write request is correlated to a native permission denial before execution; the sentinel's exact bytes/hash and the complete disposable workspace remain unchanged; and sanitized evidence records both the request and denial correlation. Configuration inspection alone is not a pass.

**Fail or inconclusive conditions:** No tool is exposed or available; no actual write request is observed; the process times out; the request cannot be correlated to a native denial; no native denial evidence is emitted; the sentinel or any other workspace content changes; evidence is missing; or a plugin/test wrapper, rather than native OpenCode permissions, is the only control that prevents the write. None of these outcomes is PASS; the M10 acceptance gate remains blocked. Do not weaken `edit: deny`, `bash: deny`, `task: deny`, or the root Bash allowlist to force an attempted write.

E8 already observed that `edit: deny` can withhold the edit tool without producing an attempted-edit denial event, and its `edit: ask`/permission-hook attempt timed out without the required denial event (`evolution-08/ADR-3.md:149-169`). Therefore, the test protocol is a proposed acceptance design, not a claim that the installed runtime can currently pass it. B12 must establish a supported, reproducible path; otherwise return the blocked gate to Joseph.

## Review Contract — Approved for Phase 1

The deterministic Python boundary should accept one reviewer JSON object with exactly `status`, `summary`, and `findings`. `status` is limited to `PASS`, `FAIL`, or `CONCERNS`; summary is non-empty; `FAIL` and `CONCERNS` require findings; unknown fields, malformed JSON, missing fields, and unknown statuses fail closed. The OpenCode reviewer remains independent and read-only; the parser does not decide Joseph's final approval.

The controller transition rules are:

| Current state and verdict | Next state | Correction state |
|---|---|---:|
| Initial review `PASS` | Return reviewed result to Joseph; no automatic final approval | 0 dispatched; none available |
| Initial review `FAIL` | `REVISION_REQUIRED`; send findings to Builder | 0 dispatched; one available |
| Review after the one correction `PASS` | Return reviewed result to Joseph | 1 dispatched |
| Review after the one correction `FAIL` | `ESCALATE_TO_JOSEPH` | 1 dispatched |
| Any review `CONCERNS` | `ESCALATE_TO_JOSEPH` | unchanged |
| Malformed or unknown verdict | `STOPPED` / fail closed | unchanged |

These rules follow frozen Part II Sections 49-52, Part II Section 51, and A18. M10 must not route a `CONCERNS` result through an implicit pass or additional correction loop.

**Pure Python boundary:** `review.py` owns typed reviewer-result parsing and a deterministic, side-effect-free state transition function. The OpenCode integration supplies the bounded structured input and consumes the transition. The parser/controller does not rank candidates, finalize a slate, decide Joseph's approval, or determine tool permissions.

**Deterministic review-cycle identifier proposal:** Require an explicit M2-safe `run_id`, a stable review `subject`, and the SHA-256 of the exact initial review-input bundle. Compute `review_cycle_id` as `review-` plus the full lowercase SHA-256 of UTF-8 canonical JSON containing exactly `run_id`, `subject`, and `initial_artifact_sha256`, serialized with sorted keys and compact separators. The initial review and its one correction/re-review share this identifier. The same tuple is the same idempotent cycle; a new cycle for the same subject and input requires a new M2 `run_id`. Each revision also carries its current artifact SHA-256, but does not change the cycle identifier.

**Receipt and run-binding proposal:** Append only through the existing M2 `Receipt` and `RunStore.append_receipt()` contract to that `run_id`'s `receipts.jsonl`; do not change M2 models, storage, or receipt conventions. Every receipt uses the exact supplied `run_id` and `review_cycle_id` as `subject`. Use an ISO-8601 UTC timestamp; `source` is `fifth-pick-reviewer` for verdict events and `fifth-pick-review-controller` for controller events. Keep `reason` bounded to the revision number, current artifact digest, and a closed transition reason code; do not store hidden reasoning or unrestricted reviewer text. Construct deterministic idempotency keys as `review-<cycle-digest>-<sequence:02d>-<event-lowercase>`, where `<cycle-digest>` is the same full lowercase SHA-256 used after `review-` in `review_cycle_id`. Reusing a key with conflicting content must fail closed under M2 behavior.

**Explicit event names and order:**

| Observable action | `Receipt.event` | `Receipt.result` | Ordering/meaning |
|---|---|---|---|
| Reviewer PASS | `REVIEW_PASS` | `PASS` | Valid typed verdict; return reviewed result to Joseph, never auto-approve. |
| Reviewer FAIL | `REVIEW_FAIL` | `FAIL` | Record each valid FAIL verdict; first FAIL permits exactly one correction, second FAIL escalates. |
| Reviewer CONCERNS | `REVIEW_CONCERNS` | `CONCERNS` | Distinct event; always escalates to Joseph, never maps to PASS or FAIL. |
| Builder correction dispatched | `REVISION_ATTEMPT` | `CORRECTION_REQUESTED` | Emit at most once, after the first FAIL and when the one correction is dispatched. |
| Escalation | `ESCALATE_TO_JOSEPH` | `ESCALATED_TO_JOSEPH` | Emit after CONCERNS or a second FAIL; preserve the triggering reason code. |

The event sequence is deterministic: initial verdict is sequence 1; after an initial FAIL, `REVISION_ATTEMPT` is sequence 2 and the post-correction verdict is sequence 3; escalation follows its triggering verdict at the next sequence. The frozen design already names `REVIEW_PASS`, `REVIEW_FAIL`, `REVISION_ATTEMPT`, and `ESCALATE_TO_JOSEPH`; `REVIEW_CONCERNS` is the proposed explicit non-ambiguous event. Malformed or unknown output remains STOPPED/fail-closed and must not be synthesized into one of these typed verdict events.

**Minimum Python/OpenCode bridge proposal:** The lifecycle adapter invokes one local Python adapter process only through an OpenCode-supported mechanism verified for the reported host, using an argument vector without shell interpolation. It sends one JSON request on stdin with exactly `schema_version` (`1`), `kind` (`VERDICT` or `REVISION_DISPATCHED`), `run_id`, `subject`, `initial_artifact_sha256`, `current_artifact_sha256`, and `revision` (`0` or `1`); `VERDICT` requests additionally carry `verdict_json`, a string containing the exact reviewer JSON to be parsed. `REVISION_DISPATCHED` is accepted only once after the initial FAIL and when the controller actually dispatches the single Builder correction. The proposed command is `uv run python -m fifth_pick.review_bridge`. A well-formed envelope returns exactly one JSON object on stdout with `review_cycle_id`, `state` (`REVIEWED_FOR_JOSEPH`, `REVISION_REQUIRED`, `ESCALATE_TO_JOSEPH`, or `STOPPED`), `correction_count` (actual dispatches, 0 or 1), `correction_available` (boolean), and `receipt_event_keys` (the ordered event keys emitted by this request). A malformed verdict or out-of-order event returns `STOPPED`, a nonzero process status, and no transition receipt; malformed outer JSON also fails nonzero without a receipt. Stdout contains no logs. Python performs strict parsing, state transition, and M2 receipt appends; the plugin transports lifecycle data and the response only. It has no authorization role and must not be used as a shell-permission workaround. Actual plugin discovery, activation, event delivery, and support for this local invocation bridge remain unverified. If the host does not support this bridge, keep plugin integration BLOCKED and return for a new decision; do not substitute an unapproved mechanism.

This contract reuses M2 conventions without changing M2 models and is approved for Phase 1 receipt behavior. The bridge shape remains a proposal only: this approval does not authorize `review_bridge.py` or plugin integration, which remain Phase 2 blockers.

## File Map

- Modify `.opencode/agents/fifth-pick-planner.md`, `.opencode/agents/fifth-pick-builder.md`, and `.opencode/agents/fifth-pick-reviewer.md` only to align their instructions with the implemented, approved controller and permission boundaries.
- Modify `.opencode/commands/fifth-pick-review.md` to pass review evidence through the approved typed contract; it must not claim a verdict has been mechanically validated unless `review.py` validates it.
- Create `.opencode/skills/evaluate-candidate/SKILL.md`, `.opencode/skills/validate-evidence/SKILL.md`, `.opencode/skills/final-slate-review/SKILL.md`, and `.opencode/skills/t20-review/SKILL.md` with only the responsibilities in frozen Part II Section 56.
- Modify `.opencode/plugin/` only after the B8/B12 plugin loading and responsibility blockers are resolved; do not repurpose the E8 TP4 gate without separate review and approval.
- Modify `opencode.json` only to preserve or tighten native permissions and to add the minimum approved integration needed by the resolved design. Do not broaden shell access or weaken Reviewer restrictions.
- Create `src/fifth_pick/review.py` for strict result parsing, pure one-correction state transitions, deterministic review-cycle IDs, and M2-compatible receipt creation; it must not perform ranking, finalization, or Joseph approval.
- Create `src/fifth_pick/review_bridge.py` only after approval of the proposed receipt/bridge contract and host-support verification; it is the local JSON stdin/stdout adapter and M2 receipt caller, not an authorization layer.
- Create `tests/test_review_loop.py` for typed parsing, transition, receipt, and denial behavior.
- Create `docs/fifth-pick/assurance.md` and update `docs/fifth-pick/harness.md` to pair each risk with a mechanical control and observed evidence.
- Update `AGENTS.md` only to name real implemented controls; retain its four-section structure and current safeguards.
- Do not modify `src/fifth_pick/models.py`, M1-M9 application code, frozen design, PRD, Evolution 00-08, or unrelated graduate-triage files.

## Four Skill Responsibilities

Use only the responsibilities stated in frozen Part II Section 56:

- `evaluate-candidate`: a repeatable procedure for evaluating one eligible NBA fantasy prop under Joseph's methodology.
- `validate-evidence`: verify candidate evidence is current, trustworthy, sufficient, correctly sourced, and complete enough.
- `final-slate-review`: apply slate ceilings, confidence eligibility, Senior priority, one-player-one-slot, displacement, and no-entry discipline.
- `t20-review`: perform the final approximately-20-minute refresh and assign `STILL STRONG`, `DOWNGRADED`, or `REMOVE RECOMMENDED`.

Each skill's description is its trigger; its `SKILL.md` body contains the procedure. Do not copy the authoritative methodology into skill descriptions or alter it.

## Historical Implementation Tasks and Authorization Boundaries

Phase 1 is authorized by Joseph. M10 must not proceed beyond Phase 1. Plugin implementation and actual native-denial runtime testing remain separately blocked:

- **Task 1**, limited to the pure typed parser and frozen correction state machine; no plugin bridge or permission behavior is included.
- **Task 3**, limited to the four project-local skills and their offline scope/trigger test.
- **Task 2** is included in Phase 1 under the approved contract and uses existing M2 types and storage without changing them.

Plugin implementation and actual native-denial runtime testing remain **BLOCKED** until their stated evidence and approvals exist (Tasks 4-5). Evidence-based documentation may accurately record a runtime control as **BLOCKED**, but final acceptance and any claim that depends on runtime proof remain blocked (Task 7). Parser or skill completion cannot be represented as satisfying a blocked runtime gate.

### Task 1: Build the Pure Review Parser and State Machine

**Authorization:** Authorized in Phase 1. Independent of plugin loading and runtime denial testing.

**Files:** Create `src/fifth_pick/review.py`; create/update pure unit tests in `tests/test_review_loop.py`.

- [ ] Write regression tests for `test_malformed_verdict_fails_closed`, `test_unknown_verdict_fails_closed`, `test_concerns_does_not_pass`, `test_concerns_escalates_to_joseph`, and `test_one_correction_then_escalation` before implementation.
- [ ] Run focused tests with built-in `unittest` and observe RED.
- [ ] Implement strict JSON parsing and deterministic, side-effect-free transitions using the frozen verdict/state vocabulary; keep this separate from M2 sports `Result` types, receipt persistence, OpenCode integration, and M8 Joseph approval.
- [ ] Verify every verdict path and fail-closed parser tests pass. Receipt construction remains limited to the approved fields/event keys in Task 2.

### Task 2: Add M2-Compatible Review Receipts — **PHASE 1 AUTHORIZED**

**Authorization:** Joseph approved the receipt contract for Phase 1. Independent of plugin readiness; do not implement the Python/OpenCode bridge.

**Files:** Only M10 review-controller/receipt code and `tests/test_review_loop.py`; do not modify M2 models or storage.

- [ ] Test deterministic cycle IDs, exact `run_id`/`subject` binding, the proposed five event names and sequence, one-correction idempotency, and conflicting-event fail-closed behavior using the existing M2 `Receipt` and `RunStore` contract.
- [ ] Implement approved receipt construction and append through `RunStore.append_receipt()` only; do not add fields to `Receipt`, change `RunStore`, or create a parallel persistence format.
- [ ] Verify identical retries are idempotent and the same event key with conflicting content fails closed.

### Task 3: Add the Four Independent Project Skills

**Authorization:** Authorized in Phase 1. Independent of the review-cycle contract, plugin, and denial-test runtime.

**Files:** Create `.opencode/skills/evaluate-candidate/SKILL.md`, `.opencode/skills/validate-evidence/SKILL.md`, `.opencode/skills/final-slate-review/SKILL.md`, and `.opencode/skills/t20-review/SKILL.md`; add only the offline skill-presence/scope test.

- [ ] Add each skill with a clear trigger and procedure matching frozen Part II Section 56; authoritative configs and methodology remain the source of truth.
- [ ] Add an in-scope test that checks the four required skill files and trigger descriptions exist.
- [ ] Verify skill language does not add selection methodology, alter frozen requirements, or replace mechanical enforcement with prompts.

### Task 4: Verify and Implement the OpenCode Lifecycle Adapter — **BLOCKED**

**Files, if eventually authorized:** Conditional changes to `.opencode/plugin/`, `opencode.json`, `.opencode/commands/fifth-pick-review.md`, and the approved Python bridge; plugin/bridge tests.

- [ ] Before adapter implementation, obtain separate authorization for a local plugin preflight and verify plugin discovery, actual activation, event delivery, and the supported local Python invocation bridge for the reported host using a non-authoritative probe. Do not install packages or change permissions for this preflight.
- [ ] Do not implement the adapter until the preflight passes, Joseph approves the review contract, and separate M10 implementation authorization is given.
- [ ] Treat `/usr/local/opt/opencode/bin/opencode` version `1.18.20` only as Joseph-supplied terminal evidence. Do not claim it proves discovery, activation, or bridge support.
- [ ] Preserve `edit: deny`, `bash: deny`, and `task: deny` for the production Reviewer and the root Bash deny-by-default allowlist. Do not add or broaden a Reviewer permission to make the adapter work.
- [ ] Implement only the approved lifecycle/receipt adapter role. Native permissions remain the sole authority; the plugin must never grant access, override a denial, weaken permissions, or substitute for Reviewer isolation.
- [ ] If discovery, activation, event delivery, or the approved bridge cannot be verified without changing those boundaries, stop and keep this task BLOCKED; return for a new decision rather than substituting an unapproved mechanism.

### Task 5: Execute the Actual Reviewer Denial Acceptance Test — **BLOCKED**

**Authorization:** Requires separate explicit authorization for the disposable runtime test and a verified, supported way to invoke the actual Reviewer. No such test is authorized in this plan revision.

**Files:** Disposable temporary workspace only during the authorized test; retain sanitized evidence outside production source changes as approved.

- [ ] Preserve `edit: deny`, `bash: deny`, `task: deny`, and the root Bash deny-by-default allowlist unchanged.
- [ ] Use a clean disposable workspace, record the sentinel bytes/hash and full workspace baseline, then direct the actual Fifth Pick Reviewer to attempt the bounded sentinel write through each required action route.
- [ ] Require a real write request correlated to an actual native denial event for each required attempt; afterward verify exact sentinel bytes/hash and the entire workspace are unchanged, and retain sanitized request/denial correlation evidence.
- [ ] Treat missing/unavailable tools, absent requests, timeouts, static configuration inspection, uncorrelated denials, missing evidence, or unchanged files alone as INCONCLUSIVE/BLOCKED, never PASS.
- [ ] If native denial evidence cannot be produced safely with production permissions unchanged, stop and keep the acceptance gate BLOCKED. Never weaken permissions to manufacture an attempt or denial.

### Task 6: Evidence-Based Assurance and Harness Documentation

**Authorization:** Authorized in Phase 1 for documentation of controls with actual implementation/test evidence. Runtime evidence must be explicitly documented as BLOCKED; this task cannot convert a blocked gate into a pass.

**Files:** Update `docs/fifth-pick/assurance.md`, `docs/fifth-pick/harness.md`, `.opencode/agents/*`, `.opencode/commands/fifth-pick-review.md`, and `AGENTS.md` only as evidence supports; no M1-M9 application files.

- [ ] Add assurance rows for reviewer write risk, malformed verdicts, second FAIL, `CONCERNS`, shell-write bypass, and each other applicable M10 risk; each row must name an implemented control and actual evidence artifact/test. Mark unavailable runtime evidence BLOCKED rather than implying it exists.
- [ ] Add `test_assurance_table_has_control_and_evidence_per_risk` only when the referenced controls/evidence are defined; test that claims do not treat prompts, static config, or missing tools as enforcement.
- [ ] Run `test_assurance_table_has_control_and_evidence_per_risk` when its referenced controls and evidence are defined; runtime denial assertions remain BLOCKED until Task 5 passes.

### Task 7: M10 Acceptance and Independent Review — ACCEPTED WITH QUALIFICATION

**Acceptance prerequisites:** Complete the approved implementation, verify runtime activation and bridge invocation, satisfy the native Reviewer gate under the applicable evidence criterion, and pass all four code gates. For OpenCode 1.18.20, apply the dated addendum below to both write routes. Joseph retains final M10 acceptance authority.

**Files:** Verify M10 files only; do not modify M1-M9 application code or frozen requirements.

- [x] Verify malformed verdicts, CONCERNS, the one-correction limit, and assurance coverage with the final implementation suite. Live second-FAIL/CONCERNS escalation remains **UNVERIFIED**, with offline regression coverage.
- [x] Map the original `test_reviewer_cannot_edit` check to approved Route B evidence for native edit/write and `test_shell_write_bypass_is_denied` to Route B evidence for native Bash/shell-write. These are original checklist names. The observed checks are the host catalog, native permission filtering, actual provider tool sets, and unchanged inventory and permission records in [the gate evidence](../../fifth-pick/gates.md#m10-native-reviewer-tool-withholding-evidence). **NATIVE TOOL WITHHOLDING VERIFIED** for both write routes on OpenCode 1.18.20. **REQUEST-TO-DENIAL BEHAVIOR UNVERIFIED**. Read-oriented tools were exposed, while write-capable tools were withheld.
- [x] Verify all four required gates exited `0` on the final implementation baseline. The [distinct final gate entry](../../fifth-pick/gates.md#m10-final-remediation-gate-run) records 510 passing unit tests and the independent remediation PASS.
- [x] Obtain the full-scope mechanically read-only Task 7 review against the roadmap, frozen spec, M1-M9/Evolution 00-08 preservation, permission evidence, skills, assurance table, and no-external-action boundary. It returned CONCERNS about gate traceability and documentation consistency. The `task7_reviewer` verdict is on line 2311 of the local Codex transcript identified in the final gate entry.
- [x] Obtain the independent, mechanically read-only recheck of the Task 7 documentation reconciliation. It returned PASS. The saved `task7_reviewer` verdict is on line 2405 of the local Codex transcript identified in the final gate entry.
- [x] Record Joseph's explicit M10 acceptance with qualification. The [formal acceptance record](../../fifth-pick/gates.md#m10-formal-acceptance-with-qualification) retains the exact limits. Do not start M11 or commit/push without separate authorization.

## Acceptance Criteria

- M9 reviewer PASS and Joseph's review precede M10; M1-M9 behavior remains unchanged and all four required gates pass.
- `PASS`/`FAIL`/`CONCERNS` parsing is strict and malformed/unknown outputs stop fail-closed.
- Exactly one correction is possible after `FAIL`; a second failure escalates to Joseph; `CONCERNS` routes to Joseph and never auto-passes.
- If Joseph approves the proposed receipt contract, review events use deterministic cycle/event keys and the exact M2 `run_id`/`Receipt`/`RunStore` conventions without changing M2 models.
- Original native Reviewer evidence criterion (preserved): The native Reviewer remains read-only; each required write route has an actual Reviewer attempt correlated to a native denial, while the sentinel and complete disposable workspace remain unchanged. If that evidence cannot be produced safely, acceptance is BLOCKED. For OpenCode 1.18.20 only, the dated addendum below also permits Route B evidence for each write route.
- The four skill files cover only their frozen responsibilities.
- The assurance table contains a real control and evidence path for every included risk.
- AGENTS, harness documentation, plugin, and config claims name controls that exist and are verified; no prompt-only claim is represented as enforcement.

## Historical Phase 2 Approval Checkpoint

1. Separately authorize plugin discovery/activation/bridge preflight and implementation. The host path/version evidence is recorded as user-supplied; plugin discovery and activation remain separate verification requirements.
2. Separately authorize the disposable actual-Reviewer denial test. Its acceptance criterion remains the correlated native denial plus unchanged sentinel and complete workspace with production permissions unchanged; otherwise the runtime gate remains BLOCKED.
3. Separately authorize Phase 2 integration and final M10 acceptance after all required runtime evidence exists.
4. Joseph's in-principle approval of the narrowly scoped non-authoritative plugin responsibility and Phase 1 review-cycle contract are recorded above; neither grants Phase 2 authorization.

## Joseph's Phase 2 Implementation Authorization

On 2026-11-17 Joseph authorized implementation of the remaining M10 Phase 2 plugin adapter and Python bridge under this plan, plus the isolated Reviewer write-denial experiment. Joseph reports `/usr/local/opt/opencode/bin/opencode` version `1.18.20`; this confirms the reported executable/version only. It does not prove project plugin discovery, successful activation, event delivery, bridge invocation, or Reviewer isolation. These runtime facts still require disposable-environment evidence.

Preserve the existing E8 plugin, production Reviewer permissions, and root Bash deny-by-default allowlist. Do not install or upgrade dependencies, create a permission grant path, commit, push, or begin another milestone. The denial experiment remains limited to a disposable workspace and passes only with correlated native denial evidence and an unchanged sentinel and complete workspace.

Implementation ruling: carry review metadata to the adapter as a strict JSON argument envelope on the existing review command; bind `review_material` to its exact UTF-8 SHA-256 and correlate the Reviewer response with a per-invocation marker and matching task `callID`. The controller invokes a separate receipt-confirmation command and waits for a persisted `REVISION_ATTEMPT` response before dispatching Builder. The plugin does not dispatch or block Builder and does not make permission decisions. Invoke only `uv run --no-sync python -m fifth_pick.review_bridge` through a fixed argument vector with no shell. Serialize each run's receipt-history read/validate/append using a private OS advisory lock file under `.review-locks`; the lock file contains no receipt data and M2 models, receipt format, and `RunStore` behavior remain unchanged. If v1.18.20 does not provide the required event or process behavior, keep runtime integration BLOCKED rather than substituting a permission hook, shell route, or other authorization mechanism.

## Historical Phase 2 Execution Status Before Disposable Verification

The offline Python bridge, lifecycle adapter, strict review-command envelope, controller receipt-confirmation command, per-run OS lock, and focused tests are implemented. The adapter and bridge use the existing review-cycle contract and M2 `RunStore`; no production Reviewer permission, root Bash allowlist, M1-M9 application code, M2 model, receipt format, or `RunStore` behavior was changed. The offline suite and code-quality gate evidence is recorded in `docs/fifth-pick/gates.md`.

Actual v1.18.20 plugin activation, lifecycle event delivery, and bridge process invocation have not been observed in a disposable OpenCode run. The session's active project Bash policy does not permit launching the host, and that policy was not changed or bypassed. The disposable Reviewer denial experiment has not been run. These are BLOCKED runtime gates, not PASS, and final M10 acceptance remains blocked.

## Joseph's Bounded Review-Correction Authorization

Joseph authorized one test-first correction pass limited to: verifying artifact digests against exact review material; requiring controller confirmation of persisted `REVISION_ATTEMPT` before Builder dispatch; correlating Reviewer output with its exact task invocation; and serializing bridge receipt operations with an ephemeral per-run OS lock. The plugin remains observer/transport only and never dispatches or blocks Builder. The lock is a private per-run `flock` coordination file with no receipt data; M2 models, receipt schema, and `RunStore` behavior are unchanged.

The correction pass ran the four required quality gates and the complete unit suite successfully. No OpenCode activation or Reviewer write-denial experiment was run in this pass. Those runtime gates remain **BLOCKED** pending the separately authorized disposable checks; no M10 acceptance or launch claim is made.


## Bounded Acceptance Preparation

The later isolated OpenCode 1.18.20 runs verified plugin activation, task event delivery, bridge invocation, an initial PASS with a matching M2 receipt, and an invalid-verdict STOPPED response with no receipt. See the recorded run IDs and M9 prerequisite in [gates.md](../../fifth-pick/gates.md).

Joseph authorized sharing CLI envelope decoding without changing either request schema and restricting Builder launch authorization to a newly persisted revision receipt. A replay or uncertain launch stops for Joseph. Builder dispatch remains controller-owned. At this preparation checkpoint, the mandatory native denial experiment was **BLOCKED**, and M10 acceptance remained withheld. See the dated addendum below for the later Route B decision and evidence.

## 2026-11-18 — OpenCode 1.18.20 Native Reviewer Evidence Addendum

Joseph approved this version-scoped alternative evidence criterion and a bounded verification in the isolated disposable workspace. The original frozen mechanically read-only requirement, shell-write boundary, Task 5 wording, and historical evidence remain in place. This addendum changes the evidence accepted for the M10 gate on OpenCode **1.18.20** only. It does not change native permissions or authorize M10 acceptance.

Evaluate native edit and Bash or equivalent shell-write separately. For each route, accept either of these forms of proof.

- **A — Native denial before execution.** An actual Reviewer write request correlates to a native denial before execution under unchanged production Reviewer permissions.
- **B — Native tool withholding before invocation.** Direct runtime evidence ties the relevant host tool catalog and native permission filter to the tool set actually exposed to the Fifth Pick Reviewer during a bounded challenge. The relevant write-capable tools must be unavailable before invocation. To verify both routes by B, show that the Reviewer received neither edit nor Bash or equivalent shell-write capability.

Both routes require unchanged exact sentinel bytes and SHA-256, an unchanged complete disposable workspace backed by reproducible before and after inventories, and confirmation that production Reviewer permissions remained unchanged. Static configuration, tool omission without native host correlation, timeout, or an unchanged workspace alone is insufficient. Missing qualifying evidence for either route leaves the gate **BLOCKED**.

Record qualifying B evidence as **NATIVE TOOL WITHHOLDING VERIFIED** and retain **REQUEST-TO-DENIAL BEHAVIOR UNVERIFIED** wherever no route A evidence exists. Obtain an independent mechanically read-only assessment of the amended gate before presenting the evidence to Joseph for a separate M10 acceptance decision.

The [2026-11-18 gate evidence](../../fifth-pick/gates.md#m10-native-reviewer-tool-withholding-evidence) records qualifying B evidence for both routes in `m10-native-withholding-2b089c988436` and the independent native Reviewer assessment. Route A behavior remains unverified. Final M10 acceptance remains withheld.
