# Design Analysis — Multi-Agent Control Boundaries vs. Prompt-Only Coordination

## Question

How should Evolution 8 separate implementation, independent review, and final
human approval?

## Option 1 — Prompt-Only Coordination

One agent could implement the task and then be prompted to review its own work,
or a second agent could simply be told not to edit.

This is simple, but the control boundary depends heavily on model obedience.
The same workflow can also blur the distinction between doing work, judging
work, and authorizing the final action.

## Option 2 — Explicit Multi-Agent State Machine

Use separate implementer and reviewer personas, structured handoff contracts,
fail-closed parsing, conditional routing, checkpoints, and a human interrupt
before merge.

The implementer produces a HandoffResult. The reviewer independently produces
a ReviewResult. Review FAIL routes back to implementation. Review PASS stops at
human approval. Merge is unavailable until the human explicitly approves it.

## Evidence From Evolution 8

TP1 demonstrated the clean path through implementation, review, human approval,
and one merge.

TP2 demonstrated that a reviewer FAIL routes back to implementation without
merge.

TP3 demonstrated that malformed or unsupported structured results are rejected
rather than defaulting to DONE or PASS.

TP4 demonstrated an important harness/runtime limitation. The reviewer remained
unable to modify the sealed fixture, but the local OpenCode permission behavior
did not produce the exact live denied edit/write event required by the test.
The harness failed closed and no TP4 PASS is claimed.

TP5 demonstrated durable workflow control: execution stopped at the human
interrupt with `merge_count` equal to 0, then resumed from the saved review
checkpoint after explicit approval and completed with exactly one merge.

## Judgment

Use explicit multi-agent control boundaries rather than prompt-only
coordination when agents have different responsibilities or authority.

The important property is not that agents merely describe their roles. The
harness must constrain which transitions and actions are possible, reject
malformed outputs, preserve checkpoints, and keep the human as the final
authority before consequential actions such as merge.
