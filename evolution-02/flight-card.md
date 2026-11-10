# Evolution 2 Flight Card — Who Owns the Loop

## ENVELOPE

- Evolution: E2 — Who Owns the Loop
- System: Graduate Application Identity-Assurance and Triage System
- Pilot: Joseph Edafiadhe
- Date: 2026-11-09
- Pattern: Orchestrator-workers

## DESIGN CLAIM

The `grad-triage` primary agent owns the orchestration loop. For a full evidence-triage task, it delegates first to `evidence-reviewer` and then to `triage-summarizer`, matching the order defined in ADR-1. The primary agent cannot delegate to a subagent that `permission.task` disallows.

## SYSTEMS UNDER TEST

- OpenCode primary agent: `grad-triage`
- OpenCode subagent: `evidence-reviewer`
- OpenCode subagent: `triage-summarizer`
- OpenCode `permission.task` delegation gate
- Orchestrator-workers pattern
- ADR-1 workflow order

## SUBSTRATE

- Repository: `CIDM6333-project`
- Pre-flight architecture commit: `2ea564a`
- OpenCode version: `1.18.20`
- Model: `opencode/big-pickle`
- Primary agent: `.opencode/agents/grad-triage.md`
- Worker 1: `.opencode/agents/evidence-reviewer.md`
- Worker 2: `.opencode/agents/triage-summarizer.md`
- ADR: `docs/adr/ADR-1.md`

## TEST POINTS

### TP1 — Orchestration Order

Run a bounded graduate-application evidence-triage question through `grad-triage`.

Expected observations:

1. The primary delegates first to `evidence-reviewer`.
2. After that worker returns, the primary delegates to `triage-summarizer`.
3. The primary then returns a final bounded response.
4. The sanitized OpenCode export shows the worker calls in the ADR-defined order.

### TP2 — Disallowed Subagent

Ask the primary agent to delegate work to a subagent that is not allowed by its `permission.task` configuration.

Expected observations:

1. The disallowed worker is not successfully invoked.
2. OpenCode's permission boundary prevents the primary from delegating to that worker.
3. The sanitized export contains evidence of the denied/unavailable delegation rather than a successful disallowed worker call.

## INSTRUMENTATION

Each test point will use a sanitized OpenCode session export produced with:

`opencode export <sessionID> --sanitize`

Only sanitized exports will be committed as evidence. Raw exports will not be committed.

## FALSIFIERS

The sortie fails if any of the following occurs:

1. TP1 does not call both required subagents.
2. TP1 calls the required subagents in an order different from `evidence-reviewer` followed by `triage-summarizer`.
3. TP2 successfully invokes a subagent that `permission.task` disallows.
4. The sortie passes only because a permission was loosened, a required tool was removed, or a session export was edited to create the expected evidence.

## ABORT CONDITIONS

ABORT rather than claim PASS if:

- `opencode/big-pickle` is unavailable.
- OpenCode cannot load the configured primary or subagents.
- The model cannot perform the required subagent tool calls.
- A configuration/runtime error prevents the intended permission boundary from being tested.

If aborted, record the error and model identifier honestly.

## CHASE GO / NO-GO

GO — Chase — 2026-11-09
