Multitool is a local Python command-line toolkit; it must never edit tests/ to make a gate pass.

# Run and test
- Run `uv run mt --version` to check the installed CLI.
- Done means all four gates pass, in order:
  - `uv run ruff check`
  - `uv run ruff format --check`
  - `uv run ty check`
  - `uv run python -m unittest discover -s tests`

# Conventions that differ from defaults
- Require Python 3.14 or newer; keep package code under `src/`.
- Use only standard-library `unittest`; do not add pytest.
- Use argparse for CLI parsing and exit 2 for invalid command input.
- New modules: use the add-module skill.

# Rules that must hold (enforced)
- Never edit files under tests/ to make a gate pass. Enforced by: opencode.json, edit on tests/ asks.

# Where the truth lives
- Toolchain and lint configuration: `pyproject.toml`; resolved versions: `uv.lock`.
- CLI behavior: `src/multitool/`; expected behavior: `tests/`.
- Closeout progress and observed results: `docs/closeout-checkpoint.md` and `docs/closeout-evidence.md`.
