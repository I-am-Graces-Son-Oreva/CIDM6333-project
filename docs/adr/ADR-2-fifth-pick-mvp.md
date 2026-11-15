# ADR-2: Fifth Pick M1 Foundation and Control Plane

## Status

Accepted for M1. Implementation stops at the approved M1 review checkpoint.

## Context

Fifth Pick needs a trustworthy foundation before any domain implementation. The repository also contains historical Evolution 00–08 material that is not part of the Fifth Pick package and must remain untouched.

## Decision

- Use a Python `src` layout: `src/fifth_pick/`.
- Require Python 3.11 or newer.
- Build with Hatchling and manage the environment with `uv`.
- Keep runtime dependencies empty in M1.
- Use `ruff` and `ty` as development dependencies.
- Use built-in `unittest` for Fifth Pick tests. Do not use pytest.
- Expose the console script `fifth-pick = "fifth_pick.cli:main"`.
- Keep runtime artifacts under gitignored `var/fifth-pick/`.
- Grant only `uv sync`, `uv lock`, `uv run fifth-pick health`, the four gates, and `git status`, `git diff`, and `pwd` to the builder.
- Establish planner, builder, and reviewer roles in M1.
- Deny the reviewer `edit`, `bash`, and `task` capabilities. Reviewer edit denial covers writes and patches.
- Require the reviewer verdict contract `PASS`, `FAIL`, or `CONCERNS`; malformed verdicts fail closed; `CONCERNS` never defaults to `PASS`.
- Preserve Evolution 00–08 exactly.

## Historical Gate Reconciliation

The pre-M1 gate baseline found historical failures in Evolution 00–08 and in the older E4/E6/E7 source and test material. The following narrow exclusions are approved for the Fifth Pick gates:

- `evolution-00/**` through `evolution-08/**`, as nine exact directory patterns.
- `src/e6_context`
- `src/e7_memory`
- `src/grad_mcp`
- `tests/test_e4_mcp.py`
- `tests/test_e6_context.py`
- `tests/test_e7_isolation.py`
- `tests/test_e7_memory.py`

These exclusions are recorded in `pyproject.toml` for Ruff and ty. The Evolution patterns name only existing directories 00 through 08; future Evolution directories are not excluded. The test patterns name only historical files and do not use broad patterns that could exempt future Fifth Pick tests. They do not edit, move, normalize, or repair historical material. They do not add a waiver for any Fifth Pick file.

The required `unittest discover` command still runs against `tests`. Two historical modules import legacy packages at module load time, so M1 restores those packages in a separate `legacy` dependency group:

- `mcp<2`, required by the historical E4 MCP server import.
- `pytest>=9`, required by the historical E7 isolation test import.

`pytest` is not used to run any Fifth Pick test. All Fifth Pick tests are built-in `unittest` tests, and the required gate command remains `uv run python -m unittest discover -s tests`. The legacy group restores import compatibility; it does not authorize pytest as a Fifth Pick test framework.

The final gate commands are unchanged:

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

## Consequences

- Fifth Pick M1 remains small and has no Odds API, registry, authorization, snapshot, methodology, ranking, T-20, finalization, or result logic.
- Historical code remains available and untouched, but it is outside the Fifth Pick quality gate.
- Fifth Pick tests are automatically discovered by the required unittest command; no test module needs manual registration.
- Legacy MCP and pytest packages are compatibility dependencies only. They are not Fifth Pick runtime dependencies and do not change the test framework.
