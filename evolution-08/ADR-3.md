# ADR-3 — Controlled Plan–Do–Check Multi-Agent Workflow

**Status:** Accepted for Evolution 8 preflight  
**Date:** 2026-11-11

## Context

Evolution 8 requires a multi-agent workflow in which implementation, independent review, and human approval are separate control boundaries.

A simple prompt such as "implement this and check your work" is not sufficient because the same agent could perform the work, judge itself, and continue without an independent control point.

The system therefore needs explicit roles, structured handoff contracts, conditional routing, checkpoints, and a human interrupt before merge.

## Decision

Evolution 8 will use a small Python state machine implementing this path:

`implement -> review -> human_approval -> merge`

If review returns FAIL:

`review -> implement`

The workflow cannot merge directly from implementation or review.

## Roles

### Implementer

The OpenCode `e8-implementer` persona performs the bounded implementation task and produces a structured `HandoffResult`.

The implementer may change implementation files but cannot approve its own work.

### Reviewer

The OpenCode `e8-reviewer` persona independently evaluates the implementation and produces a structured `ReviewResult`.

The reviewer is configured with:

`edit: deny`

This makes the review boundary a configuration-level restriction rather than only a prompt instruction.

The reviewer can issue PASS or FAIL but cannot merge.

### Human

The human is the final approval boundary.

A reviewer PASS causes the workflow to stop at `human_approval`. Merge remains unavailable until explicit human approval is recorded.

## Contract

Two structured contracts are used.

### HandoffResult

Fields:

- `status`: DONE or BLOCKED
- `summary`: non-empty string
- `evidence`: list of evidence strings

DONE without evidence is rejected.

### ReviewResult

Fields:

- `status`: PASS or FAIL
- `summary`: non-empty string
- `findings`: list of findings

FAIL without a finding is rejected.

The parsers fail closed. Prose, malformed JSON, unknown statuses, missing fields, and unknown fields are rejected. No malformed output defaults to DONE or PASS.

## Graph and Checkpoints

The state machine contains named control nodes:

1. `implement`
2. `review`
3. `human_approval`
4. `merge`

A checkpoint is recorded after each completed node.

Review PASS routes to the human interrupt.

Review FAIL routes back to implementation.

Human rejection stops the workflow without merge.

Human approval permits exactly one merge.

## Alternatives Considered

### Alternative 1 — Single Agent With Self-Review

One agent could implement a task and then inspect its own work.

Rejected because implementation and review would share the same authority and context. A self-review prompt does not create an independent control boundary.

### Alternative 2 — Prompt-Only Reviewer Restriction

A separate reviewer could be told, "Do not edit files."

Rejected because the restriction would depend only on model obedience. Evolution 8 requires the reviewer boundary to be enforced by configuration, so the reviewer uses `edit: deny`.

### Alternative 3 — LangGraph

LangGraph could provide graph routing and checkpoint infrastructure.

Not selected for this Evolution because the required control flow is small and can be represented explicitly with a plain Python state machine. The smaller implementation makes the routing, interrupt, and merge conditions easier to inspect and test.

## Consequences

Benefits:

- implementation and review authority are separated;
- malformed agent output fails closed;
- reviewer FAIL cannot reach merge;
- reviewer PASS still requires human approval;
- merge is limited to exactly one execution;
- routing behavior can be tested without relying on model claims.

Tradeoffs:

- checkpointing is currently represented by explicit workflow state rather than an external durable graph framework;
- the committed E8 driver composes the OpenCode persona runner with the workflow for the official sortie; persona outputs remain subject to fail-closed parsing before they can advance the workflow;
- human approval must be explicitly recorded before merge.

## Verification

Automated E8 tests currently verify:

- structured handoff and review parsing;
- rejection of prose and unknown statuses;
- rejection of DONE without evidence;
- PASS stopping at the human interrupt;
- FAIL routing back to implementation;
- human rejection preventing merge;
- merge requiring human approval;
- exactly one merge.

These automated tests support preflight readiness but do not substitute for the official Evolution 8 sortie evidence.
