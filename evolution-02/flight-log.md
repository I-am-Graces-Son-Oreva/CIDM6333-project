# Evolution 2 Flight Log — Who Owns the Loop

- Pilot: Joseph Edafiadhe
- Date: 2026-11-09
- Pattern: Orchestrator-workers
- Model: `opencode/big-pickle`
- OpenCode: `1.18.20`
- Chase GO: `GO — Chase — 2026-11-09`
- Pre-flight GO commit: `9943554`

## TP1 — Orchestration Order

### Session

`ses_e3d15166bffekKIKs1DGprBPme`

### Evidence

`evolution-02/evidence/tp1-sanitized.json`

### Observation

The live OpenCode run showed the primary `grad-triage` agent delegating first to the Evidence-Reviewer Agent and, after that worker completed, delegating to the Triage-Summarizer Agent. The primary then returned the bounded human-review summary.

The sanitized export is valid JSON and records:

1. the user message to `grad-triage`;
2. a first assistant turn ending with `tool-calls` and one completed `task` call;
3. a second assistant turn ending with `tool-calls` and one completed `task` call;
4. a final `grad-triage` assistant turn ending with `stop`.

The `--sanitize` export redacts each task call's input, output, metadata, and title. Therefore, the sanitized JSON preserves the existence, sequence, and successful completion of the two task calls, but it does not independently expose the worker names.

The committed primary-agent configuration allows only `evidence-reviewer` and `triage-summarizer`, and its orchestration instructions specify that order.

### TP1 Verdict

PASS, with sanitization limitation recorded above.

The observed live run followed the ADR-defined order, and the required sanitized export preserves two sequential completed task calls followed by the primary's final stop.

## TP2 — Disallowed Subagent

### Session

`ses_e3d10cf63ffeeZKfy9r94EwrVV`

### Evidence

`evolution-02/evidence/tp2-sanitized.json`

### Observation

The primary attempted a `task` delegation to the `general` subagent. OpenCode rejected the tool call before the subagent executed.

The sanitized export preserves the failed task call and the permission error. The error records these relevant rules:

- `task` pattern `*` → deny
- `task` pattern `evidence-reviewer` → allow
- `task` pattern `triage-summarizer` → allow

The assistant then stopped and reported the failed delegation. The prohibited worker did not successfully execute.

Before TP2, `opencode agent list` showed `general` as an available subagent, so the test targeted a real subagent rather than a fabricated name.

### TP2 Verdict

PASS.

The `permission.task` boundary prevented the primary agent from successfully delegating to a disallowed subagent.

## Falsifier Check

1. TP1 did call two workers sequentially; no missing worker call was observed.
2. The live TP1 run showed Evidence-Reviewer before Triage-Summarizer, matching ADR-1.
3. TP2 did not successfully invoke the disallowed `general` subagent.
4. No permission was loosened, required tool removed, or sanitized export edited to manufacture the expected result.

## SORTIE VERDICT

PASS — pending independent Chase post-flight review of the committed evidence.
