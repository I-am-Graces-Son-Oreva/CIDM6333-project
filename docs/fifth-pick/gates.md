# Fifth Pick Gate Evidence

## Pre-Implementation Baseline

Recorded before the M1 package, roles, or docs existed.

```text
uv run ruff check
Found 43 errors.
```

All 43 findings were in historical paths:

- `evolution-04`, `evolution-05`, `evolution-07`, `evolution-08`
- `src/e6_context`
- `src/grad_mcp`
- `tests/test_e4_mcp.py`
- `tests/test_e7_isolation.py`

No Fifth Pick file existed, so no finding was attributed to Fifth Pick code.

```text
uv run ruff format --check
25 files would be reformatted, 86 files already formatted
```

The reformatted set was historical Evolution/E4/E6/E7 material.

```text
uv run ty check
Found 50 diagnostics
```

The diagnostics were historical import/type failures in Evolution 00–08 and E4/E6/E7 source and tests, plus the then-missing `fifth_pick.cli` module. The missing module was the expected RED state for the new M1 tests.

```text
uv run python -m unittest discover -s tests
Ran 10 tests
FAILED (failures=3, errors=6)
```

The new M1 tests failed because the package, roles, docs, and `.gitignore` entry did not yet exist. Historical tests also failed to import because their legacy pytest/MCP environment is not part of this project.

## Narrow Reconciliation

Approved in `docs/adr/ADR-2-fifth-pick-mvp.md`. No historical file was edited.

- Ruff and ty exclude only the exact historical directories `evolution-00/**` through `evolution-08/**`, plus the listed E4/E6/E7 source and test paths.
- The test exclusions name only `tests/test_e4_mcp.py`, `tests/test_e6_context.py`, `tests/test_e7_isolation.py`, and `tests/test_e7_memory.py`. No broad `tests/test_e*.py` pattern is used.
- A separate `legacy` dependency group restores `mcp<2` and `pytest>=9` so two historical test modules import during unittest discovery. Neither package is used to run a Fifth Pick test.
- The four required gate commands are unchanged. No Fifth Pick test is excluded or skipped.

The first corrective unittest run demonstrated the remaining issue before the reconciliation was complete:

```text
Ran 13 tests in 0.146s
FAILED (errors=2)
```

`test_e4_mcp` failed on a missing `mcp` import and `test_e7_isolation` failed on a missing `pytest` import. After restoring the legacy imports, the same command ran the 11 Fifth Pick tests with no errors.

## Previous Post-M1 Results

Gate run at the previous review checkpoint, before the five requested remediations:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
39 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
............
Ran 12 tests in 0.152s
OK
```

All four commands exited `0`. The Ruff format count is recorded verbatim; the gate claim rests on the exit status and the absence of any file to reformat, not on interpreting that count. No historical Evolution file was edited.

## Previous Checkpoint Repository Evidence

```text
git status --short
 M .gitignore
 M AGENTS.md
 M docs/PRD.md
 M opencode.json
?? .opencode/agents/fifth-pick-builder.md
?? .opencode/agents/fifth-pick-planner.md
?? .opencode/agents/fifth-pick-reviewer.md
?? .opencode/commands/fifth-pick-review.md
?? docs/adr/ADR-2-fifth-pick-mvp.md
?? docs/fifth-pick/
?? docs/superpowers/
?? pyproject.toml
?? src/fifth_pick/
?? tests/__init__.py
?? tests/test_cli.py
?? tests/test_control_plane.py
?? uv.lock
```

```text
git diff --stat
 .gitignore    |   6 +++
 AGENTS.md     | 120 ++++++++++++++++++++++++----------------------
 docs/PRD.md   | 169 +++++++++++++++++++++++++++++++++++++++++++++++++---------
 opencode.json |   8 ++-
 4 files changed, 211 insertions(+), 92 deletions(-)
```

```text
git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)
```

No commit was made in this session.

## Previous Reviewer Checkpoint

At the previous checkpoint, the configured reviewer was not available in that session's subagent registry. A provisional review by the read-only `explore` agent returned `FAIL`; subsequent instructions authorized the five bounded remediations:

- Narrowed test exclusions to four exact historical files.
- Denied the MCP write tool on planner and builder as well as reviewer.
- Added tests for the MCP write denial.
- Strengthened the API-key test so reading `THE_ODDS_API_KEY` raises.
- Recorded repository evidence and corrected the format-count claim.

The reviewer denial demonstration and final configured-reviewer verdict were pending at that checkpoint.

## Remediation Evidence

### Authorization

Joseph's post-checkpoint authorization is recorded in the addenda at the end of the implementation plan and PRD. The earlier design-phase and planning checkpoint statements remain intact as historical evidence; the later authorization is M1-only and does not authorize M2 or a commit.

### Reviewer Edit Denial

The configured reviewer task was asked to replace the exact line in the external probe file `/var/folders/55/k044jjds0tv7rhmxc3x7_5gc0000gn/T/opencode/fifth-pick-reviewer-denial-probe.txt` with itself. Its result reported: `The requested edit could not be attempted because no edit tool is available; no M1 review was conducted.` The `edit: deny` harness exposed no edit tool, blocking the requested operation before invocation. A subsequent read showed the probe line unchanged. No repository content was modified by the reviewer; the harness did not emit a tool-call denial error because it exposed no edit tool.

### Installation and Health Command

```text
uv sync
Resolved 39 packages in 37ms
Building fifth-pick @ file:///Users/orevisco/CIDM6333-project
Built fifth-pick @ file:///Users/orevisco/CIDM6333-project
Installed 1 package in 5ms
~ fifth-pick==0.1.0 (from file:///Users/orevisco/CIDM6333-project)
exit 0

uv sync
Resolved 39 packages in 8ms
Checked 37 packages in 2ms
exit 0
```

Before the session permission refresh, the installed console command was requested from the main session and through the configured builder; both attempts were denied before execution:

```text
uv run fifth-pick health
DENIED by the active harness permission policy before execution; no stdout, stderr, or exit status.
```

Those attempts returned an active allowlist that omitted `uv run fifth-pick health`. The project config and builder role already allowed that exact command; the session-level policy was refreshed afterward.

Post-refresh verification:

```text
uv run fifth-pick health
{"package": "fifth_pick", "status": "ok", "version": "0.1.0"}
exit 0
```

The installed console entrypoint resolved and returned the expected deterministic M1 health JSON. No network or domain command was exercised.

### Final Remediation Gates

Observed after the bounded configuration and documentation remediations:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
39 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
............
Ran 12 tests in 0.141s
OK
```

All four commands exited `0`. Re-run them after the session restart together with `uv sync` and `uv run fifth-pick health` before the final configured review.

## Current Remediation Worktree Evidence

```text
git status --short
 M .gitignore
 M AGENTS.md
 M docs/PRD.md
 M opencode.json
?? .opencode/agents/fifth-pick-builder.md
?? .opencode/agents/fifth-pick-planner.md
?? .opencode/agents/fifth-pick-reviewer.md
?? .opencode/commands/fifth-pick-review.md
?? docs/adr/ADR-2-fifth-pick-mvp.md
?? docs/fifth-pick/
?? docs/superpowers/
?? pyproject.toml
?? src/fifth_pick/
?? tests/__init__.py
?? tests/test_cli.py
?? tests/test_control_plane.py
?? uv.lock
```

```text
git diff --stat
 .gitignore    |   6 ++
 AGENTS.md     | 120 +++++++++++++++++++---------------------
 docs/PRD.md   | 173 +++++++++++++++++++++++++++++++++++++++++++++++++---------
 opencode.json |   9 ++-
 4 files changed, 216 insertions(+), 92 deletions(-)
```

```text
git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)
```

No commit was made.
