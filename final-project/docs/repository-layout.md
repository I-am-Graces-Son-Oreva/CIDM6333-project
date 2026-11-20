# Repository organization

Before the move, Fifth Pick implementation, tests, policy, and course material
shared the root `src/`, `tests/`, `config/`, `docs/`, and `scripts/` trees with
coursework or appeared beside the root README.

| Pre-move location | Ownership and disposition |
| --- | --- |
| `src/fifth_pick/` | Fifth Pick CLI and bundled synthetic examples moved under `final-project/src/`. |
| `tests/` product tests, support, and fixtures | Moved under `final-project/tests/`. The root unittest gate still loads them by module name. |
| `config/fifth-pick/` | Frozen universe, source rules, slate fixture, and methodology moved together under `final-project/config/`. |
| Fifth Pick PRD, ADR-2, project update, guides, plans, design, and evidence | Moved into `final-project/docs/`. ADR-1 documents the separate triage coursework. |
| `scripts/course-demo.sh`, `scripts/course_demo.py` | Moved to `final-project/scripts/`. The wrapper selects the repository root before running uv. |
| `.opencode/`, `opencode.json`, `AGENTS.md` | Shared native discovery, permissions, and commands remain at the root. |
| `pyproject.toml`, `uv.lock`, root `tests/` | Shared environment, console entry point, and combined test gate remain at the root. |
| Evolution 00–08, design analyses, AI log, and legacy modules/tests | Historical coursework stays at its original paths. |
| Multi-tool exercise | No separate tracked, untracked, or historical submission was identified. |
| `var/fifth-pick/` and `var/test-evidence/` | Local runtime and preflight records stay in place and are ignored. |

The [root index](../../README.md) links to each assignment and to the [final
project](../README.md). The copied configuration and application rules retain
their original contents. The storage module adjusts its directory traversal
to keep existing receipts under the same repository-root path.

Historical gate captures, executed plans, and frozen design records preserve
the paths recorded at their original commits. Current operator commands use
the paths shown in the [demo guide](fifth-pick/demo.md).

## Verification

The first run found test import resolution and formatting failures after the
move. Ruff now includes the relocated source and test roots, and ty resolves
the relocated test package. Existing tests retain their assertions.

A fresh source export installed with `uv sync --locked --offline` using
cached dependencies. The relocated course script exited 0 and exercised the
positive and zero-pick scenarios. Both independent handoff reads matched
byte for byte, the receipt digest was unchanged, and an unknown run exited 1.
OpenCode 1.18.20 discovered all three Fifth Pick agents and four skills.
Its adapter activated and its Planner and Reviewer still withheld write,
edit, Bash, and task dispatch tools. The unrelated legacy MCP was disabled
for that isolated discovery check. Evolution 08's separate suite passed
44 tests. No standalone Multi-tool suite could be identified.

The frozen policy files, existing evidence, and decision implementation
were compared byte for byte. Only the storage module needed a source-path
adjustment to preserve the root receipts directory.

| Root quality gate | Exit | Result |
| --- | ---: | --- |
| `uv run ruff check` | 0 | All checks passed |
| `uv run ruff format --check` | 0 | 148 files already formatted |
| `uv run ty check` | 0 | All checks passed |
| `uv run python -m unittest discover -s tests` | 0 | 630 tests passed, matching the baseline |

All four gates ran from the fresh export. The independent read-only
reorganization review passed after corrections to active documentation
paths and the Evolution 6 link. No LIVE requests or publication occurred.
