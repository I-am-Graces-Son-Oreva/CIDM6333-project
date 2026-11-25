# CIDM 6333 Evolution reassessment

This index links observed repairs to the instructor's feedback. The
original feedback remains on the class repository. A Chase verdict has
the scope of its flight card. The instructor determines rubric levels.

| Work | Feedback addressed | Evidence or open item |
| --- | --- | --- |
| E0 | Align the historical tool choices and pitch | [Dated choices supplement](../evolution-00/choices.md#reassessment-note--november-25-2026) and [analysis references](../evolution-00/design-analysis.md#reassessment-references). |
| E1 | Demonstrate a second, lower configured step limit | [Native three-step retry](../evolution-01/reassessment/flight-card.md#attempt-2-result) recorded three steps and two completed reads versus five steps and four reads in the original export. The independent witness verdict was FAIL because the explicit halt explanation was absent. |
| E2 | Establish worker order from safe evidence | [Recovered event timestamps and child session links](../evolution-02/flight-log.md#reassessment--recovered-worker-order). |
| E3 and AGENTS.md lab | Close the historical Chase and measurement trail | The original recorded tool denial remains usable. [Lab commit recovery](../evolution-03/lab/reassessment-ledger.jsonl). [Recovered exact counters](../evolution-03/lab/agents-md-measurement.md#recovered-exact-counters) show differences of 190 and 174 tokens across two same-prompt candidate pairs. The original record does not identify which pair it used. A [new independent Chase review](../evolution-03/lab/agents-md-measurement.md#independent-reassessment-verdict) passed the archival probe checks. |
| E4 | Capture the existing tests | [Two passing tests](../evolution-04/evidence/reassessment/pytest.txt). These do not authenticate a caller-provided client label. A trustworthy deployment would bind identity to a verified credential or session rather than the caller's text. |
| E5 | Pin tool descriptions and externalize the exercise signing key | [Clean and mutated declaration checks](../evolution-05/flight-log.md#reassessment--tool-description-integrity). [GitHub MCP design analysis](../design-analyses/E5-GitHub-MCP.md). [Native MCP SDK 2.0 witness](../evolution-05/reassessment-flight-card.md#native-evidence) passed under a dedicated environment. The model-driven OpenCode path remains separate. |
| E6 | Analyze native thresholds and test continuation | [Source analysis](../design-analyses/E6-OpenCode-Context.md) and [alternate flight](../evolution-06/reassessment/flight-card.md). The [retry](../evolution-06/reassessment/evidence/attempt-2/run.jsonl) verified forced project-managed compaction. The [native automatic witness](../evolution-06/native-reassessment/flight-card.md#postflight) also passed with scripted above-threshold usage. |
| E7 | Compare recall ON, OFF, absent and eviction | [Actual alternate-model answers](../evolution-06/reassessment/evidence/attempt-1/run.jsonl), [recall ledger](../evolution-06/reassessment/evidence/attempt-1/recall.jsonl), [MemGPT analysis](../design-analyses/E7-MemGPT.md). Earlier native runs remain ABORT. The [native reassessment](../evolution-07/native-reassessment/flight-card.md) verified OFF isolation and ON retrieval, but ON failed to return the exact fact and provenance. |
| E8 | Identify which permission the re-flight exercised | [Scope correction](../evolution-08/flight-log.md#permission-scope-clarification-for-reassessment) and [OpenCode design analysis](../evolution-08/design-analysis.md). The [native role-correlated capture](../evolution-08/evidence/reassessment/tool-exposure.json) confirms Reviewer write-tool withholding. No Reviewer write request was made. |
| E9 | Preserve third-attempt accounting and qualification | [Cross-family receipts](../evolution-09/evidence/attempt-3/) and [AI log](../AI_LOG.md#e9-attempt-3--cross-family-re-flight--november-23-2026). |
| E10 | Push-triggered gate, deeper design analysis and a discriminating hollow check | [Published push run](https://github.com/WTAMU-CIDM6333/CIDM6333-Fall2026-Joseph-Edafiadhe/actions/runs/45552174473), [E10 amendment](../evolution-10/hollow-amendment.md) and [design analysis](../design-analyses/E10-SWE-bench-Verified.md). |
| E11 | Give the instructor direct access to the later evidence | [Flight](../evolution-11/flight-log.md), [Chase review](../evolution-11/chase-review.md) and [A0 limitations](../evolution-11/lab/worksheet.md). The later published run is available for reassessment. |
| E12 | Demonstrate rollback of exact attested artifact | [Cold replay and ledger](../evolution-12/flight-log.md). The release trial and retry are offline. The product release belongs to the excluded Fifth Pick workstream. |
| Pocock–Humpherys activity | Locate all 13 questions or existing submission | The provided EPUB names the activity but contains no questions. The original worksheet or WTClass submission is needed. |
| Reciprocal Chase | Supply evidence that Joseph served in the reciprocal role | The [agent-partner exchange](../evolution-11/reciprocal/chase-review.md) has a separate target owner, two delegated probes, a GO and a verdict. Acceptance of this substitute remains with the instructor. |

The [design-analysis ledger](../design-analyses/LEDGER.md) now indexes
all 13 Evolution numbers. No grading level is claimed on that basis alone.

## Verification for the reassessment batch

| Check | Exit | Observation |
| --- | ---: | --- |
| Ruff lint | 0 | Passed. |
| Ruff format check | 0 | Passed. |
| ty | 0 | Passed. |
| Network-blocked root unittest discovery | 0 | 724 passed. |
| Targeted E6 and E7 pytest | 0 | 37 passed with local loopback and macOS sandbox available. The first run under the outer sandbox failed 11 isolation tests. |
| E4 pytest in a disposable clone | 0 | 2 passed. |
| E10 grader unit tests | 0 | 2 passed. |
| Git whitespace check | 0 | Passed on the scoped submission. |

The alternate harnesses run independently of the Fifth Pick production
source. Git records the original attempts separately from later GO decisions
and evidence. No provider requests or application release were made for
this batch.
