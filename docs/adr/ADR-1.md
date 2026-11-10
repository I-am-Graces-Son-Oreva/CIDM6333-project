# ADR-1 — Orchestration Pattern for Graduate Application Triage

**Status:** Accepted  
**Date:** 2026-11-09

## Context

The Graduate Application Identity-Assurance and Triage System needs more than one kind of work. Evidence must first be reviewed to separate verified facts from uncertainty, and then that reviewed information must be summarized for human triage.

Evolution 2 requires an explicit workflow pattern and a decision about who owns the loop.

## Decision

Use OpenCode's orchestrator-workers pattern.

The `grad-triage` primary agent owns the workflow and delegates specialized work in this order:

1. `evidence-reviewer`
2. `triage-summarizer`

The primary agent is restricted through `permission.task` so it may delegate only to these named subagents.

## Alternative 1 — LangGraph

LangGraph could represent the workflow as an explicit graph with nodes and edges.

### Consequences

- Strong explicit workflow and state representation.
- Useful for larger branching or durable workflows.
- Adds another framework and additional implementation complexity.
- More infrastructure than this two-worker course sortie requires.

## Alternative 2 — Pydantic AI

Pydantic AI could provide typed agents, structured outputs, dependencies, and tool integration.

### Consequences

- Strong Python typing and structured validation.
- Useful when application code depends heavily on typed model outputs.
- Introduces another agent framework and Python integration layer.
- Does not provide an advantage large enough to justify replacing the OpenCode harness used throughout this assignment.

## Scorecard

Scores use 1 = weak and 5 = strong.

| Criterion | OpenCode Agents | LangGraph | Pydantic AI |
|---|---:|---:|---:|
| Fits current course harness | 5 | 3 | 3 |
| Simple two-worker orchestration | 5 | 4 | 4 |
| Permission control for this sortie | 5 | 4 | 4 |
| Low additional complexity | 5 | 2 | 3 |
| Explicit complex workflow support | 3 | 5 | 4 |
| Structured Python integration | 3 | 4 | 5 |
| **Total** | **26** | **22** | **23** |

## Consequences of the Decision

The primary agent owns the loop while specialized subagents own narrow tasks. This makes worker order visible and gives the harness a clear place to enforce delegation permissions.

The cost is that orchestration behavior still depends on the primary model following the defined workflow. Therefore the sortie must inspect the session export rather than assuming delegation occurred.

## Failure Modes

1. The primary skips a required worker.
2. The primary calls the workers in the wrong order.
3. The primary performs all work itself instead of delegating.
4. A worker outside the allowed `permission.task` list can be called.

## Preservation Mechanism

Keep worker roles narrow, state the required order in the primary agent instructions, restrict delegation with `permission.task`, and verify actual task calls from sanitized OpenCode exports.
