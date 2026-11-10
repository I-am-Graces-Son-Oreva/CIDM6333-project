# Evolution 1 Flight Card

## ENVELOPE

Evolution: E1 — The loop is OpenCode's; the agent is yours

System: Graduate Application Identity-Assurance and Triage System

Pilot: Joseph Edafiadhe

Date: 2026-11-09

## DESIGN CLAIM

The primary OpenCode agent can answer a bounded question and stop before its configured step limit, while a task that requires more tool activity than the configured limit will halt at that limit and return text instead of continuing tool calls.

## SYSTEMS UNDER TEST

- OpenCode primary agent
- Agent step limit
- OpenCode agent loop
- Graduate Application Identity-Assurance and Triage System instructions

## SUBSTRATE

Repository: CIDM6333-project

Pre-flight commit: e873524

OpenCode version: 1.18.20

Agent: .opencode/agents/grad-triage.md

Model: opencode/big-pickle

Configured step limit: 5

## TEST POINTS

### TP1 — Bounded question

Prompt the E1 primary agent with one bounded question.

Expected observation:
The agent answers the question and stops in fewer than 5 steps.

Evidence:
A sanitized OpenCode session export showing the bounded answer and step/tool activity.

### TP2 — Open-ended task

Give the agent a task deliberately requiring more tool activity than its configured 5-step limit.

Expected observation:
The agent reaches the configured step limit, stops making tool calls, and returns a text response describing the incomplete state.

Evidence:
A sanitized OpenCode session export showing the halt at the step limit and the final text response.

## INSTRUMENTATION

- OpenCode session behavior
- Sanitized exports produced with `opencode export <sessionID> --sanitize`
- Tool-call/step sequence visible in the sanitized evidence
- Flight log mapping TP1 and TP2 to their evidence

## PRE-REGISTERED FALSIFIERS

1. TP1 requires 5 or more steps or fails to produce the bounded answer.
2. TP2 continues making tool calls beyond the configured 5-step limit or does not terminate with text.
3. The configured agent used in the sortie does not contain `steps: 5`.
4. The sortie passes only because a permission was loosened, a tool was removed, or an export was edited.

## ABORT

ABORT if the configured model is unavailable, OpenCode cannot load the primary agent, or the model cannot perform the behavior required to exercise the test points. Record the exact error and model id rather than changing the evidence.

## CHASE GO / NO-GO

GO — Chase — 2026-11-09
