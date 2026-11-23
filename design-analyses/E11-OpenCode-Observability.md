# Design Analysis · OpenCode export and local evidence

| Component | Observation |
| --- | --- |
| Foundation | The local model emits replies and can propose actions. |
| Perception | The agent receives input and any tool results made available to it. |
| Memory | OpenCode keeps sessions in its local store, including information absent from the submitted slice. |
| Reasoning | The session narrative may describe why the model acted, but its claims need corroboration. |
| Planning | Tool calls and their ordering expose the observed execution path. |
| Action | OpenCode permission rules mediate tool execution. The A0 sessions did not reach the write check. |
| Evaluation and feedback | Exported tool events distinguish a model omission from an enforced error. A separate scratch-state check supports file-state claims. |
| Runtime and operations | Raw captures stay in scratch storage. An allowlisted projection retains timing, model usage, tool IDs and status. |
| Governance and human interface | The Chase receives sanitized evidence, and Git binds the permission cards, approvals and observed artifacts to the exercise. |

Keeping only metadata makes adjudication possible without publishing notes,
tool arguments or model replies. The corresponding cost is losing literal
argument evidence. Payload hashes preserve enough identity for a reviewer to
compare a frozen fixture with its delivery record. [OpenCode CLI](https://opencode.ai/docs/cli/) · [OpenCode permissions](https://opencode.ai/docs/permissions/) · [Course Figure 12](https://ahuimanu.github.io/CIDM6333/figures/receipts-over-narrative.html)

**Judgment loop** · Use a metadata-only evidence slice. Prioritize auditability
and limited disclosure. Accept less transcript detail. Address Appendix C
mode 8 by omitting content, redacting synthetic secret text, and checking the
published tree for the unique marker.
