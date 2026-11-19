# Fifth Pick M1 Harness

## Purpose

M1 establishes the minimum trustworthy control plane before any Fifth Pick domain work. It is intentionally limited to packaging, mechanical gates, narrow permissions, role separation, documentation, and preservation checks.

## Gate Model

The only approved mechanical gates are:

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

All four must exit `0`. A failure must be shown before it is corrected. Historical Evolution material is excluded only through the narrow, documented reconciliation in `ADR-2-fifth-pick-mvp.md`; Fifth Pick files are never waived.

## Permission Model

`opencode.json` permits the builder to run only:

- `uv sync`
- `uv lock`
- `uv run fifth-pick health`
- the four gate commands
- `git status`, `git diff`, and `pwd`

Every other bash pattern is denied. The global edit permission remains `ask`; the builder role explicitly permits edits, while the planner and reviewer roles deny them.

## Roles

### Planner

The planner is read-only: `edit: deny`, `bash: deny`, `task: deny`, and the MCP write tool is denied. It turns an authorized request into a bounded plan and does not implement.

### Builder

The builder may edit and run only the approved gates. It must produce observed evidence, preserve historical material, and stop at the authorized checkpoint. It cannot dispatch subagents or call the MCP write tool.

### Reviewer

The reviewer is mechanically read-only: `edit: deny`, `bash: deny`, `task: deny`, and the MCP write tool is denied. The reviewer cannot change builder work, cannot run shell commands, and cannot dispatch subagents. Its denial is configured by the harness, not merely requested by its prompt.

The reviewer returns one JSON object:

```json
{
  "status": "PASS|FAIL|CONCERNS",
  "summary": "non-empty string",
  "findings": ["precise finding"]
}
```

`PASS` may have no findings. `FAIL` and `CONCERNS` require at least one finding. Malformed or unknown verdicts fail closed. `CONCERNS` never defaults to `PASS`.

## Evidence

Gate outputs are recorded in `docs/fifth-pick/gates.md`. M1 evidence must include:

- the pre-correction gate failure,
- the post-M1 gate results,
- the configured reviewer verdict, or an explicit statement that the configured reviewer was unavailable and why,
- confirmation that Evolution 00–08 are unchanged,
- `git status --short` and `git diff --stat`.

The configured reviewer is the only authority for the final M1 verdict. A provisional review by another read-only agent is recorded as provisional and cannot be reported as the configured reviewer's PASS.

## M10 Phase 1 Status

Phase 1 adds `src/fifth_pick/review.py` for strict typed reviewer-output parsing, deterministic one-correction state transitions, review-cycle IDs, and append-only M2 receipts. At the Phase 1 checkpoint, the unit-tested Python review logic had no OpenCode plugin or lifecycle bridge. It does not rank candidates, finalize a slate, or record Joseph's approval.

The four project-local skills provide procedures only. They do not enforce authorization, evidence validity, ranking, finalization, or Reviewer isolation; those controls remain in the existing application and native permission configuration.

The Reviewer remains configured with `edit: deny`, `bash: deny`, and `task: deny`. Phase 1 did not perform an actual Reviewer write attempt, plugin preflight, or runtime denial test. At the Phase 1 checkpoint, plugin discovery/activation, the Python bridge, and the original correlated native-denial acceptance gate were **BLOCKED**. Static permission configuration is not runtime denial evidence.

## M10 Phase 2 Status

The non-authoritative adapter is present at `.opencode/plugin/fifth-pick-review-adapter.ts`; the v1.18.20 loader can discover project-local TypeScript plugins. It observes the named review command, correlates its Reviewer task by invocation marker and `callID`, and transports the controller's separate receipt-confirmation command. It does not dispatch Builder or register a permission hook. Only a fresh `REVISION_ATTEMPT` confirmation authorizes the controller to dispatch Builder. Replay returns STOPPED. If launch is uncertain, stop for Joseph. The bridge verifies digests against the exact UTF-8 review material, invokes M2 persistence under an ephemeral per-run OS lock, and appends only through the existing `RunStore`; M2 models and storage behavior remain unchanged.

Offline tests cover request validation, receipt-history reconstruction, retries, lifecycle-contract constraints, and command-envelope fields. They are not host runtime evidence. The isolated OpenCode 1.18.20 run verified plugin activation, lifecycle delivery, Python invocation, and a matching initial PASS receipt. The earlier isolated empty verdict returned STOPPED without a receipt. See [gates.md](gates.md) for both runs. At that checkpoint the original request-to-denial gate was **BLOCKED**. That evidence remains unverified under Route A. The later addendum and Route B result below give the current gate status on OpenCode 1.18.20. The production Reviewer permissions and root Bash allowlist remain unchanged.

For disposable OpenCode 1.18.20 review runs, set the child process working directory and `PWD` to the canonical disposable project path and pass that same absolute path to `opencode run --dir`. OpenCode can bootstrap from the process working directory while choosing the inherited `PWD` for a new CLI session. Use disposable XDG directories, and before dispatching a Reviewer, verify the persisted session directory with a CLI invocation that names a nonexistent command. Verify the parent and Reviewer session directories against the same disposable path in the runtime evidence.

Run `m10-final-correction-1b5b2abef146` verified the native correction path under process-only local Qwen3 4B model overrides. The observed sequence was `REVIEW_FAIL → REVISION_ATTEMPT → REVIEW_PASS`, with a single Builder dispatch, an inline correction from `2 + 2 = 5` to `2 + 2 = 4`, and a second Reviewer PASS. The final controller state was `REVIEWED_FOR_JOSEPH`. The [evidence index](gates.md#m10-end-to-end-correction-path) records the task calls, exact receipt binding, and fixture digests. At the correction-path checkpoint, the native gate was still **BLOCKED** under the original criterion. Live second-FAIL/CONCERNS escalation remains **UNVERIFIED**, with offline regression coverage. The [final implementation gate record](gates.md#m10-final-remediation-gate-run) records all four gates exiting 0 and 510 unit tests.

The 2026-11-18 OpenCode 1.18.20 addendum permits native pre-invocation withholding as alternative evidence for each write route. Challenge `m10-native-withholding-2b089c988436` established **NATIVE TOOL WITHHOLDING VERIFIED** for edit and Bash/shell-write under unchanged production permissions. **REQUEST-TO-DENIAL BEHAVIOR UNVERIFIED** remains the status of the original evidence path. Read-oriented tools were exposed, while write-capable tools were withheld. The [gate record](gates.md#m10-native-reviewer-tool-withholding-evidence) links the host filter, actual exposed tools, inventory and sentinel comparisons, and independent native read-only assessment. The final Task 7 independent recheck returned PASS. Joseph accepted M10 **WITH QUALIFICATION** on 2026-11-18. The [formal acceptance record](gates.md#m10-formal-acceptance-with-qualification) retains the scope and limits.

## Limits

M1 does not implement feature-specific skills, defense-in-depth hooks, the mechanical correction counter, Odds API integration, registry, authorization, snapshots, methodology, ranking, T-20, finalization, or result grading. Those remain later milestones.

The `legacy` dependency group restores the historical MCP and pytest imports needed by old test modules during discovery. Fifth Pick tests remain built-in `unittest` tests and are discovered automatically by the required gate command.
