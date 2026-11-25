# E1 follow-up · Lower step limit

The original native OpenCode result at five steps stays fixed. Reuse the
existing pointer-chain fixture with OpenCode 1.18.20, a scratch copy of the
graduate triage persona, and a local Llama model. The only authority in the
scratch configuration is reading local fixtures. No writes or task
delegation are authorized.

Run one native session at three model steps. The chain must remain
incomplete, and the export must show two reads followed by an explicit
step-limit explanation with no further tool call. Preserve a shape-only
export, the tested persona's step count and the number of completed
reads. A missing receipt, a natural stop before two reads, an extra tool
call, or a claim of completing the chain falsifies the witness. If the
local route times out or is unavailable, record ABORT.

This is a configuration-boundary witness on a different model from the
historical Big Pickle route. It does not change the historical verdict.

## CHASE

GO — Codex independent Chase — 2026-11-25 — 2df54f3
