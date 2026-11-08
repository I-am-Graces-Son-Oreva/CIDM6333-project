# CIDM 6333 — Agentic Systems

This repository contains my CIDM 6333 Agentic Systems work.

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
