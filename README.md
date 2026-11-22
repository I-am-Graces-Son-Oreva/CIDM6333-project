# FINAL PROJECT — THE FIFTH PICK

**WTAMU CIDM 6333 · Joseph Edafiadhe**

The Fifth Pick is a Python CLI for disciplined NBA fantasy-prop selection.
It validates evidence, applies the frozen selection rules, and leaves the
final decision to Joseph. The classroom rehearsal uses a synthetic four-game slate with 12 players.

- [Final project README](final-project/README.md)
- Technical design · [PDF](final-project/docs/fifth-pick/technical-design.pdf) · [HTML](final-project/docs/fifth-pick/technical-design.html)
- Evidence and ranking code · [Snapshots](final-project/src/fifth_pick/snapshots.py) · [Methodology](final-project/src/fifth_pick/methodology.py) · [Ranking](final-project/src/fifth_pick/ranking.py)
- User guide · [PDF](final-project/docs/fifth-pick/user-guide.pdf) · [HTML](final-project/docs/fifth-pick/user-guide.html) · [Public website](https://the-fifth-pick-docs.reedyolive6.chatgpt.site/user-guide)
- Get the code from the [class repository](https://github.com/WTAMU-CIDM6333/CIDM6333-Fall2026-Joseph-Edafiadhe).
- [Offline demonstration](final-project/docs/fifth-pick/demo.md)

The PDFs are readable in GitHub. If a link in the PDF preview does not open,
use the direct links above or download the PDF and open it in a PDF reader.

From the repository root, start the interactive CLI in Demo Mode:

```sh
uv sync --locked
uv run --offline --no-sync fifth-pick menu
```

Run the professor’s scripted offline demonstration after setup:

```sh
sh final-project/scripts/course-demo.sh
```

Dependency setup may require downloads. The rehearsal uses bundled synthetic
fixtures and requires no provider credentials. Live NBA integration is only
partially verified.

## Multi-tool exercise

The CIDM 6333 Closeout Walkthrough builds a Python CLI with codecs, unit
conversion, hashing, CIDR inspection, and project health checks. Its OpenCode
harness uses permissions, a skill, Reviewer and Worker roles, and Python
guards. Start with the [Multi-tool exercise README](multi-tool-exercise/README.md)
or inspect the [original walkthrough evidence](multi-tool-exercise/docs/closeout-evidence.md).

## Evolution assignments

| Assignment | Deliverables |
| --- | --- |
| [Evolution 00](evolution-00/) | Pitch, design, and toolkit |
| [Evolution 01](evolution-01/) | Flight card and execution evidence |
| [Evolution 02](evolution-02/) | Agent delegation and flight records |
| [Evolution 03](evolution-03/) | Instructions and boundary evaluation |
| [Evolution 04](evolution-04/) | MCP and GitHub tool work |
| [Evolution 05](evolution-05/) | MCP security lab |
| [Evolution 06](evolution-06/) | Persistent context and evidence |
| [Evolution 07](evolution-07/) | Memory and isolation |
| [Evolution 08](evolution-08/) | Multi-agent control and review |

See the [design-analysis ledger](design-analyses/LEDGER.md) and [AI interaction log](AI_LOG.md).

## Shared tool configuration

The root [Python project](pyproject.toml) and [lockfile](uv.lock) serve the
final project and coursework. [OpenCode configuration](opencode.json),
[native definitions](.opencode/), and [repository instructions](AGENTS.md)
live at the root so OpenCode discovers the agents, skills, and plugins from
the same directory used for course commands.
## Evolution 6 — Layers of Truth

Evolution 6 separates persistent context into three layers.

### L1 — Canon

Stable instructions and decisions that should survive across sessions.

Primary paths:

- `AGENTS.md`
- `evolution-06/flight-card.md`
- `evolution-06/handoff.md`

### L2 — Runtime Ledger

Append-only evidence of what actually happened during execution.

Primary path:

- `evolution-06/runtime-ledger.jsonl`

### L3 — Derived Views

Summaries, status views, compacted representations, and other information
derived from stronger sources.

Examples:

- `evolution-06/evidence/compacted-context.txt`
- `evolution-06/evidence/stale-status.md`

### Precedence

When layers disagree:

`L2 ledger > L1 canon > L3 derived views`

A stale L3 view cannot override the runtime ledger or block work.

Evolution 6 deliberately plants a stale L3 status file and verifies that a
fresh session follows L2 instead.
