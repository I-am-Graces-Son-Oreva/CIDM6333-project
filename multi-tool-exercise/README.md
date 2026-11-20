# Multi-tool exercise

CIDM 6333’s **Closeout Walkthrough** builds a Python command-line utility and
the OpenCode harness around it. The harness shows how a skill guides the
model, permissions constrain its tools, and independent review, gates, and
receipts provide evidence of what happened.
[Official walkthrough](https://ahuimanu.github.io/CIDM6333/exercises/closeout-walkthrough.html)

## Run the exercise

From the CIDM 6333 repository root, use Python 3.14 and uv:

```sh
cd multi-tool-exercise
uv sync --locked
uv run mt --version
uv run mt codec base64 encode café
uv run mt units 0 C K
uv run mt hash sha256 hello
uv run mt net 192.0.2.0/30
uv run mt health .
```

The examples print version `0.1.0`, Base64 `Y2Fmw6k=`, `273.15` Kelvin,
the SHA-256 digest of `hello`, and the network and host details for the
example CIDR. The health check verifies project files, runs the four gates,
and reports functions that exceed the exercise’s branch or line limits.
The CLI needs no credentials. Initial dependency setup may need downloads.

Run the gates separately from the same directory:

```sh
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

## Files and evidence

- [Python CLI](src/multitool/) and [33 unittest cases](tests/)
- [Project instructions](AGENTS.md), [permissions and formatter](opencode.json),
  [Reviewer](.opencode/agents/reviewer.md), [Worker](.opencode/agents/worker.md),
  [add-module skill](.opencode/skills/add-module/SKILL.md), and
  [native plugin shim](.opencode/plugins/guard.ts)
- [Python pre-tool guard and after-edit formatter](guard/)
- [Checkpoint summary](docs/closeout-checkpoint.md),
  [walkthrough evidence](docs/closeout-evidence.md), and
  [recorded command output](docs/evidence/command-runs.md)

The original setup and six step commits are retained through the import
parent `8e001bf`. The evidence includes the Reviewer demonstration, a
typed API Worker/Reviewer handoff, and direct guard and formatter receipts.
The original ledger marks the native TUI Worker/Reviewer handoff, a live
protected-test edit blocked by the plugin, and a native after-edit formatter
event as unobserved. Its GitHub status entries describe the time of recording.
[Original standalone repository](https://github.com/I-am-Graces-Son-Oreva/multitool)

For a native OpenCode walkthrough, open the original standalone checkout or
use the following commands from the CIDM 6333 root. This keeps the exercise’s
OpenCode session outside the parent repository’s harness and retains the
original checkpoint history for Git diffs.

```sh
exercise_dir=$(mktemp -d)
git clone --no-hardlinks --no-checkout . "$exercise_dir"
git -C "$exercise_dir" switch --detach 8e001bf
cd "$exercise_dir"
uv sync --locked
opencode
```

Use the official prompts and record the events you observe. Local runtime
receipts stay under the exercise’s ignored `.receipts/` directory.
