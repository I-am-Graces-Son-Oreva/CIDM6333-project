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

## M3 Authorization and Baseline

Joseph's 2026-11-15 instruction authorizes M3 only. It authorizes the existing Part II 9.1 approved player universe as version `v1`, effective `2026-11-15`, with no entry changes. Part III A1/A2, E4, and E5 govern normalization and authorization. M4 and later work, Evolution changes, frozen-spec changes, and commits remain out of scope.

Fresh pre-M3 baseline:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
47 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.....................................
Ran 37 tests in 0.140s
OK
```

All four commands exited `0` before M3 implementation began.

## M4 Authorization and Baseline

Joseph's 2026-11-15 instruction authorizes M4 implementation only. It does not authorize a live API request. Live smoke remains opt-in and requires separate explicit authorization, `THE_ODDS_API_KEY`, and an explicit credit budget. M5 and later work and commits remain out of scope.

Fresh pre-M4 baseline:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
..........................................................................................
Ran 90 tests in 1.311s
OK
```

All four commands exited `0` before M4 implementation began. No live request was made.

## M3 — Configuration, Registry, Identity, and Authorization

### M3 RED Before Production Code

The M3 tests were written before `config.py`, `registry.py`, `identity.py`, and `authorization.py` existed. Full discovery reported three import failures. The exception and module lines were retained; the full tracebacks were not retained.

```text
ImportError: Failed to import test module: test_authorization
ModuleNotFoundError: No module named 'fifth_pick.authorization'

ImportError: Failed to import test module: test_config
ModuleNotFoundError: No module named 'fifth_pick.config'

ImportError: Failed to import test module: test_identity
ModuleNotFoundError: No module named 'fifth_pick.identity'
```

This was the expected RED: the M1 and M2 tests still ran, and the new M3 test modules could not import because their production modules did not yet exist.

During the initial implementation pass, `uv run ruff check` reported E501 line-length findings and `uv run ruff format --check` reported unformatted files before correction. Those exact earlier outputs were not retained. They were corrected manually; no assertion or gate was weakened. The retained format failure below is from the later test-strengthening pass.

### M3 Test-Strengthening RED

A stronger test was added to compare every parsed Part II 9.1 category/direction segment with `approved-universe.yaml`. Its first run exposed a test-helper parsing bug, not a production defect. Observed first failure and final count:

```text
FAIL: test_all_normalized_categories_follow_a1_and_a2 (test_config.ConfigLoadingTests.test_all_normalized_categories_follow_a1_and_a2) (player='Trae Young')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_config.py", line 300, in test_all_normalized_categories_follow_a1_and_a2
    self.assertEqual(actual, expected_categories(source_entry))
                             ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/Users/orevisco/CIDM6333-project/tests/test_config.py", line 86, in expected_categories
    raise AssertionError(f"unparsable category segment: {segment!r}")
AssertionError: unparsable category segment: 'higher'

----------------------------------------------------------------------
Ran 81 tests in 0.948s

FAILED (failures=131)
```

The helper split on `/`, so the `higher/lower` direction text in the frozen source was split into `higher` and `lower`. The separator was corrected to the exact `" / "` delimiter used by the source. The strengthened test now compares every entry and does not weaken or skip any assertion.

### M3 First Post-Implementation Format Gate Failure

After the strengthened test passed, `uv run ruff format --check` failed. Observed output:

```text
unformatted: File would be reformatted
   --> tests/test_config.py:100:1
    |
 99 |
    -
100 | def copy_config_dir(destination: Path) -> Path:
    |

1 file would be reformatted, 53 files already formatted
```

The extra blank line was removed manually. No formatter command was run, and no gate was bypassed.

### M3 Final Gate Results

Observed after the strengthened test, documentation update, and manual formatting correction:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.................................................................................
----------------------------------------------------------------------
Ran 81 tests in 0.872s

OK
```

All four commands exited `0`. The 81 tests comprise the 37 M1/M2 tests plus the 44 M3 tests. No Fifth Pick test was skipped or excluded.

### M3 Worktree Evidence

Snapshot taken after M3 implementation and the architecture update, before this evidence section was appended:

```text
git status --short --untracked-files=all
 M AGENTS.md
 M docs/PRD.md
 M docs/fifth-pick/architecture.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
 M pyproject.toml
 M uv.lock
?? config/fifth-pick/approved-sources.yaml
?? config/fifth-pick/approved-universe.yaml
?? config/fifth-pick/category-map.yaml
?? config/fifth-pick/governance.yaml
?? config/fifth-pick/methodology.yaml
?? config/fifth-pick/trust-tiers.yaml
?? src/fifth_pick/authorization.py
?? src/fifth_pick/config.py
?? src/fifth_pick/identity.py
?? src/fifth_pick/registry.py
?? tests/fixtures/registry/provider-aliases.yaml
?? tests/test_authorization.py
?? tests/test_config.py
?? tests/test_identity.py
```

```text
git diff --stat
 AGENTS.md                                          |  2 +-
 docs/PRD.md                                        |  4 ++
 docs/fifth-pick/architecture.md                    | 59 ++++++++++++++++--
 docs/fifth-pick/gates.md                           | 24 ++++++++
 .../superpowers/plans/2026-11-14-fifth-pick-mvp.md |  4 ++
 pyproject.toml                                     |  5 +-
 uv.lock                                            | 70 ++++++++++++++++++++++
 7 files changed, 161 insertions(+), 7 deletions(-)
```

```text
git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)

git status --short -- docs/superpowers/specs/2026-11-13-fifth-pick-design.md
(no output)
```

No M3 commit was made. The frozen design and historical Evolution material are unchanged. `AGENTS.md`, `docs/PRD.md`, and the implementation plan contain only the previously authorized M3 status addenda.

### M3 Reviewer Finding Correction — Authoritative Authorization Configuration

Reviewer findings requiring correction:

1. `AuthorizationGate(live_categories=...)` lets a caller include `THREE_POINT_ATTEMPTS`, overriding the frozen live allowlist.
2. `AuthorizationGate` accepts caller-supplied `Registry`/`CategoryMapConfig` derived from arbitrary `load_configs(config_dir)` data, allowing added grants to reach authorization despite v1 metadata.
3. Caller-supplied universe version/effective-date arguments let decisions carry arbitrary provenance.

The correction makes `AuthorizationGate` construct its own `ConfigBundle` from the fixed default authoritative config directory, derive the registry, category map, version, and effective date from that validated bundle, and always use `LIVE_MVP_CATEGORIES`. The constructor accepts no caller overrides.

#### Correction RED Before Production Code

Tests were added before the production change for caller-supplied registry, category map, live-category set, and universe metadata. The custom registry test builds a registry containing an extra player and a `THREE_POINT_ATTEMPTS` grant to show that data cannot reach the gate. With the no-arg API not yet implemented, the first full discovery run stopped in `setUpClass`:

```text
E......................................................................
======================================================================
ERROR: setUpClass (test_authorization.AuthorizationTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 21, in setUpClass
    cls.gate = AuthorizationGate()
               ~~~~~~~~~~~~~~~~~^^^
TypeError: AuthorizationGate.__init__() missing 4 required keyword-only arguments: 'registry', 'category_map', 'universe_version', and 'universe_effective_date'

----------------------------------------------------------------------
Ran 70 tests in 0.887s

FAILED (errors=1)
```

To exercise the injection findings directly, `setUpClass` temporarily used the legacy constructor, which was still the production API. Full discovery then showed the four injection tests failing because the legacy gate accepted each override:

```text
....FFFF.............................................................................
======================================================================
FAIL: test_gate_rejects_caller_supplied_category_map (test_authorization.AuthorizationTests.test_gate_rejects_caller_supplied_category_map)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 181, in test_gate_rejects_caller_supplied_category_map
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

======================================================================
FAIL: test_gate_rejects_caller_supplied_live_categories (test_authorization.AuthorizationTests.test_gate_rejects_caller_supplied_live_categories)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 187, in test_gate_rejects_caller_supplied_live_categories
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

======================================================================
FAIL: test_gate_rejects_caller_supplied_registry (test_authorization.AuthorizationTests.test_gate_rejects_caller_supplied_registry)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 161, in test_gate_rejects_caller_supplied_registry
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

======================================================================
FAIL: test_gate_rejects_caller_supplied_universe_metadata (test_authorization.AuthorizationTests.test_gate_rejects_caller_supplied_universe_metadata)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 191, in test_gate_rejects_caller_supplied_universe_metadata
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

----------------------------------------------------------------------
Ran 85 tests in 1.126s

FAILED (failures=4)
```

#### Correction GREEN After Production Code

After the constructor/root fix and restoring the no-arg `setUpClass` construction, full discovery passed:

```text
.....................................................................................
----------------------------------------------------------------------
Ran 85 tests in 1.447s

OK
```

#### Correction Final Gate Results

Observed after the production fix and documentation updates:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.....................................................................................
----------------------------------------------------------------------
Ran 85 tests in 0.955s

OK
```

All four commands exited `0`. No test was skipped or excluded. No commit was made.

### M3 Post-Correction Worktree Evidence

Snapshot after the authorization-gate correction and final gate run:

```text
git status --short --untracked-files=all
 M AGENTS.md
 M docs/PRD.md
 M docs/fifth-pick/architecture.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
 M pyproject.toml
 M uv.lock
?? config/fifth-pick/approved-sources.yaml
?? config/fifth-pick/approved-universe.yaml
?? config/fifth-pick/category-map.yaml
?? config/fifth-pick/governance.yaml
?? config/fifth-pick/methodology.yaml
?? config/fifth-pick/trust-tiers.yaml
?? src/fifth_pick/authorization.py
?? src/fifth_pick/config.py
?? src/fifth_pick/identity.py
?? src/fifth_pick/registry.py
?? tests/fixtures/registry/provider-aliases.yaml
?? tests/test_authorization.py
?? tests/test_config.py
?? tests/test_identity.py
```

```text
git diff --stat
 AGENTS.md                                          |   2 +-
 docs/PRD.md                                        |   4 +
 docs/fifth-pick/architecture.md                    |  61 +++-
 docs/fifth-pick/gates.md                           | 337 +++++++++++++++++++++
 .../superpowers/plans/2026-11-14-fifth-pick-mvp.md |   4 +
 pyproject.toml                                     |   5 +-
 uv.lock                                            |  70 +++++
 7 files changed, 476 insertions(+), 7 deletions(-)
```

```text
git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)

git status --short -- docs/superpowers/specs/2026-11-13-fifth-pick-design.md
(no output)
```

No M3 commit was made. Both `src/fifth_pick/__pycache__/` and `tests/__pycache__/` are empty after cleanup. No M4 files or runtime artifacts are present.

### M3 Controller Verification After Authorization Fix

Fresh controller-run gates after removing caller-controlled authorization inputs:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.....................................................................................
Ran 85 tests in 1.042s
OK
```

All four commands exited `0`. The 85-test suite includes M1, M2, and M3 tests; the M3 authorization-boundary tests are in `tests/test_authorization.py`.

Current M3 worktree snapshot, before this evidence block was appended:

```text
git status --short --untracked-files=all
 M AGENTS.md
 M docs/PRD.md
 M docs/fifth-pick/architecture.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
 M pyproject.toml
 M uv.lock
?? config/fifth-pick/approved-sources.yaml
?? config/fifth-pick/approved-universe.yaml
?? config/fifth-pick/category-map.yaml
?? config/fifth-pick/governance.yaml
?? config/fifth-pick/methodology.yaml
?? config/fifth-pick/trust-tiers.yaml
?? src/fifth_pick/authorization.py
?? src/fifth_pick/config.py
?? src/fifth_pick/identity.py
?? src/fifth_pick/registry.py
?? tests/fixtures/registry/provider-aliases.yaml
?? tests/test_authorization.py
?? tests/test_config.py
?? tests/test_identity.py
```

```text
git diff --stat
 AGENTS.md                                          |   2 +-
 docs/PRD.md                                        |   4 +
 docs/fifth-pick/architecture.md                    |  61 ++++-
 docs/fifth-pick/gates.md                           | 274 +++++++++++++++++++++
 .../superpowers/plans/2026-11-14-fifth-pick-mvp.md |   4 +
 pyproject.toml                                     |   5 +-
 uv.lock                                            |  70 ++++++
 7 files changed, 413 insertions(+), 7 deletions(-)
```

The frozen design spec and Evolution 00–08 remained unchanged at this snapshot. No M3 commit was created and no M4 work was started.

### M3 Final Reviewer Finding Correction — Approved-Universe Entry Content Pin

Final reviewer finding: `load_configs(custom_dir)` accepted a caller-supplied directory whose `approved-universe.yaml` retained `v1` / `2026-11-15` metadata but contained extra outside-universe players or grants, so a modified `v1` bundle could be treated as the authorized universe.

The correction adds `test_modified_v1_universe_entries_fail_closed` in `tests/test_config.py`. It copies the six configs to a `TemporaryDirectory`, appends a syntactically valid outside-universe player with a `POINTS` higher/lower grant to `approved-universe.yaml` while leaving `content_version`, `effective_date`, and `provenance` intact, and asserts `load_configs(copied_dir)` raises `ConfigError`.

#### Correction RED Before Production Code

Observed before the content-integrity check existed; the current loader accepted the altered universe:

```text
..............................F.......................................................
======================================================================
FAIL: test_modified_v1_universe_entries_fail_closed (test_config.ConfigLoadingTests.test_modified_v1_universe_entries_fail_closed)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_config.py", line 237, in test_modified_v1_universe_entries_fail_closed
    with self.assertRaises(ConfigError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
AssertionError: ConfigError not raised

----------------------------------------------------------------------
Ran 86 tests in 1.071s

FAILED (failures=1)
```

#### Expected Digest Exposure

A temporary diagnostic unittest asserted the canonical entry digest against a placeholder, exposed the actual value, and was then removed. Only the mutation-rejection test was retained.

```text
AssertionError: 'PENDING' != '5b80fc42654e72f0a04d184fa078e319126bfbdb9117d672be71529d0ec6c121'
- PENDING
+ 5b80fc42654e72f0a04d184fa078e319126bfbdb9117d672be71529d0ec6c121
```

`APPROVED_UNIVERSE_ENTRIES_SHA256` is the canonical UTF-8 JSON SHA-256 of the parsed `approved-universe.entries` list (`sort_keys`, compact separators, preserved list order).

#### Correction GREEN After Production Code

Observed after the digest pin was added and the diagnostic test removed:

```text
......................................................................................
----------------------------------------------------------------------
Ran 86 tests in 1.057s

OK
```

#### Correction Final Gate Results

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
......................................................................................
----------------------------------------------------------------------
Ran 86 tests in 1.057s

OK
```

All four commands exited `0`. The 86 tests comprise the 85 prior M1/M2/M3 tests plus the retained mutation-rejection test; no test was skipped or excluded. Only `src/fifth_pick/config.py`, `tests/test_config.py`, `docs/fifth-pick/architecture.md`, and `docs/fifth-pick/gates.md` were changed for this correction. No commit was made.

### M3 Final Reviewer Finding Correction — Immutable Authorization State

Final reviewer finding: after the no-argument constructor, ordinary callers could reassign `AuthorizationGate._registry` or `AuthorizationGate._live_categories`, and the gate reached mutable registry index dictionaries and a mutable `CategoryMapConfig.mappings`, bypassing the fixed live-category and universe configuration.

The correction makes `AuthorizationGate` a frozen, slotted record with no caller-supplied construction path. Its registry ID/name/alias index attributes are frozen and hold read-only `MappingProxyType` mappings; `CategoryMapConfig.mappings` is defensively copied into a read-only `MappingProxyType`. `LIVE_MVP_CATEGORIES` is still assigned internally by the no-argument constructor.

#### Correction RED Before Production Code

Tests were added first for gate attribute reassignment, registry index injection, and category-map entry addition. Full discovery observed the expected failures against the prior mutable gate, registry indexes, and category map:

```text
....F....FFFFFF...FFFF.............F..............................................................
======================================================================
FAIL: test_gate_category_map_is_immutable (test_authorization.AuthorizationTests.test_gate_category_map_is_immutable)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 255, in test_gate_category_map_is_immutable
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

======================================================================
FAIL: test_gate_state_is_immutable_after_construction (test_authorization.AuthorizationTests.test_gate_state_is_immutable_after_construction) (attribute='_registry')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 208, in test_gate_state_is_immutable_after_construction
    with self.assertRaises(AttributeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
AssertionError: AttributeError not raised

======================================================================
FAIL: test_gate_state_is_immutable_after_construction (test_authorization.AuthorizationTests.test_gate_state_is_immutable_after_construction) (attribute='_category_map')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 208, in test_gate_state_is_immutable_after_construction
    with self.assertRaises(AttributeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
AssertionError: AttributeError not raised

======================================================================
FAIL: test_gate_state_is_immutable_after_construction (test_authorization.AuthorizationTests.test_gate_state_is_immutable_after_construction) (attribute='_live_categories')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 208, in test_gate_state_is_immutable_after_construction
    with self.assertRaises(AttributeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
AssertionError: AttributeError not raised

======================================================================
FAIL: test_gate_state_is_immutable_after_construction (test_authorization.AuthorizationTests.test_gate_state_is_immutable_after_construction) (attribute='_universe_version')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 208, in test_gate_state_is_immutable_after_construction
    with self.assertRaises(AttributeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
AssertionError: AttributeError not raised

======================================================================
FAIL: test_gate_state_is_immutable_after_construction (test_authorization.AuthorizationTests.test_gate_state_is_immutable_after_construction) (attribute='_universe_effective_date')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 208, in test_gate_state_is_immutable_after_construction
    with self.assertRaises(AttributeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
AssertionError: AttributeError not raised

======================================================================
FAIL: test_gate_state_is_immutable_after_construction (test_authorization.AuthorizationTests.test_gate_state_is_immutable_after_construction)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 211, in test_gate_state_is_immutable_after_construction
    self.assertFalse(
    ~~~~~~~~~~~~~~~~^
        gate.authorize("outside-universe-player", Category.POINTS, Direction.HIGHER).allowed
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
AssertionError: True is not false

======================================================================
FAIL: test_registry_indexes_are_immutable (test_authorization.AuthorizationTests.test_registry_indexes_are_immutable) (attribute='_by_id')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 239, in test_registry_indexes_are_immutable
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

======================================================================
FAIL: test_registry_indexes_are_immutable (test_authorization.AuthorizationTests.test_registry_indexes_are_immutable) (attribute='_by_name')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 239, in test_registry_indexes_are_immutable
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

======================================================================
FAIL: test_registry_indexes_are_immutable (test_authorization.AuthorizationTests.test_registry_indexes_are_immutable) (attribute='_by_alias')
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 239, in test_registry_indexes_are_immutable
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

======================================================================
FAIL: test_registry_indexes_are_immutable (test_authorization.AuthorizationTests.test_registry_indexes_are_immutable)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_authorization.py", line 244, in test_registry_indexes_are_immutable
    self.assertIsNone(registry.player_by_id(injected.player_id))
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: RegistryPlayer(player_id='outside-universe-player', canonical_name='Outside Universe Player', grants=frozenset({AuthorizationGrant(category=<Category.POINTS: 'POINTS'>, direction=<Direction.HIGHER: 'HIGHER'>)}), aliases=(), foul_trouble=False) is not None

======================================================================
FAIL: test_category_map_mappings_are_immutable (test_config.ConfigLoadingTests.test_category_map_mappings_are_immutable)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/orevisco/CIDM6333-project/tests/test_config.py", line 390, in test_category_map_mappings_are_immutable
    with self.assertRaises(TypeError):
         ~~~~~~~~~~~~~~~~~^^^^^^^^^^^
AssertionError: TypeError not raised

----------------------------------------------------------------------
Ran 90 tests in 1.349s

FAILED (failures=12)
```

#### Correction GREEN After Production Code

The first post-implementation gate attempt found two test-side issues only: Ruff `SIM117` for a nested `with`, and ty rejecting `operator.setitem` against a value typed as `Mapping`. The tests were corrected by combining the `with` statements and typing the attempted-mutation value as `Any` at that site. No assertion was weakened.

Observed GREEN:

```text
..........................................................................................
----------------------------------------------------------------------
Ran 90 tests in 1.317s

OK
```

#### Correction Final Gate Results

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
..........................................................................................
----------------------------------------------------------------------
Ran 90 tests in 1.267s

OK
```

All four commands exited `0`. The 90 tests comprise the 86 prior M1/M2/M3 tests plus four retained immutability tests; no test was skipped or excluded. Only `src/fifth_pick/authorization.py`, `src/fifth_pick/registry.py`, `src/fifth_pick/config.py`, `tests/test_authorization.py`, `tests/test_config.py`, `docs/fifth-pick/architecture.md`, and `docs/fifth-pick/gates.md` were changed for this correction. No constructor or factory path for caller-supplied registry, category map, config directory, live categories, universe version, or effective date was added. No commit was made.

### M3 Final Controller Verification

Fresh gates after the authorization-state correction:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
..........................................................................................
Ran 90 tests in 1.311s
OK
```

All four commands exited `0`.

Final M3 worktree snapshot before appending this block:

```text
git status --short --untracked-files=all
 M AGENTS.md
 M docs/PRD.md
 M docs/fifth-pick/architecture.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
 M pyproject.toml
 M uv.lock
?? config/fifth-pick/approved-sources.yaml
?? config/fifth-pick/approved-universe.yaml
?? config/fifth-pick/category-map.yaml
?? config/fifth-pick/governance.yaml
?? config/fifth-pick/methodology.yaml
?? config/fifth-pick/trust-tiers.yaml
?? src/fifth_pick/authorization.py
?? src/fifth_pick/config.py
?? src/fifth_pick/identity.py
?? src/fifth_pick/registry.py
?? tests/fixtures/registry/provider-aliases.yaml
?? tests/test_authorization.py
?? tests/test_config.py
?? tests/test_identity.py
```

```text
git diff --stat
 AGENTS.md                                          |   2 +-
 docs/PRD.md                                        |   4 +
 docs/fifth-pick/architecture.md                    |  63 +++-
 docs/fifth-pick/gates.md                           | 627 +++++++++++++++++++++
 .../superpowers/plans/2026-11-14-fifth-pick-mvp.md |   4 +
 pyproject.toml                                     |   5 +-
 uv.lock                                            |  70 ++++
 7 files changed, 768 insertions(+), 7 deletions(-)
```

No M3 commit was made. No Evolution or frozen-spec changes were present. No `var/fifth-pick/` directory was created. Test-generated Python bytecode caches were removed after this gate run; no verification command is run after cache cleanup.

### M3 Cache-Cleanup Authorization and Reverification

The final reviewer identified ignored bytecode caches under `evolution-07/lab/__pycache__/` and `evolution-08/src/__pycache__/`. Joseph authorized cleanup only in those two locations. On inspection, both directories were already absent, so no Evolution file was deleted or otherwise modified. After the final gate run below, both directories remained absent and `git status --short -- evolution-07 evolution-08` returned no output.

```text
uv run ruff check
All checks passed!

uv run ruff format --check
54 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
..........................................................................................
Ran 90 tests in 1.317s
OK
```

All four commands exited `0`. No M4 work or M3 commit was performed.

## M4 — Source Adapter, Live Client, Redaction, and Quota

### M4 RED Before Production Code

The M4 tests (`tests/test_odds_api.py`, `tests/test_normalize.py`, `tests/test_quota.py`) and the synthetic fixtures were written before any `src/fifth_pick/sources/` module existed. Full discovery ran the prior 90 M1–M3 tests and reported three import failures for the new modules:

```text
...........................................................................EEE...............
======================================================================
ERROR: test_normalize (unittest.loader._FailedTest.test_normalize)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_normalize
Traceback (most recent call last):
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/orevisco/CIDM6333-project/tests/test_normalize.py", line 8, in <module>
    from fifth_pick.sources.base import (
    ...<4 lines>...
    )
ModuleNotFoundError: No module named 'fifth_pick.sources'


======================================================================
ERROR: test_odds_api (unittest.loader._FailedTest.test_odds_api)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_odds_api
Traceback (most recent call last):
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/orevisco/CIDM6333-project/tests/test_odds_api.py", line 10, in <module>
    from fifth_pick.sources import odds_api
ModuleNotFoundError: No module named 'fifth_pick.sources'


======================================================================
ERROR: test_quota (unittest.loader._FailedTest.test_quota)
----------------------------------------------------------------------
ImportError: Failed to import test module: test_quota
Traceback (most recent call last):
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/Users/orevisco/CIDM6333-project/tests/test_quota.py", line 4, in <module>
    from fifth_pick.sources.quota import (
    ...<5 lines>...
    )
ModuleNotFoundError: No module named 'fifth_pick.sources'


----------------------------------------------------------------------
Ran 93 tests in 1.264s

FAILED (errors=3)
```

This was the expected RED: the prior M1–M3 tests still ran, and the three M4 test modules could not import because `src/fifth_pick/sources/` did not yet exist.

### M4 First Post-Implementation Gate Failure

After the M4 modules were written, full unittest passed and `uv run ruff format --check` reported no file to reformat. Two gates still failed. Observed `uv run ruff check`:

```text
E501 Line too long (101 > 100)
  --> src/fifth_pick/sources/normalize.py:67:101
   |
67 | def resolve_identity(projection: SourceProjection, resolver: IdentityResolver) -> ResolvedProjection:
   |                                                                                                     ^
68 |     """Bind one projection to a canonical player using the provider alias index only.
   |

F401 [*] `fifth_pick.sources.quota.QuotaSnapshot` imported but unused
  --> src/fifth_pick/sources/odds_api.py:37:5
   |
35 | from fifth_pick.sources.quota import (
36 |     QuotaBudget,
37 |     QuotaSnapshot,
   |     ^^^^^^^^^^^^^
38 |     estimate_odds_cost,
39 |     parse_quota_headers,
   |
help: Remove unused import: `fifth_pick.sources.quota.QuotaSnapshot`

E501 Line too long (101 > 100)
   --> src/fifth_pick/sources/odds_api.py:306:101
    |
304 |         for bookmaker in bookmakers:
305 |             if not isinstance(bookmaker, dict):
306 |                 raise MalformedPayloadError(f"odds payload for {event_id} has a malformed bookmaker")
    |                                                                                                     ^
307 |             platform = _platform_for_bookmaker(bookmaker.get("key"))
    |

E501 Line too long (101 > 100)
   --> tests/test_odds_api.py:407:101
    |
405 |     def test_non_list_bookmakers_fails_closed(self) -> None:
406 |         events_body = (FIXTURE_DIR / "events.json").read_bytes()
407 |         responses = {events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=events_body)}
    |                                                                                                     ^

E501 Line too long (101 > 100)
   --> tests/test_odds_api.py:421:101
    |
421 |         responses = {events_url(): HttpResponse(status=200, headers=QUOTA_HEADERS, body=events_body)}
    |                                                                                                     ^

Found 5 errors.
[*] 1 fixable with `--fix`.
```

Observed `uv run ty check`:

```text
error[missing-attribute]: Object of type `object` has no attribute `events`
   --> tests/test_odds_api.py:263:30
error[missing-attribute]: Object of type `object` has no attribute `provenance`
   --> tests/test_odds_api.py:269:22
error[missing-attribute]: Object of type `object` has no attribute `projections`
   --> tests/test_odds_api.py:284:23
error[missing-attribute]: Object of type `object` has no attribute `projections`
   --> tests/test_odds_api.py:322:52
error[missing-attribute]: Object of type `object` has no attribute `projections`
   --> tests/test_odds_api.py:328:62
error[missing-attribute]: Object of type `object` has no attribute `events`
   --> tests/test_odds_api.py:338:26
error[missing-attribute]: Object of type `object` has no attribute `provenance`
   --> tests/test_odds_api.py:346:26
error[missing-attribute]: Object of type `object` has no attribute `events`
   --> tests/test_odds_api.py:362:30
error[invalid-argument-type]: Argument to function `fetch_fixture_board` is incorrect
   --> tests/test_odds_api.py:441:37
info: Expected `FakeTransport`, found `FixtureTransport`
error[missing-attribute]: Object of type `object` has no attribute `events`
   --> tests/test_odds_api.py:443:30
Found 10 diagnostics
```

The findings were corrected without weakening any assertion: the long lines were wrapped, the unused import was removed, and `fetch_fixture_board()`/`make_client()` were typed against the `Transport` protocol and `SourceBoard` so the fake and fixture transports both satisfy the boundary.

### M4 Final Gate Results

Observed after the M4 modules, fixtures, and documentation existed:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
66 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.....................................................................................................................................................
---------------------------------------------------------------------
Ran 149 tests in 1.466s

OK
```

All four commands exited `0`. The 149 tests comprise the 90 prior M1–M3 tests plus the M4 tests in `tests/test_odds_api.py`, `tests/test_normalize.py`, and `tests/test_quota.py`. No test was skipped or excluded. No live request was made: every M4 test injects a fake or synthetic transport. The Ruff format file count is recorded verbatim from the final run; the gate claim rests on the exit status and the absence of any file to reformat, not on interpreting that count.

### M4 Worktree Evidence

Snapshot taken after M4 implementation and the architecture and source-verification docs, before this evidence block was appended:

```text
git status --short --untracked-files=all
 M AGENTS.md
 M docs/PRD.md
 M docs/fifth-pick/architecture.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
?? docs/fifth-pick/source-verification.md
?? src/fifth_pick/sources/__init__.py
?? src/fifth_pick/sources/base.py
?? src/fifth_pick/sources/fixtures.py
?? src/fifth_pick/sources/normalize.py
?? src/fifth_pick/sources/odds_api.py
?? src/fifth_pick/sources/quota.py
?? src/fifth_pick/sources/transport.py
?? tests/fixtures/odds_api/README.md
?? tests/fixtures/odds_api/events.json
?? tests/fixtures/odds_api/odds-evt-bos-nyk-20261115.json
?? tests/fixtures/odds_api/odds-evt-lal-dal-20261115.json
?? tests/test_normalize.py
?? tests/test_odds_api.py
?? tests/test_quota.py
```

```text
git diff --stat
 AGENTS.md                                          |  2 +-
 docs/PRD.md                                        |  4 +++
 docs/fifth-pick/architecture.md                    | 41 +++++++++++++++++++---
 docs/fifth-pick/gates.md                           | 24 +++++++++++++
 .../superpowers/plans/2026-11-14-fifth-pick-mvp.md |  4 +++
 5 files changed, 70 insertions(+), 5 deletions(-)
```

```text
git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)

git status --short -- docs/superpowers/specs/2026-11-13-fifth-pick-design.md
(no output)
```

No M4 commit was made. The frozen design specification and Evolution 00–08 are unchanged. `AGENTS.md`, `docs/PRD.md`, and the implementation plan contain only the previously authorized M4 status and authorization addenda; `docs/fifth-pick/architecture.md` and `docs/fifth-pick/gates.md` are updated with M4 content. The M4 paths listed above are the only implementation additions, and no M5 files are present.

Ignored Python bytecode caches exist under `src/fifth_pick/__pycache__/`, `src/fifth_pick/sources/__pycache__/`, and `tests/__pycache__/` (confirmed by `git status --short --ignored`). They are git-ignored and untracked, and they were created by the verification runs. Removing them is not possible under this session's authorized command allowlist, so they are disclosed here rather than reported as cleaned. The historical Evolution caches listed as ignored (`evolution-08/tests/__pycache__/`, `src/__pycache__/`, `src/e6_context/__pycache__/`, `src/e7_memory/__pycache__/`, `src/grad_mcp/__pycache__/`) were not created or modified by M4 and were left untouched.

### M4 Quota Preflight Fix — Reported Remaining

Joseph provided the regression evidence (two failing tests) and authorized a minimal quota-preflight fix in `src/fifth_pick/sources/odds_api.py` only. No live calls and no commit.

#### RED Before Fix (provided)

`uv run python -m unittest discover -s tests` ran 151 tests and failed with exactly 2 expected failures:

```text
Ran 151 tests
FAILED (failures=2)
test_reported_remaining_below_estimate_fails_closed_before_odds
test_reported_remaining_below_next_event_fails_closed_before_odds
AssertionError: QuotaExhaustedError not raised
```

#### Fix

- In `fetch_board()` (`src/fifth_pick/sources/odds_api.py`): after computing the estimated board cost, if provider-reported `x-requests-remaining` is present and less than the complete estimate, raise `QuotaExhaustedError` before starting odds requests.
- Before each event-odds request, if reported remaining is present and less than the cost for the remaining events (`remaining_events * len(markets)`), raise `QuotaExhaustedError` before that request.
- Caller-budget checks, request headers/URLs, transport, and all other source/request constraints preserved; no tests altered.

#### GREEN Full Discovery After Fix

```text
uv run python -m unittest discover -s tests
.......................................................................................................................................................
----------------------------------------------------------------------
Ran 151 tests in 1.505s

OK
```

#### Final Gate Results

```text
uv run ruff check
All checks passed!

uv run ruff format --check
66 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
.......................................................................................................................................................
----------------------------------------------------------------------
Ran 151 tests in 1.505s

OK
```

All four commands exited `0`. No live request was made. No commit was made.

## M5 Snapshot Workflow Verification

M5 was explicitly authorized in Joseph's current instruction after M4 acceptance. The implementation is limited to the frozen snapshot workflow; its tests use synthetic M4 `SourceBoard` values and temporary storage roots. No live API request is required or was made. A narrow M4 provenance metadata extension marks built-in `UrllibTransport` boards `LIVE`, synthetic `FixtureTransport` boards `FIXTURE`, and unmarked custom transports `UNKNOWN`; it does not change the approved request shape or behavior. The mode is stamped by `OddsApiClient` and is not a `BoardProvenance` constructor or `dataclasses.replace` field. M5 rejects `UNKNOWN` and stores the mode to prevent fixtures being presented as live evidence.

### TDD RED Evidence

Before the snapshot workflow existed, the required full discovery command failed on the M5 module-presence assertion:

```text
uv run python -m unittest discover -s tests
FAIL: test_m5_snapshot_workflow_module_exists (test_snapshots.SnapshotModuleTests.test_m5_snapshot_workflow_module_exists)
AssertionError: False is not true : M5 snapshot workflow module is missing
Ran 153 tests
FAILED (failures=1)
```

Additional regression tests were added before correcting demonstrated gaps in batch ledger idempotency, missing-projection retry windows, canonical identity binding, event-time consistency, and persisted ledger validation. The full unittest command was rerun after each correction.

The independent M5 reviewer then identified two edge cases. New regression tests reproduced both before the narrow fixes:

```text
uv run python -m unittest discover -s tests
FAIL: test_early_absent_snapshot_3_does_not_miss_open_snapshot_2
FAIL: test_source_update_after_retrieval_fails_closed
Ran 182 tests
FAILED (failures=2)
```

The fix preserves an open Snapshot 2 window after an early absent-candidate Snapshot 3 attempt and rejects a source update later than its retrieval. Earlier source `last_update` timestamps remain valid and are retained as provenance.

The next read-only review identified persistence-only timestamp checks. Regression tests failed before adding ledger read validation:

```text
uv run python -m unittest discover -s tests
FAIL: test_persisted_snapshots_require_consistent_event_tipoff
FAIL: test_persisted_source_update_after_retrieval_fails_closed
Ran 186 tests
FAILED (failures=2)
```

Ledger loading now rejects source update timestamps later than retrieval and event tipoff changes across snapshots for one candidate key. The M5 authorization addenda are undated because Joseph's current instruction did not provide an authorization date.

The reviewer re-review found two additional timing cases; their regression tests failed before correction:

```text
uv run python -m unittest discover -s tests
FAIL: test_projection_retrieved_before_board_request_fails_closed
FAIL: test_snapshot_3_recorded_after_tipoff_fails_closed
Ran 184 tests
FAILED (failures=2)
```

Board validation now rejects a system retrieval timestamp preceding the request that returned the board, and persisted Snapshot 3 entries must have a system recording timestamp before tipoff. Provider `last_update` may still predate the request.

The final reviewer pass identified an additional post-tipoff case. Its regression failed before moving the missed-slot check ahead of the T-25 eligibility check; the same review also exposed stale M3/M4 control-status text in `AGENTS.md`:

```text
uv run python -m unittest discover -s tests
FAIL: test_post_tipoff_collection_marks_old_snapshot_3_projection_missed
Ran 187 tests
FAILED (failures=1)
```

M5 now records Snapshot 3 as missed when collection occurs after tipoff even if the projection timestamp is earlier than T-25. `AGENTS.md` now points to the implemented M3 identity/authorization and M4 platform controls and distinguishes M6 functionality that remains unbuilt.

The empty-board schedule-conflict regression also failed before the absent-candidate path began checking the persisted event tipoff:

```text
uv run python -m unittest discover -s tests
FAIL: test_empty_board_tipoff_change_fails_closed_without_missed_slot
Ran 197 tests
FAILED (failures=1)
```

The final reviewer found persisted slot ordering was not validated. The orphaned and reordered ledger tests failed before adding cross-row slot-state checks:

```text
uv run python -m unittest discover -s tests
FAIL: test_persisted_snapshot_2_requires_snapshot_1_first
FAIL: test_persisted_ledger_rejects_snapshot_2_before_snapshot_1
FAIL: test_persisted_snapshot_3_requires_snapshot_2_or_miss_first
Ran 194 tests
FAILED (failures=3)
```

The source-mode provenance tests also failed before the M4 metadata extension:

```text
uv run python -m unittest discover -s tests
FAIL: test_fixture_board_provenance_is_labeled_fixture
FAIL: test_fixture_origin_is_preserved_in_snapshot
FAIL: test_unknown_evidence_origin_fails_closed
Ran 190 tests
FAILED (failures=3)
```

The BoardProvenance API initially still exposed a fixture-mode mutator. Its regression failed before that mutator was removed:

```text
uv run python -m unittest discover -s tests
FAIL: test_board_provenance_has_no_caller_fixture_mode_setter
Ran 195 tests
FAILED (failures=1)
```

The relabel regression then failed before making evidence mode non-init provenance metadata:

```text
uv run python -m unittest discover -s tests
FAIL: test_fixture_evidence_mode_cannot_be_relabelled_live
Ran 195 tests
FAILED (failures=1)
```

The reviewer also found that a persisted missed-slot marker could disagree with its Snapshot 1 player/event. The regression failed before the ledger cross-check was added:

```text
uv run python -m unittest discover -s tests
FAIL: test_persisted_missed_slot_must_match_snapshot_1_identity
Ran 196 tests
FAILED (failures=1)
```

The late-S3 retry and persisted provider-name excerpt checks also failed before correction:

```text
uv run python -m unittest discover -s tests
FAIL: test_absent_snapshot_3_can_retry_after_t20_before_tipoff
FAIL: test_snapshot_excerpt_provider_name_must_be_nonempty_text
Ran 199 tests
FAILED (failures=2)
```

The final Snapshot 3 ordering regression failed before collection rejected an observation older than Snapshot 1:

```text
uv run python -m unittest discover -s tests
FAIL: test_snapshot_3_source_retrieval_must_follow_snapshot_1
Ran 200 tests
FAILED (failures=1)
```

The persisted-miss boundary test failed before ledger validation required Snapshot 3 misses to be recorded at or after tipoff:

```text
uv run python -m unittest discover -s tests
FAIL: test_persisted_snapshot_3_miss_before_tipoff_fails_closed
Ran 201 tests
FAILED (failures=1)
```

Event-time conflict tests then failed before collection and persisted-ledger checks were keyed by event rather than candidate:

```text
uv run python -m unittest discover -s tests
FAIL: test_persisted_event_tipoff_is_consistent_across_candidates
FAIL: test_tipoff_change_blocks_new_candidate_for_existing_event
Ran 203 tests
FAILED (failures=2)
```

The collection-time ordering regression failed before Snapshot 2 rejected a source/recording clock that regressed behind Snapshot 1:

```text
uv run python -m unittest discover -s tests
FAIL: test_snapshot_2_recording_time_must_follow_snapshot_1_recording
Ran 205 tests
FAILED (failures=1)
```

### Final M5 Gates

Observed after M5 implementation and documentation:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
70 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 205 tests in 13.294s

OK
```

All four commands exited `0`. The 205-test full suite includes the 51 M5 snapshot tests, two M4 evidence-mode tests, and all prior M1-M4 and historical discovery tests; no live API call was made. M5 snapshot payload excerpts are derived from the M4 source projections and remain separate from Joseph-reported live verification evidence. No commit was made.
