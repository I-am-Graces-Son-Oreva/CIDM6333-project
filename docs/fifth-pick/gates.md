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

## M5 Independent Reviewer Checkpoint

Reviewer verdict: `PASS`, findings: none. The read-only review covered M5 snapshot timing, retry/no-backfill behavior, ledger validation, provenance, platform separation, identity/authorization, fixture/live evidence mode, and M5-only scope. The reviewer accepted the gate outputs and repository/session claims as supplied evidence; it did not run shell commands or independently inspect Git state. No M6 work began before this PASS checkpoint.

## M6 Authorization and Scope

After this M5 `PASS`, Joseph authorized M6 evidence validation, frozen-methodology evaluation, confidence guards, candidate auditing, and ranking only. Acceptance is synthetic/offline. No live API request, M7 work, frozen-spec or Evolution change, or commit is authorized. The pre-existing M5 reviewer checkpoint above is retained unchanged. The frozen design specification remains unmodified.

## M6 RED and Initial Gate Failures

Before M6 methodology and ranking implementation, full discovery reproduced the expected incomplete implementation:

```text
uv run python -m unittest discover -s tests
Ran 227 tests
FAILED (failures=14)
```

The failures were in the unimplemented `evaluate_candidate()` and `rank_candidates()` paths. Added M6 regression tests also exposed missing evidence serialization, accepting out-of-order snapshot records, malformed confidence judgments, unauthorized audit ranking, and invalid or overlapping near-tie decisions.

The first M6 mechanical gate attempt recorded these failures before correction:

```text
uv run ruff check
Found 26 errors.

uv run ruff format --check
6 files would be reformatted

uv run ty check
Found 7 diagnostics
```

No gate was weakened and no test was excluded. Formatting, imports/types, malformed-input handling, confidence guards, and ranking validation were corrected. Full discovery includes the existing M1-M5 tests and all M6 tests; no live source access was used.

## M6 Implementation Decisions

- History summaries are measured against the actual Snapshot 3 projection (`33.5` in the synthetic case), which yields four higher and four lower outcomes for the supplied last-eight fixture. The prior `3/4` expectation used a `34.0` line inconsistent with Snapshot 3 and was corrected.
- The frozen Senior list excludes Karl-Anthony Towns. Senior LOWER tests now use authorized Senior Luka Doncic; the separate Karl-Anthony Towns foul-trouble test remains. This corrects the test fixture, not the frozen classification.
- The frozen specification leaves “approximately equal” non-Senior candidates qualitative. M6 permits discretionary tie-breaking only when candidates share confidence, category/direction/platform/event context, evidence-kind/effect/significance and facts, history sample counts/outcome sequence, and material-gap signatures; one slot must remain, and the decision must cite evidence and explain the preference. The pair must be adjacent so the decision cannot cross any other candidate. This restrictive operational definition avoids a numeric score; if it is too narrow, a legitimate discretionary comparison may remain untied for Joseph.
- M6 serializes audits and rankings and atomically writes `candidates.json` under the injected `RunStore` run directory. It does not expose an analyze CLI command or provide a full run orchestrator; those integrations remain outside M6.

## M6 Pre-Review Gates

Observed after the M6 implementation, tests, and documentation:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 241 tests in 18.446s
OK
```

All four commands exited `0`. The full discovery run includes 36 M6 tests in addition to the 205-test pre-M6 suite. M6 acceptance used only synthetic/offline evidence; no live API request was made. M7 remains blocked until the independent M6 reviewer returns `PASS`. No commit was made.

## M6 Pre-Review Worktree Evidence

Snapshot after M6 implementation and final gates:

```text
git status --short --untracked-files=all
 M AGENTS.md
 M docs/PRD.md
 M docs/fifth-pick/architecture.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
?? src/fifth_pick/evidence.py
?? src/fifth_pick/methodology.py
?? src/fifth_pick/ranking.py
?? tests/fixtures/evidence/README.md
?? tests/fixtures/evidence/m6-history.json
?? tests/m6_support.py
?? tests/test_evidence.py
?? tests/test_methodology.py
?? tests/test_ranking.py
```

```text
git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)

git status --short -- docs/superpowers/specs/2026-11-13-fifth-pick-design.md
(no output)
```

No commit was made. The M5 PASS checkpoint was preserved; M6 review remains pending.

## M6 Independent Review and Correction Pass

The independent read-only M6 reviewer returned `FAIL`. It identified five findings: ranking trusted caller-provided authorization/Senior flags; the near-tie signature omitted meaningful gaps and outcome history; unavailable H2H/incomplete last-8 could be omitted from audits; incomplete unauthorized cases returned caller gap details before authorization; and the planned fixture `candidates.json` artifact was absent.

One test-first correction pass addressed those findings:

- `rank_candidates()` now rechecks canonical registry equality, candidate-key identity, exact category/direction authorization, and Senior classification from authoritative config. Forged outside-universe qualified audits cannot rank.
- The near-tie signature now compares player-market context, evidence kinds/effects/significance, summarized history outcomes, and material-gap details in addition to confidence. Tests reject mismatched evidence strength, material gaps, and overlapping discretionary decisions.
- Missing H2H and unavailable/incomplete last-8 history now produce explicit minor `EvidenceGap` records by default. A caller can mark missing evidence critical when the recommendation materially depends on it, following frozen A9.
- Authorization now precedes incomplete-snapshot status and caller-supplied gap disclosure. Unauthorized incomplete candidates return `BLOCKED` without evidence/gaps.
- `write_candidates()` reruns ranking validation and atomically writes `candidates.json` inside the validated `RunStore` run directory. A temporary-root test verifies the output path and contents.

The reviewer workflow permits one correction pass; no re-review was dispatched. The recorded independent verdict therefore remains `FAIL`, notwithstanding the implemented corrections and their tests. Joseph's review/decision is required before treating M6 as accepted or beginning M7.

## M6 Post-Correction Gates

Observed after the single reviewer-correction pass, its regression tests, and documentation:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 248 tests in 19.876s
OK
```

All four commands exited `0`. The 248-test suite is the 205-test pre-M6 suite plus 43 M6 tests. It includes forged-audit authorization and Senior rechecks, material near-tie gaps/history, missing-history disclosures, authorization-before-gap output, and atomic `candidates.json` writing. Acceptance remained offline; no live API request was made. The independent reviewer verdict remains `FAIL` because no re-review was dispatched after the correction pass. M7 remains blocked for Joseph's decision.

Post-correction repository state:

```text
git status --short --untracked-files=all
 M AGENTS.md
 M docs/PRD.md
 M docs/fifth-pick/architecture.md
 M docs/fifth-pick/gates.md
 M docs/superpowers/plans/2026-11-14-fifth-pick-mvp.md
?? src/fifth_pick/evidence.py
?? src/fifth_pick/methodology.py
?? src/fifth_pick/ranking.py
?? tests/fixtures/evidence/README.md
?? tests/fixtures/evidence/m6-history.json
?? tests/m6_support.py
?? tests/test_evidence.py
?? tests/test_methodology.py
?? tests/test_ranking.py

git status --short -- evolution-00 evolution-01 evolution-02 evolution-03 evolution-04 evolution-05 evolution-06 evolution-07 evolution-08
(no output)

git status --short -- docs/superpowers/specs/2026-11-13-fifth-pick-design.md
(no output)
```

No commit was made. Only M6 authorization, implementation, tests, and architecture/gate evidence are in the worktree; the frozen specification and Evolution 00–08 are unchanged.

## M6 Latest Ranking Findings and Correction

The fresh reviewer returned `FAIL` with three ranking findings: near-tie signatures omitted history outcome sequences and recorded facts; nonadjacent pair reordering could cross Senior LOWER candidates; equal-confidence ordering used lexicographic signal labels rather than qualitative evidence strength.

Test-first regression coverage reproduced all three findings. Additional regressions cover disclosed history versus absent history and retaining the most material concern when an evidence kind has multiple signals. The narrow `ranking.py` correction now:

- Compares near-ties using candidate context, every evidence kind/effect/significance and structured facts, history sample counts and ordered outcomes, and material gaps.
- Allows a discretionary reordering only for adjacent candidates, so no intervening candidate, including Senior LOWER, can be crossed.
- Uses qualitative Pareto dominance after Senior HIGHER priority and existing confidence: stronger supporting evidence, fewer/less significant concerns and gaps, and favorable history comparisons when sample availability is comparable. It preserves stable input order for incomparable profiles rather than applying enum/text lexical order or an aggregate score.

## M6 Latest Ranking Correction Gates

Observed after the three ranking corrections and regression tests:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 254 tests in 19.694s
OK
```

All four commands exited `0`. The 254-test suite includes the 205-test pre-M6 suite and 49 M6 tests. M6 remains offline; no live API request was made. No M7 work, commit, or push occurred. A new independent configured read-only reviewer is pending.

## M6 Final Near-Tie Signature Correction

The latest reviewer identified one remaining hole: near-tie signatures did not include claims, excerpts, full provenance, raw history samples, or candidate projection. Five test-first regressions independently changed each of those recorded inputs. Before the signature correction, the observed RED was:

```text
uv run python -m unittest discover -s tests
Ran 259 tests
FAILED (failures=5)
```

`_evidence_signature()` now includes the candidate projection; every evidence claim, excerpt, provenance field, structured fact, and normalized raw sample; and history sample counts and ordered outcome patterns. It does not calculate scores or use those values to rank; they only prevent materially different records from entering the bounded discretionary near-tie path. The five RED tests now pass.

Final M6 gates after this correction:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 259 tests in 20.699s
OK
```

All four commands exited `0`. The 259-test suite is the 205-test pre-M6 suite plus 54 M6 tests. Acceptance remained offline; no live request occurred. Evolution 00-08 and the frozen design remain unchanged. No M7 work, commit, or push occurred. A fresh independent read-only reviewer is pending.

## M6 Final Qualification-Revalidation Correction

The sole remaining reviewer finding was that `rank_candidates()` could trust caller-forged `CandidateAudit` `QUALIFIED`/`HIGH` fields without verifying that the existing M6 methodology and evidence supported them. Regression coverage verifies that ranking excludes a qualified/high audit with empty evidence, excludes a qualified/high audit with only one cited IMPORTANT supporting signal, and excludes forged status/confidence that conflict with the audit's retained `ANALYSIS_ONLY` disposition.

The first RED run exposed three intended ranking failures and four existing `make_audit()` fixture `TypeError`s caused by callers supplying `status`/`trust_labels` that the helper did not accept. The helper signature was corrected without changing production behavior. The clean RED run then reproduced only the three expected assertion failures:

```text
uv run python -m unittest discover -s tests
Ran 262 tests
FAILED (failures=3)
```

The correction keeps the evidence citation, HIGH/MEDIUM confidence, disposition, sufficient-evidence, major-concern, and Senior LOWER checks in `methodology.py`. `evaluate_candidate()` and the new audit revalidation predicate share those M6 checks. The audit retains the judgment fields needed to revalidate; ranking calls the predicate only after its authoritative identity/authorization/Senior rechecks and excludes unsupported claims. A qualitative-ranking test fixture was also corrected to remove a support citation when it changes that evidence item to a concern; the comparison and expected ordering remain unchanged.

Fresh final gates after the correction and M6 documentation update:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 262 tests in 28.525s
OK
```

All four commands exited `0`. The 262-test suite remains the 205-test pre-M6 suite plus 57 M6 tests. Acceptance used offline fixtures only; no live API/network request was made. The current independent read-only M6 review is pending. Evolution 00-08 and the frozen design specification remain unchanged. No M7 work, commit, or push occurred.

## M6 Architecture-Level Ranking Trust Boundary

The repeated ranking findings had one root cause: `CandidateAudit` was both a methodology output and ranking's proof that methodology had run. The record is frozen but caller-replaceable, so individually rechecking status, confidence, authorization, or evidence left all other derived fields available to ordering, disclosure, serialization, and near-tie comparison. Findings involving forged authorization/Senior flags, methodology status/confidence, evidence/provenance, history, gaps, projection, and near-tie signatures were manifestations of this same output-trust boundary.

The architecture now makes `CandidateCase` the sole ranking input. `rank_candidates()` calls the existing `evaluate_candidate()` for each case and ranks only the fresh `CandidateAudit` results. A caller-supplied `CandidateAudit` is rejected as the wrong input type; none of its candidate identity/projection, status, confidence, authorization, Senior, evidence/provenance, history, gaps, movement, rationale, rules, exclusions, citations, or disclosure fields can affect ranking. The methodology layer validates exact registry identity and authorization before evidence analysis/disclosure, and derives classification, history, gaps, movement, status, confidence, and audit text from the typed case. Ranking still uses the existing qualitative comparator and constrained near-tie decision; the near-tie signature now includes all gap details, including MINOR gaps.

The architecture-level RED was observed before changing the API:

```text
uv run python -m unittest discover -s tests
Ran 265 tests
FAILED (failures=23, errors=2)
```

The 23 failures were adversarial `CandidateAudit` variants that the old ranking boundary accepted instead of rejecting; the two errors were new `CandidateCase` inputs rejected by the old audit-only API. After converting the ranking behavior tests to cases and adding the missing minor-gap signature regression, restoring the old material-gap-only signature produced this independent RED:

```text
uv run python -m unittest discover -s tests
Ran 266 tests
FAILED (failures=1)
```

The failure was `test_near_tie_rejects_different_minor_gap_disclosures`; including all recorded gaps in the signature resolved it.

Final M6 architecture-correction gates:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 268 tests in 26.032s
OK
```

All four commands exited `0`. The suite includes 205 pre-M6 tests and 63 M6 tests. Existing M6 controls remain in force: qualitative evidence dominance and stable incomparable ordering, authoritative Senior and authorization evaluation, adjacent-only near-tie discretion with full evidence/history/gap signatures, generated missing-history disclosures, authorization-before-disclosure, and atomic run-scoped `candidates.json`. Acceptance used deterministic offline fixtures only. Evolution 00-08 and the frozen design specification remain unchanged; no live request, M7 work, commit, or push occurred. The broad independent read-only M6 review is pending.

### Final Case-Validation Closure After Broad Review

The broad reviewer returned `FAIL` with five findings. All five were defects in the same remaining boundary: the methodology accepted a caller-built `CandidateCase` but did not canonicalize or validate every cross-record relationship and source claim before producing the audit. One coherent correction extended the M6 case/evidence validation boundary rather than adding ranking-specific checks:

- Snapshot sets now agree on event start; Snapshot 2's target is recomputed using the existing M5 midpoint function; provider-player excerpts must match the canonical player or a registered alias; missed markers must match candidate ID/key/event and be unique by slot.
- Live supporting evidence is rejected because M6 has no supporting-source retrieval path. Fixture provenance remains explicit and validated.
- Repeated MATCHUP, LAST_8, or SAME_SEASON_H2H records fail closed; validated evidence and history summaries are canonicalized so tuple order cannot change history, ranking, or serialized audit output.
- HIGH confidence counts distinct underlying supporting signals rather than duplicate records with different evidence IDs.
- Regression tests cover each reviewer finding, while the ranking boundary continues to accept only cases and re-run the methodology.

Before the closure, the new adversarial regressions produced the observed RED:

```text
uv run python -m unittest discover -s tests
Ran 276 tests
FAILED (failures=8)
```

Final gates after the single coherent correction pass:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 276 tests in 27.729s
OK
```

All four commands exited `0`. The full suite is 205 pre-M6 tests plus 71 M6 tests. Acceptance remained offline; the M6 supporting-evidence validator now fails closed on all `LIVE` evidence and no live request was made. Evolution 00-08 and the frozen design specification remain unchanged. No M7 work, commit, or push occurred. The one final independent read-only M6 review is pending.

## M6 Sealed Canonical Output Boundary

The final requested architecture completes one trust transition:

```text
raw CandidateCase
  -> evaluate_candidates(): validate/canonicalize, then run M6 methodology
  -> sealed MethodologyResult containing immutable CandidateAudit records
  -> rank_candidates()/write_candidates(): accept only the registered, unmodified result
```

The prior raw-case ranking API was replaced. Ranking does not inspect raw cases, reconstruct audits, or accept standalone audits. A `MethodologyResult` constructed or replaced by a caller is not in the methodology's process-local result registry and fails closed. This resolves the remaining trust gap where a typed case could bypass the method-to-ranking handoff even after its fields were validated.

The same canonicalization pass now reuses `validate_snapshot_sequence()` from the M5 ledger contract before incomplete-case returns; validates approved source/reference, event start, Snapshot 2 target, slot/order timing, missed-marker identity/uniqueness/timing; preserves snapshots and missed markers in canonical audits; fails closed on unavailable live supporting-source retrieval; redacts evidence IDs, claims, excerpts, provenance, fact keys/values, sample text, gaps, methodology rationale/disclosure, and serialized snapshot text through the existing redactor; canonicalizes evidence/history ordering; rejects duplicate summary context; deduplicates underlying HIGH signals independent of EvidenceKind labels; and preserves the strongest gap per kind/reason. Near-tie signatures include the full validated snapshot path, including projection sequence, provenance, and late Snapshot 3 state, plus all evidence/history/gap details.

The M6 regressions observed RED before their corresponding corrections. The final snapshot/missed-marker audit regression specifically failed before `CandidateAudit` serialized the validated missed records:

```text
uv run python -m unittest discover -s tests
Ran 288 tests
FAILED (errors=1)
```

The prior broad-review RED runs also remain recorded above; no reviewer finding was patched outside this single methodology-owned trust transition. Final four-gate evidence and the final independent reviewer verdict are pending.

## M6 Final Canonicalization Trust Boundary

The final broad reviewer returned `FAIL` with six remaining paths within one root cause: M6 did not yet establish a single complete canonical state before ranking and serialization. Findings covered fabricated snapshot source/reference data; incomplete snapshot/marker checks before partial-case returns; unredacted facts and samples; confidence signals duplicated by changing `EvidenceKind`; weaker gaps overwriting stronger gaps; and snapshot history/late state missing from audits and near-tie comparison.

The final architecture is now:

```text
raw CandidateCase
  -> evaluate_candidates(): validate, canonicalize, and evaluate with M6 methodology
  -> immutable MethodologyResult registered only by the methodology factory
  -> rank_candidates()/write_candidates(): accept only that unmodified result
```

The ranking layer does not receive raw cases, reconstruct audits, or accept standalone/replaced audits or caller-created/replaced result wrappers. The methodology boundary reuses the M5 ledger-order contract for all available snapshots and missed markers before incomplete-case returns; checks the approved board source and event-bound reference; verifies exact registry/provider identity, cross-snapshot event start, Snapshot 2 midpoint, marker IDs/slots/times, and existing Snapshot 3 rules; rejects all `LIVE` supporting evidence while the M6 supporting-source retrieval path is unavailable; canonicalizes/redacts evidence, judgments, gaps, and output text; sorts evidence/history deterministically; rejects ambiguous duplicate history-context records; counts distinct underlying HIGH support signals independent of caller `EvidenceKind`; and retains only the strongest gap per kind/reason. Canonical audits serialize full snapshot observations, provenance, missed markers, and late state; near-tie signatures use the validated snapshot path plus complete evidence, history, and gap details. The existing qualitative ranking, Senior priority, stable incomparable ordering, adjacent-only discretion, authorization ordering, and atomic run-scoped persistence remain downstream of that transition.

Observed RED runs for this correction sequence:

```text
uv run python -m unittest discover -s tests
Ran 281 tests
FAILED (failures=2, errors=21)

uv run python -m unittest discover -s tests
Ran 284 tests
FAILED (failures=3)

uv run python -m unittest discover -s tests
Ran 284 tests
FAILED (failures=1)

uv run python -m unittest discover -s tests
Ran 288 tests
FAILED (errors=1)
```

Those RED runs exposed, respectively, the missing sealed methodology-result boundary, evidence/gap text redaction and strongest-gap handling, distinct-signal relabeling, and missed-marker audit serialization. They were resolved by the single canonicalization pipeline above rather than ranking-specific repairs.

Final gates after the canonicalization boundary and documentation updates:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
78 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 288 tests in 31.063s
OK
```

All four commands exited `0`. The suite is 205 pre-M6 tests plus 83 M6 tests. Acceptance uses offline fixtures; no live API/network request was made. Evolution 00-08 and the frozen design specification remain unchanged. No M7 work, commit, or push occurred. The final independent read-only M6 reviewer is pending.

## M6 Latest Structural Trust-Boundary Remediation

The latest independent review named three remaining structural defects: the mutable `MethodologyResult` `WeakSet` trust registry, LIVE snapshots that were only internally validated rather than bound to M5 records, and duplicate `PerformanceSample` identities that could alter history summaries. Regression tests first reproduced the defects, including caller self-registration and bypass mutation, fabricated LIVE snapshots, all previously forged audit fields, duplicate-history ordering changes, and conflicting same-game values. The observed RED was:

```text
uv run python -m unittest discover -s tests
Ran 293 tests
FAILED (failures=31)
```

A follow-up regression then demonstrated that a module-level private seal could itself be imported and used to construct a forged result. The observed RED was:

```text
uv run python -m unittest discover -s tests
Ran 294 tests
FAILED (failures=1)
```

The result type, its seal, and its constructor/checking functions now live in one private factory closure; `evaluate_candidates()` is the only supported producer, and the public module has no registration set or seal constant.

The structural corrections use the existing boundaries:

- `MethodologyResult` is now a tuple-backed immutable result with a closure-private constructor seal. The mutable registry is removed; `rank_candidates()` and `write_candidates()` still accept only canonical methodology output.
- LIVE `CandidateCase` inputs name an M5 run and require the existing `SnapshotWorkflow` to read its validated snapshot ledger and missed markers. Every supplied record must equal the corresponding persisted record, including source mode and provenance. Fixture cases continue through the explicit offline path.
- `PerformanceSample` identity is `(played_at, opponent, season)`. Identical duplicates are canonicalized once; differing values for one identity raise `EvidenceError` before history summaries.

The focused offline regression also populated an M5 fixture ledger through `SnapshotWorkflow` and verified that relabeling those persisted fixture records as LIVE does not qualify them.

### Final Structural Remediation Gates

Observed after the three structural corrections and their adversarial regressions:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
79 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 294 tests
OK
```

All four commands exited `0`. This full suite includes 205 pre-M6 tests and 89 M6 tests. Acceptance used offline fixtures only; no live network/API request was made. Evolution 00-08 and the frozen design specification remain unchanged. No M7 work, commit, or push occurred. The single final broad independent M6 review is reported in the task closeout.

## M6 Caller-Case Ranking Boundary

The final independent reviewer demonstrated that `tuple.__getitem__(valid_result, 0)` recovered the closure-held result seal and allowed a forged audit to reach ranking and `candidates.json`. The new regressions were added before the structural change. Against the old result-accepting API, full discovery showed:

```text
uv run python -m unittest discover -s tests
Ran 295 tests
FAILED (failures=28, errors=21)
```

The correction removes `MethodologyResult`, the seal, and the result factory altogether. `rank_candidates()` and `write_candidates()` accept only `tuple[CandidateCase, ...]`. Ranking invokes the existing M6 evaluator inside its own call and immediately consumes its local canonical audits; persistence uses the same ranking path. A caller-supplied audit tuple or result-shaped object is rejected before ranking or writing. No methodology implementation was duplicated.

The regression coverage now exercises the recovered internal-field attack as an untrusted result-shaped object, confirms valid cases retain their established ranking, and checks forged audits/status/confidence/evidence/provenance/history/gaps remain rejected. Existing M5 LIVE-ledger binding and duplicate-sample tests remain in the suite. Final four-gate evidence and the one final independent read-only acceptance verdict follow.

### Final Gates After Caller-Case Boundary

```text
uv run ruff check
All checks passed!

uv run ruff format --check
79 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 295 tests
OK
```

All four commands exited `0`. M6 acceptance remained offline; no live API/network request occurred. No Evolution 00-08 or frozen-design changes, M7 work, commit, or push were made.

## M6 M5-Owned Ledger Access Boundary

The latest independent reviewer found that a caller could override methods on a supplied `SnapshotWorkflow` and make fabricated records appear to come from M5. Tests were added before changing that path. Against the caller-supplied-workflow implementation, full discovery observed:

```text
uv run python -m unittest discover -s tests
Ran 300 tests
FAILED (failures=3)
```

The correction removes workflow/reader parameters from M6 evaluation and ranking. M6 requires the injected exact `RunStore` for LIVE cases and reads through M5's module-owned `read_snapshot_ledger(store, run_id)` function. That function performs the existing ledger decoding, identity/slot checks, and `validate_ledger_order()`; `SnapshotWorkflow` read methods delegate to the same M5-owned parser. Caller overrides of `read()`, `read_missed()`, or `_read_entries` are not consulted by M6. The offline LIVE-mode integration test stamps deterministic fixture boards at the existing M4 transport-mode seam, records them using M5, and confirms those records qualify only when read from that M5 ledger. Other regressions confirm fabricated snapshot and missed-marker records fail despite overridden workflow methods/state, and fixture cases remain independent of a store.

The resulting trust path is `CandidateCase -> M6 evaluation inside ranking/persistence`, with LIVE origin read from M5-owned ledger code and no caller-controlled workflow reader. Final gate evidence and the one final independent read-only acceptance verdict follow below.

### Final Gates After M5-Owned Reader

```text
uv run ruff check
All checks passed!

uv run ruff format --check
79 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 301 tests
OK
```

All four commands exited `0`. The suite includes the new M5 reader override, missed-marker override, `_read_entries` mutation, fake workflow, valid M5 LIVE-ledger, and fixture-path regressions. No live network/API request was made. No Evolution 00-08 or frozen-design changes, M7 work, commit, or push occurred.

## M6 Application-Owned LIVE Storage

The latest reviewer identified caller-selected `RunStore.root` as the remaining LIVE origin bypass. Tests first demonstrated that a caller could submit an M5-shaped ledger from an arbitrary root, while M6 either trusted that store or had no application-owned lookup. The observed RED was:

```text
uv run python -m unittest discover -s tests
Ran 305 tests
FAILED (failures=4)
```

The frozen design requires recorded source provenance, access method, payload hashes, and receipts; the M5 contract defines the operational `var/fifth-pick` root, run-scoped ledger, and receipts. Neither document requires cryptographic signatures or signing keys. `RunStore()`'s application default is now `APPLICATION_STORAGE_ROOT = <project-root>/var/fifth-pick`; `application_run_store()` constructs that path internally. M6 accepts only the `CandidateCase.snapshot_run_id` for LIVE lookup and calls M5's `read_application_snapshot_ledger()`, which resolves the fixed root internally, reuses the existing ledger parser/order validator, and verifies each record against its accepted or missed receipt. `rank_candidates()` and `write_candidates()` do not accept a source `RunStore`; the latter's store is only its candidates.json output location. M5 tests continue using explicitly injected temporary stores.

The regressions cover an arbitrary caller store, a schema-valid altered ledger outside the application root, a mismatched run ID, missing M5 receipts, successful M5-produced LIVE-mode records at the configured root, and fixture evaluation with an empty root. Direct malicious modification of the application data directory is outside the specified frozen threat model and is documented as future filesystem-permission or cryptographic-manifest hardening; M6 adds no signing mechanism.

### Final Gates After Application-Owned Storage

```text
uv run ruff check
All checks passed!

uv run ruff format --check
79 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 305 tests
OK
```

All four commands exited `0`. Acceptance used offline source fixtures only; no live API/network request occurred. No Evolution 00-08 or frozen-design changes, M7 work, commit, or push occurred. The single final independent M6 acceptance verdict follows in the task report.

## M6 Application-Owned LIVE Storage

The subsequent reviewer found that a caller could choose a `RunStore` root containing a schema-valid LIVE ledger. Regressions for application-root resolution, arbitrary store arguments, an external fabricated ledger, run-ID mismatch, legitimate M5 data, fixture isolation, and matching receipts were added before the storage-boundary change. The observed RED was:

```text
uv run python -m unittest discover -s tests
Ran 305 tests
FAILED (failures=4)
```

The frozen design specifies source identifiers, retrieval/source times, access method, excerpts, payload hashes, and receipts. The frozen M5 contract specifies `var/fifth-pick/runs/<run_id>/snapshots/ledger.jsonl` and run-scoped receipts. Neither specifies signatures, keys, or cryptographic ledger authenticity. Therefore M6 uses the application-owned `APPLICATION_STORAGE_ROOT` (`var/fifth-pick`) and M5 `application_run_store()` construction. M6 accepts only the case's `snapshot_run_id`; it cannot receive a store/root. M5's `read_application_snapshot_ledger()` reads that run from the fixed root, reuses the existing decoder/order checks, and requires matching accepted/missed receipts and source provenance. `write_candidates()` may still receive its output `RunStore`, but that value is not used to resolve LIVE source evidence. Tests inject the app-root constant only to isolate temporary M5 runs.

Direct malicious filesystem modification of the application data directory is not detected cryptographically and is not specified by the frozen threat model. Filesystem access controls or signed manifests are future hardening only if Joseph expands that requirement; no signing mechanism is added in M6. Final four-gate evidence and the single final independent M6 acceptance verdict follow below.

## M10 Phase 1 Review Controller and Skills

Phase 1 implements strict typed reviewer parsing, deterministic bounded transitions, deterministic review-cycle IDs, and M2-compatible review receipts in `src/fifth_pick/review.py`. It also adds the four procedure skills and an assurance table. It does not add an OpenCode plugin or Python/OpenCode bridge, alter native Reviewer permissions, or perform the runtime denial experiment.

Baseline gate evidence before Phase 1 changes:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
90 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 424 tests in 259.709s
OK
```

The first test-first RED run occurred before `review.py` existed:

```text
uv run python -m unittest discover -s tests
Ran 425 tests
FAILED (errors=1)
ImportError: No module named 'fifth_pick.review'
```

After adding the parser and transition code but before the skill and assurance artifacts, tests failed only on the not-yet-created authorized documents. A subsequent regression also exposed that direct `ReviewVerdict` construction could accept an unsupported status; typed construction now rejects it, and transitions accept only the supported `ReviewStatus` values. The later pre-final lint run found one line-length issue; the format check reported two files needing formatting, and `ty` caught an optional receipt event key used without narrowing. Those were corrected before the final gate run.

The first independent Phase 1 review returned FAIL because a directly constructed `ReviewCycle` could carry a noncanonical cycle ID or impossible event sequence, and the assurance table cited a stale test name. Regression tests were added first and observed RED:

```text
uv run python -m unittest discover -s tests
Ran 465 tests
FAILED (failures=2)
```

`ReviewCycle` now validates its deterministic identity and phase/correction/event-sequence invariants on construction, so transitions and receipt appends cannot consume those malformed cycle records. The assurance table now cites the actual `test_concerns_escalates_to_joseph` test.

Final Phase 1 gates:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
97 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 465 tests in 244.399s
OK
```

The first concurrent invocation of the final unit gate exceeded its 600-second tool timeout without a failure summary; the isolated rerun above completed successfully. All four gates subsequently exited `0`. These are Phase 1 results only. `docs/fifth-pick/assurance.md` marks plugin discovery/activation/bridge and the actual native-denial acceptance gate **BLOCKED**; no reviewer write attempt or security experiment was performed.

The independent mechanically read-only Phase 1 reviewer returned a second `FAIL` after the one correction allowed by the review-cycle contract. No further implementation correction was made; the result is escalated to Joseph. Remaining findings:

- `src/fifth_pick/review.py`: the `STOPPED` cycle invariant accepts an unreachable zero-correction/event-sequence-2 combination.
- `src/fifth_pick/review.py`: `ReviewEvent`/`ReviewTransition` can be directly constructed without validating event/result/sequence/digest consistency before `append_review_receipts()` persists them.
- `tests/test_review_loop.py`: `test_assurance_table_has_control_and_evidence_per_risk` does not ensure cited evidence exists or prevent prompt/static-config/unavailable-tool claims from being presented as enforcement.

This Phase 1 reviewer verdict is not final M10 acceptance.

## M10 Phase 1 Additional Bounded Correction

Joseph authorized one further bounded correction cycle for STOPPED terminal behavior, event/transition validation before receipt writes, and assurance evidence verification. No plugin, bridge, runtime denial test, permission change, or final M10 acceptance work is included.

The test-first run exposed the new missing controls:

```text
uv run python -m unittest discover -s tests
Ran 481 tests
FAILED (failures=15, errors=4)
```

After correcting test assertion boundaries, the direct STOPPED-state reachability regression remained RED:

```text
uv run python -m unittest discover -s tests
Ran 481 tests
FAILED (failures=1)
```

The implementation now rejects follow-up transitions from `REVIEWED_FOR_JOSEPH`, `ESCALATE_TO_JOSEPH`, and `STOPPED`; restricts STOPPED positions to those reachable from nonterminal invalid inputs; validates event name/result/revision/cycle ID/digest and the exact cycle phase/sequence before receipt writes; and revalidates the complete transition before appending any M2 receipt. The assurance test checks cited test symbols and file paths, gate commands, guidance-only status, and BLOCKED runtime rows.

Final four-gate evidence for this correction cycle:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
97 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 476 tests in 220.290s
OK
```

All four gates exited `0`. A fresh independent read-only Explore assessment returned `PASS` with no findings after checking all three authorized corrections and M1-M9 preservation. The assessment used read/search tools only; it did not invoke the OpenCode-configured `fifth-pick-reviewer` command. This is Phase 1 evidence only, not final M10 acceptance. Plugin loading, the Python/OpenCode bridge, and runtime denial remain BLOCKED.

## M10 Phase 2 Offline Implementation

Joseph authorized the Phase 2 adapter, bridge, and disposable Reviewer denial experiment on 2026-11-17. The implementation adds the strict stdin/stdout Python bridge, an auto-discovered v1 lifecycle adapter, and an explicit JSON metadata envelope for `/fifth-pick-review`. The bridge reconstructs review state from M2 receipts, rejects malformed/conflicting/out-of-order input, and appends only through the existing M2 `RunStore`. The plugin invokes only `uv run --no-sync python -m fifth_pick.review_bridge` using a fixed argument vector with `shell: false`; it registers no permission hook. Production Reviewer permissions and the root Bash allowlist are unchanged.

Test-first bridge/plugin regressions initially failed because the bridge and adapter did not exist. Further RED runs exposed a partial multi-event receipt retry failure and a validly shaped initial verdict with a mismatched artifact digest returning exit status `0`. The bridge now recovers exact receipt prefixes through M2 idempotency and returns `STOPPED` with nonzero status for that digest mismatch. The offline tests cover malformed and duplicate request fields, strict verdicts, M2 run/cycle binding, event ordering, retry/conflict handling, partial-write recovery, exact stdout shape, adapter lifecycle constraints, fixed argv, and the command envelope.

The most recent full unit run after these corrections reported:

```text
uv run python -m unittest discover -s tests
Ran 499 tests
OK
```

Final four-gate evidence after the bounded correction pass and assurance updates:

```text
uv run ruff check
All checks passed!

uv run ruff format --check
101 files already formatted

uv run ty check
All checks passed!

uv run python -m unittest discover -s tests
Ran 499 tests
OK
```

All four gates exited `0`. These offline results do not prove actual host plugin discovery, activation, event delivery, or subprocess invocation.

### Phase 2 Runtime Gates — BLOCKED

Joseph reports `/usr/local/opt/opencode/bin/opencode` version `1.18.20`. This host identity does not prove runtime plugin behavior. The actual OpenCode host was not launched in this session because the active project Bash allowlist denies the host invocation; the allowlist was not broadened or bypassed. No disposable Reviewer write request was made. Plugin activation/event delivery/bridge runtime and the actual correlated native-denial experiment remain **BLOCKED**, not PASS. The Reviewer sentinel and disposable workspace were therefore not created or modified.

## M10 Phase 2 Bounded Correction Pass

Joseph authorized one correction pass limited to material-digest binding, controller-confirmed correction receipts, Reviewer task-call correlation, and concurrent bridge serialization. Tests were added first. The full unittest gate observed expected RED states for the missing digest/call correlation/dispatch-command/lock behavior and for a first `REVISION_DISPATCHED` request whose digest did not match the prior FAIL receipt. The final 499-test run above is GREEN.

The adapter hashes the exact UTF-8 `review_material`, correlates review output with a unique invocation marker and identical OpenCode task `callID`, and only transports the separate controller receipt-confirmation command. The controller dispatches Builder only after receiving a response confirming the persisted `REVISION_ATTEMPT`. The Python bridge serializes each run's receipt-history read/validation/append with a private per-run OS advisory lock under `.review-locks`; the lock file contains no receipt data. M2 models, receipt format, `RunStore` behavior, Reviewer permissions, and the root Bash allowlist remain unchanged.

No host activation test or Reviewer security experiment was run in this correction pass, as Joseph explicitly excluded them. Both runtime gates remain **BLOCKED** pending their separately authorized execution.


### M10 Disposable Runtime Evidence and M9 Prerequisite

- M9 final independent Reviewer PASS with no findings is in local OpenCode session `ses_e14b54779ffebdBI11EtBPvtE2`, part `prt_1eb4bfc630015l2QimZbh07M6O`. Parent session `ses_e1833d963ffeQQqHHZxX0cWhEs` records four passing gates and 424 unit tests in part `prt_1eb4c607d001oeq7L798eYIrw9`, and Joseph's M9 completion statement for commits `60fd576` and `48f82d2` in part `prt_1eb59e04f0010WasVj7q6ehKha`.
- Prior isolated runtime PASS evidence is in the disposable project's `var/test-evidence/m10-routing-4a668301ac3e.jsonl` and `var/fifth-pick/runs/m10-routing-4a668301ac3e/receipts.jsonl`. OpenCode 1.18.20 and local Ollama returned a valid PASS and `REVIEWED_FOR_JOSEPH`; the receipt key and digest matched. That pass recorded all four gates exiting 0 and 507 unit tests.
- The earlier isolated run `var/test-evidence/m10-handoff-12da2b7620fa.jsonl` returned structured STOPPED for an empty verdict, with no receipt.
- At this preparation checkpoint, the original native Reviewer write-denial gate was **BLOCKED**. No denial experiment was conducted at that checkpoint.

### Targeted Dispatch Corrections — Historical FAIL Checkpoint

The new regressions first failed on CLI-wrapped dispatch JSON, identical replay, and concurrent confirmation. After the changes, all four required gates exited 0, including 510 unit tests.

The independent read-only review returned FAIL. It confirmed the Python bridge requires a newly persisted receipt under the run lock, and identified three adapter risks: duplicate JSON keys collapse before schema checks, the launch confirmation checks only the receipt key suffix, and an unhandled bridge stdin error can interrupt structured STOPPED delivery. The isolated FAIL-to-correction run was withheld because the review prerequisite did not pass. The prior isolated PASS and STOPPED artifacts remain the available host evidence. The native denial gate remains **BLOCKED**.

### M10 Final Remediation Gate Run

On 2026-11-18, after remediation of the three findings from the historical FAIL checkpoint above, all four established commands exited `0` on the final implementation baseline.

| Gate | Recorded result |
|---|---|
| `uv run ruff check` | Exit 0, all checks passed |
| `uv run ruff format --check` | Exit 0, 101 files already formatted |
| `uv run ty check` | Exit 0, all checks passed |
| `uv run python -m unittest discover -s tests` | Exit 0, 510 tests in 212.849 seconds, OK |

The independent remediation review returned **PASS** for duplicate-key rejection, exact cycle and receipt confirmation, and structured STOPPED on bridge transport failure. Evidence is in the local Codex transcript `~/.codex/sessions/2026/11/18/rollout-2026-11-18T10-44-39-01a1ef8b-ce59-7710-922f-20b7beabd38f.jsonl`. Line 960 records the first three results and the unittest launch. Line 1015 records the final unittest result. Line 983 records the independent remediation verdict. This is the saved implementation gate run. The subsequent documentation reconciliation did not rerun it.

### M10 End-to-End Correction Path

Run `m10-final-correction-1b5b2abef146` passed the bounded isolated workflow on OpenCode 1.18.20 with local `ollama/qwen3:4b`. The canonical disposable project used matching working directory, `PWD`, and `--dir`, with isolated XDG paths and process-only model overrides. Controller session `ses_e0fdc58e3ffeCSD5sq17hgXUa1` had exactly three child tasks in that workspace: initial Reviewer, one Builder, and second Reviewer.

Evidence paths below are relative to the existing disposable project, `$TMPDIR/fifth-pick-m10.kMXZVL25/project`. Every receipt carries run ID `m10-final-correction-1b5b2abef146` and cycle `review-31a033c0a96aee5ee90b2916258eabc8cce2d3dd2b254983a76ba3844cd1babd`. Each deterministic event key is that cycle plus the suffix shown below.

| Stage | Observed result | Evidence |
|---|---|---|
| Initial Reviewer | Task `01M7R27AJ7WV39CXH07TD88BTV` returned a typed FAIL for `2 + 2 = 5`. Controller returned `REVISION_REQUIRED` with zero corrections used and the matching `-01-review_fail` key. | `var/test-evidence/m10-final-correction-1b5b2abef146-initial-review.jsonl` |
| Dispatch confirmation | The controller returned one fresh launch authorization with correction count 1 and the matching `-02-revision_attempt` key before Builder started. | `var/test-evidence/m10-final-correction-1b5b2abef146-confirmation-response.json` |
| Builder | The single task `01M7R2CK7MSG7B9DGMFDW0PV4X` used local Qwen3 4B and returned exactly `2 + 2 = 4` inline. No Builder tool calls or workspace edits were observed. | `var/test-evidence/m10-final-correction-1b5b2abef146-builder.jsonl` and `var/test-evidence/m10-final-correction-1b5b2abef146-corrected-fixture.txt` |
| Second Reviewer | Task `01M7R2GV3E3FMXQXKR63NGGA5J` returned a typed PASS. Controller returned `REVIEWED_FOR_JOSEPH` with one correction used, none available, and the matching `-03-review_pass` key. | `var/test-evidence/m10-final-correction-1b5b2abef146-rereview.jsonl` |

The complete `REVIEW_FAIL → REVISION_ATTEMPT → REVIEW_PASS` sequence is in `var/fifth-pick/runs/m10-final-correction-1b5b2abef146/receipts.jsonl`. The first two receipts bind to SHA-256 `864b89d282ca79477e5021acd5ee1e1780f93630a8623b4d9477cadc9ef90172`. The final PASS receipt binds to SHA-256 `cc1dba8fb20f329a067166ecb59f3aa1d2cfb2f2b45b77379857972eeb2a56df`, independently recomputed from the exact corrected fixture bytes.

The stopped run `m10-qwen4b-f1748bae08d0` retains its original `REVIEW_FAIL → REVISION_ATTEMPT` sequence and Builder model-resolution error. Its authorization was consumed. The successful fresh run verifies the correction path through post-correction PASS. At this correction checkpoint the original native write-denial gate was **BLOCKED**. The later Route B evidence below gives the current security status. Live second-FAIL/CONCERNS escalation remains **UNVERIFIED**. Offline coverage includes `tests/test_review_loop.py::test_one_correction_then_escalation` and `tests/test_review_loop.py::test_concerns_after_correction_escalates_without_another_correction`. M10 acceptance remains withheld.

### M10 Native Reviewer Tool-Withholding Evidence

Joseph's [2026-11-18 addendum](../superpowers/plans/2026-11-17-fifth-pick-m10-harness-hardening.md#2026-11-18--opencode-11820-native-reviewer-evidence-addendum) authorizes an alternative to request-to-denial evidence for OpenCode 1.18.20. The original Task 5 criteria and historical outcomes above remain in the record.

- The first challenge, `m10-native-withholding-7da85682c373`, timed out. Its provider capture and integrity artifacts are retained. The timeout is inconclusive and is excluded from qualifying evidence.
- The bounded recovery challenge, `m10-native-withholding-2b089c988436`, used the unchanged native Fifth Pick Reviewer in session `ses_e0fc51df8fferaZje4dy4iglVT`, the canonical disposable project, and local-only Ollama. OpenCode's host catalog exposed `edit`, `write`, and `bash` to the host control. Native Reviewer resolution marked all three unavailable under the effective wildcard deny for `edit` and `bash`. The installed-host excerpts show the edit-tool alias mapping and the agent/session permission filter applied before provider delivery.
- Each of the three captured provider requests carried the exact bounded Reviewer challenge and exposed only `glob`, `grep`, `read`, `skill`, `todowrite`, and `webfetch`. The relay recorded and forwarded the provider requests without altering their tool schemas. No edit or shell-write tool was exposed or invoked. The Reviewer used read-only `glob` and `grep`, and OpenCode blocked a final `grep` targeting the parent directory. That read rejection supplies no write-route denial evidence. No child tasks were created.
- The challenge's exact sentinel bytes and SHA-256 matched before and after. The sentinel SHA-256 was `40da4dd534e5ce2de79bcca1026f66bfecde3d595ebc2beca7952544eae46ef1`. The byte-identical, complete 6,711-entry inventories had SHA-256 `48809d1b4d27129aa977c226c4e5953d41598bb5a71bfa7b6150edc4658fba90`. They include hidden paths, file content hashes, modes, owners, modification times, and symlink targets. Production and disposable Reviewer definitions and project permission configuration were unchanged.

The recovery evidence is under `$TMPDIR/fifth-pick-m10.kMXZVL25/m10-native-withholding-2b089c988436/`, outside the inventoried project. The principal artifacts are `host-tool-catalog.json`, `reviewer-native-filter.json`, `installed-host-filter-excerpts.txt`, `provider-events.jsonl`, `challenge-runtime.jsonl`, `challenge-runtime.log`, `sentinel-before.bin`, `sentinel-after.bin`, `workspace-before.json`, `workspace-after.json`, `permissions-before.json`, `permissions-after.json`, and `integrity-summary.json`. Reproduce the inventory with the saved `capture.py --inventory <canonical-disposable-project>` procedure.

Under the addendum, edit and Bash/shell-write are each **NATIVE TOOL WITHHOLDING VERIFIED**. **REQUEST-TO-DENIAL BEHAVIOR UNVERIFIED** for both. The original Task 7 check `test_reviewer_cannot_edit` maps to Route B evidence for the native edit/write tools. The original check `test_shell_write_bypass_is_denied` maps to Route B evidence for Bash/shell-write. These names describe the original checklist and are not claims that those unit tests ran. Read-oriented tools were exposed, while write-capable tools were withheld. Neither the timed-out challenge nor the out-of-directory read rejection is used as proof.

The recovery capture wrapper did not issue an aggregate PASS. Its location parser included a line break in a directory token, and its zero-tool-call assertion was stricter than the addendum. The evidence audit rechecked the host log directories, actual Reviewer session, native tool filter, all provider requests, and inventory files directly. The recorded read calls do not satisfy a write-denial route and did not modify the workspace.

The independent assessment used a separate actual Fifth Pick Reviewer session under the unchanged native permissions. The first assessment timed out. The recovery assessment, session `ses_e0fb96571ffezEp2c6WrBtz34c`, returned a typed PASS, made no tool calls, and left the complete inventory unchanged. Its original verdict is retained in `assessment-result.json`, with the native output in `assessment-recovery-runtime.jsonl`. One finding mistakenly described the exposed read-oriented tools as blocked. The provider capture supplies the exact distinction: those tools were exposed, while edit, write, and Bash were withheld. M10 acceptance remains withheld for Joseph's decision.

A separate independent audit of the raw artifacts corroborated route B for both write routes and identified the same factual error in the native assessment. It recomputed the inventory and sentinel hashes and matched the production configuration files to the captured permission records.


### M10 Formal Acceptance With Qualification

On 2026-11-18 Joseph explicitly accepted M10 **WITH QUALIFICATION** under the approved OpenCode 1.18.20 evidence addendum. The independent, mechanically read-only Task 7 documentation recheck returned **PASS** after the full-scope review's CONCERNS were reconciled. The original full-scope verdict is retained on line 2311 of the local Codex transcript identified in the final remediation gate entry. The final recheck verdict is on line 2405 of that transcript.

- **NATIVE TOOL WITHHOLDING VERIFIED** for both edit and Bash/shell-write routes on OpenCode 1.18.20. Read-oriented tools were exposed, while write-capable tools were withheld.
- **REQUEST-TO-DENIAL BEHAVIOR UNVERIFIED** for both write routes.
- **Live second-FAIL/CONCERNS escalation UNVERIFIED**, with offline regression coverage.

The final implementation gate run remains the recorded four-gate PASS with 510 unit tests and independent remediation PASS. The isolated correction-path and Route B evidence remain indexed above. Earlier FAIL, CONCERNS, BLOCKED, and unsuccessful runtime records were retained as historical evidence. This decision does not change the frozen architecture, native permissions, or the version-scoped addendum. It does not authorize course closeout work, a commit, or a push.

## M11 offline course closeout — November 18, 2026

The implementation checkpoint is commit `f39cf8296387e7e253ab8229178553ba0b5d636b`.
A clean local clone of that commit had empty porcelain status before and after
verification. Gates used the existing environment with dependency sync and
package networking disabled. Python imported the clone's committed sources.
The implementation commit and the documentation-only closeout evidence are
separate so the gate record can name the exact tested implementation.

| Gate | Result |
| --- | --- |
| `uv run ruff check` | Exit 0 |
| `uv run ruff format --check` | Exit 0, 133 files already formatted |
| `uv run ty check` | Exit 0 |
| `uv run python -m unittest discover -s tests` | Exit 0, 595 tests passed |
| Focused committed-checkout workflow and receipt checks | Exit 0, 4 tests passed |

The fresh fixture workflow is documented in [demo.md](demo.md), with its
[30-receipt audit trail](evidence/course-demo-f39cf82.jsonl). The exact reviewed
fixture proposal preceded the explicit owner decision and synthetic settlement.
The earlier settlement attempt exited 1. The LIVE replay test verified correct
blocking without an additional transport request or new receipt. The independent
review of the staged implementation passed and confirmed that no Evolution or
runtime paths entered the implementation commit.

The initial full M11 checkpoint returned CONCERNS for missing final records,
the current-commit demo evidence, and incomplete gate evidence while the suite
was running. This record, the actual fixture audit, and the updates to
architecture and assurance address those findings. This is offline course
evidence. The independent, mechanically read-only documentation recheck
returned PASS and matched the demo receipt hash to the captured checkout
artifact. No paid pilot was authorized, no provider request was made, and LIVE
analysis is not operational. M10's formal acceptance and qualifications are
unchanged.

## Professor rehearsal checkpoint — November 19, 2026

Baseline `e2d2671`. This checkpoint packages the existing Python CLI and
review harness for classroom reproduction. The production methodology,
native permissions, and milestone acceptance scopes were preserved.

The first gate attempt with uv's default cache returned exit 2 for all
four commands. The workspace sandbox denied access to
`~/.cache/uv/sdists-v9/.git`. Verification switched to a writable uv cache.
A fresh tracked-source export with the course files overlaid installed
successfully with `uv sync --locked --offline` and a warm cache. The
environment used Python 3.14.7 and Node 24.21.0.

From that fresh environment, with provider credentials absent,
`sh scripts/course-demo.sh` exited 0. The invalid slot exited 2 as expected.
Fixture A recorded 8.5, 9.0, and 9.5, produced one `HIGH` / `STILL STRONG`
proposal under a four-pick cap, and wrote 28 receipts. Fixture B recorded
zero observations in slot 3, proposed zero picks, printed
`NO ENTRY RECOMMENDED TODAY.`, and wrote 26 receipts. All four selected
workflow regressions passed. The 14 OpenCode adapter contract tests also
passed, including Node-executed lifecycle hooks.

The independent read-only finalization review initially returned CONCERNS
about the printed receipt directory and the walkthrough's treatment of
fixture and native review states. The corrected files received PASS.
This course review covered the deliverables. It was separate from the
native proposal review state in the demo and the qualified M10 evidence.

The fresh-export rehearsal used the restricted workspace and an empty
inherited environment with only executable path, scratch home, and cache
location set. An attempt to add a second OS-level network sandbox was
rejected by the host. No LIVE validation or provider request was made.

| Final gate | Exit | Result |
| --- | ---: | --- |
| `uv run ruff check` | 0 | All checks passed in the fresh export |
| `uv run ruff format --check` | 0 | 145 files formatted in the fresh export |
| `uv run ty check` | 0 | All checks passed in the fresh export |
| `uv run python -m unittest discover -s tests` | 0 | 629 tests passed in the workspace in 298.063 s |

All gates used `UV_OFFLINE=1` and `UV_NO_SYNC=1` after dependency setup.
`AGENTS.md` had four sections and 3,644 characters. Three pre-existing
untracked `var/test-evidence/` files were excluded from the commit.

## Professor-alignment verification — November 19, 2026

Baseline `0931fb2`. The new `review-handoff` CLI regression initially failed
with exit 2 from the CLI because the command was unavailable. Independent
review then identified a partial-verdict crash path. Before the correction,
the updated test failed because the receipt-free handoff suggested loading
initial review material without confirming that no attempt had occurred.
The corrected handoff verifies identity and digests through the existing
review status path, surfaces interrupted initial verdict writes, and stops
after a consumed correction. The independent re-review returned PASS
within the code, tests, demo wiring, and operator guidance scope.

The final `sh scripts/course-demo.sh` run exited 0 from a fresh source
export with a separately installed locked environment and provider
credentials absent. The positive run produced 28 receipts and a separate
CLI process returned `CONFIRM_INITIAL_REVIEW_NOT_ATTEMPTED` with dispatch
unauthorized. The missing T-20 observation produced zero proposals and
26 receipts. All four selected replay checks passed.

OpenCode 1.18.20 resolved all three project agents and the four project
skills. A scripted loopback model drove real native Planner calls to
`validate-evidence` and Superpowers `verification-before-completion`.
Both completed, and the native request excluded the prohibited tools.
A real local Qwen3 4B run timed out before completing a skill call. The
[native evidence](evidence/professor-native-discovery-2026-11-19.json)
and [harness record](harness.md#professor-alignment-native-checks-and-fresh-session-recovery)
retain the distinct scopes. Route A and M10 qualifications remain in force.

Two extra fresh CLI processes reconstructed the same 484-byte handoff
byte for byte. The receipt ledger SHA-256 stayed identical across both
reads. A missing run returned exit 1 with missing slate metadata.

| Final gate | Exit | Result |
| --- | ---: | --- |
| `uv run ruff check` | 0 | All checks passed |
| `uv run ruff format --check` | 0 | 145 files already formatted |
| `uv run ty check` | 0 | All checks passed |
| `uv run python -m unittest discover -s tests` | 0 | 630 tests passed in 353.796 s |

All four commands ran with uv offline and synchronization disabled after
setup. No LIVE endpoint was requested.
