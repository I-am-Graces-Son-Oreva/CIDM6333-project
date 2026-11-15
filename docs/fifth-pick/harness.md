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

## Limits

M1 does not implement feature-specific skills, defense-in-depth hooks, the mechanical correction counter, Odds API integration, registry, authorization, snapshots, methodology, ranking, T-20, finalization, or result grading. Those remain later milestones.

The `legacy` dependency group restores the historical MCP and pytest imports needed by old test modules during discovery. Fifth Pick tests remain built-in `unittest` tests and are discovered automatically by the required gate command.
