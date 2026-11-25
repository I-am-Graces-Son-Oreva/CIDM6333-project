# Design Analysis · OpenCode 1.18.20 context compaction

| Component | Observation |
| --- | --- |
| Foundation | Model limits are runtime metadata. Deployment-specific limits can differ from a provider's advertising. |
| Perception | Active messages and tool results contribute to measured context. Old tool output may be pruned. |
| Memory | Compaction creates a summary and selects a recent tail. E6 separately persists a keep list and handoff. |
| Reasoning | A model-produced summary can omit the next action or reverse a decision. |
| Planning | The harness chooses when to compact and can append an automatic continuation to the same session. |
| Tools and orchestration | The compaction model summarizes without tools. Application commands run outside that summarize step. |
| Runtime and operations | Compaction costs a model call and latency. OpenCode and E6 use distinct thresholds. |
| Evaluation and feedback | Verify ordering, session identity, the next tool or action, and the retained constraint. A summary alone demonstrates no continuation. |
| Governance and human interface | The operator controls budget and retention. The runtime ledger takes precedence over a stale derived view. |

For an unpublished context window, inspect the *resolved* model metadata
for that runtime. In 1.18.20 a zero context limit disables the automatic
overflow check. With an explicit input limit, the usable budget is that
limit minus reserved tokens, floored at zero. Otherwise, it is context
minus maximum output tokens, floored at zero. The provider-reported count
is compared with that budget. The historical E6 private 8,000-token
budget is an application setting and does not establish the provider limit.
[Version-pinned overflow source](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/session/overflow.ts) · [Version-pinned compaction source](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/session/compaction.ts)

**Judgment loop** · Keep explicit handoff state. Prioritize intent and
provenance, accept an extra state artifact and summarize call, test the
skipped-verification failure mode (Appendix C mode 4), and preserve the
turn budget and next action in the ledger.
