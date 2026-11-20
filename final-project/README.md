# The Fifth Pick

The Fifth Pick is a Python CLI for disciplined NBA fantasy-prop selection
and the final project for WTAMU CIDM 6333 Agentic Systems. Python validates
inputs, processes source records, evaluates evidence, enforces selection
rules, and writes receipts. Joseph defines authorization and makes the
final decision. The application has no entry submission or wagering path.

## Start here

- [User guide](docs/fifth-pick/user-guide.html)
- [Technical and design documentation](docs/fifth-pick/technical-design.html)
- [Tuesday presentation walkthrough](docs/fifth-pick/presentation.md)
- [Beginner learning notes](docs/fifth-pick/learning-notes.md)
- [Course demonstration and verification](docs/fifth-pick/demo.md)

From the repository root with Python 3.11 or later and uv, install the locked
environment once. Initial setup may need package downloads. All subsequent
demo execution uses local files and requires no provider credentials.

```sh
uv sync --locked
sh final-project/scripts/course-demo.sh
uv run --offline --no-sync fifth-pick menu
```

The script replays checked-in synthetic provider responses. It prints rejected
inputs, three simulated timestamps, a one-pick proposal, an empty proposal
with a missing third observation, and audit commands for both runs. The
regression replay exercises review receipt binding, explicit approval before
simulated settlement, both selection ceilings, and no refill. The menu defaults
to Demo Mode and allows interactive inspection and decisions. Runtime outputs
stay in the ignored `var/fifth-pick/` directory.

## Methodology

The frozen 156-player universe and Joseph's exact player/category/direction
grants govern selection. PrizePicks and Underdog remain separate across
points, rebounds, assists, points+rebounds+assists, and rebounds+assists.
The workflow preserves three timestamped observations and separate T-20
verification. It freezes the ranked pool, uses at most one slot per player,
and caps a 1–4 game slate at four selections and a 5+ game slate at five.
A missed observation or insufficient evidence can remove a candidate.
Removed candidates are never replaced to fill slots. A valid run can end
with `NO ENTRY RECOMMENDED TODAY.`

## Architecture and agent context

[AGENTS.md](../AGENTS.md) carries repository-wide rules and points to the
durable operating guidance. [Project skills](../.opencode/skills) contain
task-specific procedures for evidence, candidate evaluation, and slate
and T-20 review. [Native agent definitions](../.opencode/agents) define roles
and permissions. The Python Controller owns review state. The Planner
scopes the task, the Builder prepares the artifact within that scope, and
the independent Reviewer examines the exact artifact with write tools
withheld under the recorded OpenCode configuration.

Agents receive task-scoped material and evidence references. The native
review adapter correlates a bounded review envelope to a specific task
and passes the verdict to Python. Persistent config, receipts, digests,
and checked-in gates support reconstruction in a fresh session. Summaries
are navigation aids. The workflow depends on explicit handoffs and Python
validation to control drift as the conversation grows. On restart, use the
run ID with `fifth-pick review-handoff --run-id RUN_ID` to reconstruct a
bounded checkpoint. Compare both digests before loading evidence for the
next stage. The checkpoint grants no Builder dispatch authority. Stop when required inputs
are missing or the bounded handoff cannot be validated.

Superpowers guided design, implementation planning, review, and verification
during development. Those plans and findings are checked into the repository.
The CLI and its synthetic replay run independently of Superpowers. Native
OpenCode discovery and fixture-driven skill calls were exercised separately.
See the
[architecture](docs/fifth-pick/architecture.md),
[OpenCode harness record](docs/fifth-pick/harness.md), and
[development plans](docs/superpowers/plans).

## Sources and LIVE limits

The Odds API `us_dfs` route supplies platform lines. A line or optional
multiplier alone supplies no calibrated hit probability. Historical
performance, availability, and Joseph's frozen policy each have separate
provenance and authority. BALLDONTLIE Teams and Players returned HTTP 200 in
Joseph's scoped checks. The Stats request returned HTTP 401. Support was
contacted and the history gap remains open. Paid Odds API requests require
Joseph's explicit budget. See the [source verification record](docs/fifth-pick/source-verification.md)
and [LIVE runbook](docs/fifth-pick/runbook.md).

The offline demonstration exercises production validation and decision logic
with synthetic inputs. Full LIVE coverage, supporting evidence, and a completed
real-time release remain unverified. M10 is accepted with qualification on
OpenCode 1.18.20. Native write-tool withholding was verified for both routes.
Correlated request-to-denial evidence remains blocked, and native second-FAIL
and CONCERNS escalation remain unverified with offline regression coverage.
Use Route A only. See the [gate record](docs/fifth-pick/gates.md).

## Repository layout

| Location | Purpose |
| --- | --- |
| [src/fifth_pick](src/fifth_pick/) | Python CLI package |
| [Bundled examples](src/fifth_pick/demo/) | Three synthetic observations and [example audit output](docs/fifth-pick/evidence/course-demo-f39cf82.jsonl) |
| [tests](tests/) | Fifth Pick tests and source fixtures |
| [config/fifth-pick](config/fifth-pick/) | Frozen universe, source policy, methodology, and governance |
| [docs](docs/) | Design, guides, presentation, and preserved evidence |
| [Repository organization](docs/repository-layout.md) | Move inventory and root dependencies |
| [scripts](scripts/) | Offline course rehearsal |
| [Root OpenCode files](../.opencode/) | Native agents, commands, skills, and plugins discovered from the repository root |

Run commands from the [repository root](../README.md). The root
`pyproject.toml` and `uv.lock` maintain a single environment for the
project and coursework. The root `tests/` discovery shim includes the
relocated project tests in the original unittest gate. OpenCode uses
root `opencode.json`, `.opencode/`, and `AGENTS.md` for project discovery,
permissions, and root-relative commands. Existing runtime receipts remain
under ignored `var/fifth-pick/`.

### Native agents and skills

- [Planner](../.opencode/agents/fifth-pick-planner.md), [Builder](../.opencode/agents/fifth-pick-builder.md), and [Reviewer](../.opencode/agents/fifth-pick-reviewer.md)
- [Candidate evaluation](../.opencode/skills/evaluate-candidate/SKILL.md), [evidence validation](../.opencode/skills/validate-evidence/SKILL.md), [final slate](../.opencode/skills/final-slate-review/SKILL.md), and [T-20 review](../.opencode/skills/t20-review/SKILL.md)
- [Review adapter](../.opencode/plugin/fifth-pick-review-adapter.ts) and [harness evidence](docs/fifth-pick/harness.md)
