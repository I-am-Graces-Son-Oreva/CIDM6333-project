# FINAL PROJECT — THE FIFTH PICK

**WTAMU CIDM 6333 · Joseph Edafiadhe**

The Fifth Pick is a Python CLI for disciplined NBA fantasy-prop selection.
It validates evidence, applies the frozen selection rules, and leaves the
final decision to Joseph. The classroom rehearsal uses synthetic data.

- [Final project README](final-project/README.md)
- Technical design · [PDF](final-project/docs/fifth-pick/technical-design.pdf) · [HTML](final-project/docs/fifth-pick/technical-design.html)
- User guide · [PDF](final-project/docs/fifth-pick/user-guide.pdf) · [HTML](final-project/docs/fifth-pick/user-guide.html)
- [Offline demonstration](final-project/docs/fifth-pick/demo.md)
- [Presentation walkthrough](final-project/docs/fifth-pick/presentation.md)

The PDFs open directly from the GitHub repository once this commit is published.
Reading them requires only access to the repository.

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

## Multi-tool exercise

No standalone Multi-tool submission was identified among the repository files
or Git history available for this checkout. The Evolution assignments and their
tool exercises remain under their original coursework.

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
