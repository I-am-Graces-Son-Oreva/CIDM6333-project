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

## M2 — Domain Model, Receipts, and Run Storage

### M2 RED Before Production Code

The M2 tests were written before `models.py`, `errors.py`, `receipts.py`, and `storage.py` existed. Full discovery ran the new tests and produced this observed failure:

```text
............EEE
======================================================================
ERROR: test_models (unittest.loader._FailedTest.test_models)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_models
Traceback (most recent call last):
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/orevisco/CIDM6333-project/tests/test_models.py", line 5, in <module>
    from fifth_pick.errors import ValidationError
ModuleNotFoundError: No module named 'fifth_pick.errors'


======================================================================
ERROR: test_receipts (unittest.loader._FailedTest.test_receipts)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_receipts
Traceback (most recent call last):
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/orevisco/CIDM6333-project/tests/test_receipts.py", line 4, in <module>
    from fifth_pick.errors import ReceiptError
ModuleNotFoundError: No module named 'fifth_pick.errors'


======================================================================
ERROR: test_storage (unittest.loader._FailedTest.test_storage)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_storage
Traceback (most recent call last):
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/orevisco/CIDM6333-project/tests/test_storage.py", line 6, in <module>
    from fifth_pick.errors import ReceiptConflictError, StorageError, UnsafeRunIdError
ModuleNotFoundError: No module named 'fifth_pick.errors'


----------------------------------------------------------------------
Ran 15 tests in 0.118s

FAILED (errors=3)
```

This is the expected RED: the previous M1 tests still ran, and the three M2 modules could not import because their production modules did not yet exist.

### M2 First Post-Implementation Gate Attempt

After the initial implementation and tests, unittest passed because the M2 code existed. The first post-implementation lint and type gates still failed.

Observed Ruff failure:

```text
UP017 [*] Use `datetime.UTC` alias
  --> tests/test_models.py:23:7
   |
21 | )
22 |
23 | UTC = timezone.utc
   |       ^^^^^^^^^^^^
24 | NOW = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)
25 | LATER = datetime(2026, 11, 15, 17, 5, tzinfo=UTC)
   |
help: Convert to `datetime.UTC` alias
   |
2  | import unittest
   - from datetime import datetime, timezone
3  + from datetime import datetime, timezone, UTC
4  |
--------------------------------------------------------------------------------
22 |
   - UTC = timezone.utc
23 + UTC = UTC
24 | NOW = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)
   |

SIM117 Use a single `with` statement with multiple contexts instead of nested `with` statements
  --> tests/test_storage.py:56:17
   |
55 |               for run_id in ("", ".", "..", "../escape", "nested/run", "/absolute", "a\\b"):
56 | /                 with self.subTest(run_id=run_id):
57 | |                     with self.assertRaises(UnsafeRunIdError):
58 | |_____________________________________________________________|
59 |                           store.run_directory(run_id)
   |
help: Combine `with` statements

SIM117 Use a single `with` statement with multiple contexts instead of nested `with` statements
  --> tests/test_storage.py:121:21
   |
119 |               for failure_target in ("fifth_pick.storage.os.fsync", "fifth_pick.storage.os.replace"):
120 |                   with self.subTest(failure_target=failure_target):
121 | /                     with mock.patch(failure_target, side_effect=OSError("injected failure")):
122 | |                         with self.assertRaises(OSError):
123 | |                             store.append_receipt(
124 | |                                 make_receipt(
   |
help: Combine `with` statements

Found 3 errors.
[*] 1 fixable with `--fix`.
```

Observed ty failure:

```text
error[invalid-argument-type]: Argument to bound method `TestCase.assertIn` is incorrect
  --> tests/test_receipts.py:83:41
   |
83 |         self.assertIn(REDACTION_MARKER, record["source"])
   |                                         ^^^^^^^^^^^^^^^^ Expected `Iterable[Any] | Container[Any]`, found `str | None`
info: element `None` of union `str | None` is not assignable to `Iterable[Any] | Container[Any]`
info: └── type `None` is not assignable to any element of the union `Iterable[Any] | Container[Any]`
info:     ├── type `None` is not assignable to protocol `Iterable[Any]`
info:     │   └── protocol member `__iter__` is not defined on type `None`
info:     └── type `None` is not assignable to protocol `Container[Any]`
info:         └── protocol member `__contains__` is not defined on type `None`
info: Method defined here
   --> stdlib/unittest/case.pyi:217:9
    |
217 |     def assertIn(self, member: Any, container: Iterable[Any] | Container[Any], msg: Any = None) -> None:
    |                                         ----------------------------------- Parameter declared here

error[invalid-argument-type]: Argument to bound method `TestCase.assertIn` is incorrect
  --> tests/test_receipts.py:84:53
   |
84 |         self.assertIn("apiKey=" + REDACTION_MARKER, record["source"])
   |                                                     ^^^^^^^^^^^^^^^^ Expected `Iterable[Any] | Container[Any]`, found `str | None`
info: element `None` of union `str | None` is not assignable to `Iterable[Any] | Container[Any]`
info: └── type `None` is not assignable to any element of the union `Iterable[Any] | Container[Any]`
info:     ├── type `None` is not assignable to protocol `Iterable[Any]`
info:     │   └── protocol member `__iter__` is not defined on type `None`
info:     └── type `None` is not assignable to protocol `Container[Any]`
info:         └── protocol member `__contains__` is not defined on type `None`
info: Method defined here
   --> stdlib/unittest/case.pyi:217:9
    |
217 |     def assertIn(self, member: Any, container: Iterable[Any] | Container[Any], msg: Any = None) -> None:
    |                                         ----------------------------------- Parameter declared here

error[invalid-argument-type]: Argument to bound method `TestCase.assertIn` is incorrect
  --> tests/test_receipts.py:85:41
   |
85 |         self.assertIn("regions=us_dfs", record["source"])
   |                                         ^^^^^^^^^^^^^^^^ Expected `Iterable[Any] | Container[Any]`, found `str | None`
info: element `None` of union `str | None` is not assignable to `Iterable[Any] | Container[Any]`
info: └── type `None` is not assignable to any element of the union `Iterable[Any] | Container[Any]`
info:     ├── type `None` is not assignable to protocol `Iterable[Any]`
info:     │   └── protocol member `__iter__` is not defined on type `None`
info:     └── type `None` is not assignable to protocol `Container[Any]`
info:         └── protocol member `__contains__` is not defined on type `None`
info: Method defined here
   --> stdlib/unittest/case.pyi:217:9
    |
217 |     def assertIn(self, member: Any, container: Iterable[Any] | Container[Any], msg: Any = None) -> None:
    |                                         ----------------------------------- Parameter declared here

error[invalid-argument-type]: Argument to bound method `TestCase.assertIn` is incorrect
  --> tests/test_receipts.py:86:48
   |
86 |         self.assertIn("markets=player_points", record["source"])
   |                                                ^^^^^^^^^^^^^^^^ Expected `Iterable[Any] | Container[Any]`, found `str | None`
info: element `None` of union `str | None` is not assignable to `Iterable[Any] | Container[Any]`
info: └── type `None` is not assignable to any element of the union `Iterable[Any] | Container[Any]`
info:     ├── type `None` is not assignable to protocol `Iterable[Any]`
info:     │   └── protocol member `__iter__` is not defined on type `None`
info:     └── type `None` is not assignable to protocol `Container[Any]`
info:         └── protocol member `__contains__` is not defined on type `None`
info: Method defined here
   --> stdlib/unittest/case.pyi:217:9
    |
217 |     def assertIn(self, member: Any, container: Iterable[Any] | Container[Any], msg: Any = None) -> None:
    |                                         ----------------------------------- Parameter declared here

error[invalid-argument-type]: Argument to bound method `TestCase.assertIn` is incorrect
  --> tests/test_receipts.py:87:41
   |
87 |         self.assertIn(REDACTION_MARKER, record["subject"])
   |                                         ^^^^^^^^^^^^^^^^^ Expected `Iterable[Any] | Container[Any]`, found `str | None`
info: element `None` of union `str | None` is not assignable to `Iterable[Any] | Container[Any]`
info: └── type `None` is not assignable to any element of the union `Iterable[Any] | Container[Any]`
info:     ├── type `None` is not assignable to protocol `Iterable[Any]`
info:     │   └── protocol member `__iter__` is not defined on type `None`
info:     └── type `None` is not assignable to protocol `Container[Any]`
info:         └── protocol member `__contains__` is not defined on type `None`
info: Method defined here
   --> stdlib/unittest/case.pyi:217:9
    |
217 |     def assertIn(self, member: Any, container: Iterable[Any] | Container[Any], msg: Any = None) -> None:
    |                                         ----------------------------------- Parameter declared here

Found 5 diagnostics
```

At that same point, `uv run ruff format --check` reported `46 files already formatted`, and full unittest reported `Ran 36 tests ... OK`. The lint and type failures were corrected in the test files without weakening an assertion.

### M2 Final Gate Results

Observed after all M2 files and `docs/fifth-pick/architecture.md` existed:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
47 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
....................................
----------------------------------------------------------------------
Ran 36 tests in 0.162s

OK
```

All four commands exited `0`. The 36 tests comprise the 12 M1 tests plus the M2 tests. No test was skipped or excluded.

### M2 Redaction Iterable Correction

A review of `Receipt.redacted()` found that a caller-supplied generator could be consumed by the first receipt field, leaving later fields unredacted. A failing test was added before the fix.

Observed RED:

```text
......................F..............
======================================================================
FAIL: test_receipt_redaction_accepts_iterable_secrets_once (test_receipts.ReceiptTests.test_receipt_redaction_accepts_iterable_secrets_once)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_receipts.py", line 100, in test_receipt_redaction_accepts_iterable_secrets_once
    self.assertNotIn(SECRET, json.dumps(redacted.to_dict()))
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'odds-secret-123' unexpectedly found in '{"timestamp": "2026-11-15T17:00:00+00:00", "event": "BOARD_RETRIEVED", "result": "odds-secret-123", "subject": "board for odds-secret-123", "source": "https://api.the-odds-api.com/v4/sports/us_dfs/odds/?apiKey=[REDACTED]&regions=us_dfs&markets=player_points", "reason": null, "run_id": "run-20261115", "event_key": "board-retrieved-1"}'

----------------------------------------------------------------------
Ran 37 tests in 0.142s

FAILED (failures=1)
```

`Receipt.redacted()` now normalizes the secret iterable once and reuses the normalized tuple for every field. The first post-fix formatting gate then failed:

```text
unformatted: File would be reformatted
   --> src/fifth_pick/receipts.py:117:21
    |
116 |             source=redact_text(self.source, normalized_secrets),
    -             reason=(
    -                 None
    -                 if self.reason is None
    -                 else redact_text(self.reason, normalized_secrets)
    -             ),
117 +             reason=(None if self.reason is None else redact_text(self.reason, normalized_secrets)),
    |
```

Observed after the formatting correction:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
47 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.....................................
----------------------------------------------------------------------
Ran 37 tests in 0.147s

OK
```

All four commands exited `0`. The final M2 discovery run is 37 tests: the 12 M1 tests plus the M2 tests. No test was skipped or excluded.

### M2 Authorization and Review Remediation

After the M1 review and commit `8c7d01e`, Joseph explicitly authorized M2 only. The later authorization is recorded as append-only addenda in `docs/PRD.md` and `docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md`; prior M1-only checkpoint wording remains intact. M3 and later work and commits remain unauthorized.

The first M2 reviewer returned `FAIL` with three evidence findings: missing later M2 authorization evidence, no contemporaneous M2 worktree/no-commit snapshot, and generated bytecode caches under `src/fifth_pick/__pycache__/`. The authorization addenda and the following M2 worktree snapshot address the first two; generated caches are removed after final gate execution so verification will not recreate them afterward.

Worktree snapshot taken after M2 implementation and authorization addenda, before this snapshot was appended to the gate evidence:

```text
git status --short --untracked-files=all
 M docs/PRD.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
?? docs/fifth-pick/architecture.md
?? src/fifth_pick/errors.py
?? src/fifth_pick/models.py
?? src/fifth_pick/receipts.py
?? src/fifth_pick/storage.py
?? tests/test_models.py
?? tests/test_receipts.py
?? tests/test_storage.py
```

```text
git diff --stat
 docs/PRD.md                                        |   4 +
 docs/fifth-pick/gates.md                           | 296 +++++++++++++++++++++
 .../superpowers/plans/2026-11-14-fifth-pick-mvp.md |   4 +
 3 files changed, 304 insertions(+)
```

```text
git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)

git status --short -- docs/superpowers/specs/2026-11-13-fifth-pick-design.md
(no output)
```

No M2 commit was made. The listed M2 paths are the only implementation additions; no M3 files are present. The frozen design specification is unchanged.

### M2 Verification After Reviewer Corrections

Observed after the authorization and current-worktree evidence updates:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
47 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.....................................
Ran 37 tests in 0.167s
OK
```

All four commands exited `0`. The full suite includes the 25 M2 tests and 12 M1 tests. Generated `__pycache__` files are removed after this run; no tests or production behavior are changed by that cleanup.
