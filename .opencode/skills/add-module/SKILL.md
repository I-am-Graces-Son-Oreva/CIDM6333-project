---
name: add-module
description: "Use when adding a new subcommand module to multitool: tests first, module, CLI wiring, four gates."
---

## Procedure

1. Write `tests/test_<name>.py` first and run it; it must fail.
2. Write `src/multitool/<name>.py`.
3. Wire `mt <name>` in the CLI.
4. Run the four gates from AGENTS.md and report each exit code.
5. Never change an existing test; if one blocks you, stop and say which.
