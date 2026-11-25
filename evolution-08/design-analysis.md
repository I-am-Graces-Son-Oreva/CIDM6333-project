# Design Analysis · OpenCode subagents

| Component | Observation |
| --- | --- |
| Foundation | The harness can assign a model per role. Our TP4 re-flight used Big Pickle. |
| Perception | The Reviewer receives the artifact and can inspect it through exposed read tools. Exposure is observable separately from tool execution. |
| Memory | A child session has separate context. Evidence needed for the review must arrive through the handoff or authorized reads. |
| Reasoning | The Reviewer identifies deficiencies and gives locations. Python parses the structured verdict. |
| Planning | The parent selects the next role. The project controller determines whether the state permits dispatch. |
| Action | OpenCode grants tools by persona. The challenge test observed automatic rejection of an ask; the separate read-only route has a deny policy. |
| Orchestration | Role configuration bounds capability. A persisted controller transition authorizes a single correction. |
| Evaluation and feedback | A located FAIL and matching artifact hashes prove distinct things. Neither proves request denial on the read-only route. |
| Governance and human interface | Human approval controls the merge. An independent Chase reviews the recorded evidence. |

Use a named read-only Reviewer with a separate context. The extra
session adds wall time and usage, although the free re-flight reported
$0.00. Appendix C mode 1 concerns a prohibited action finding a different
route. The permission profile and fail-closed verdict parser establish
separate boundaries, while tool-exposure and request-outcome evidence
prevent us from conflating the two. [OpenCode agents](https://opencode.ai/docs/agents/) · [E8 re-flight](flight-log.md#targeted-tp4-re-flight--2026-11-23)

**Judgment loop** · Use a separate Reviewer, prioritize independent inspection
and bounded tools, accept a second session, test for safeguard circumvention,
and preserve scope with sealed fixture hashes and separate captures.
