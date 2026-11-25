# Design Analysis · MemGPT

| Component | Observation |
| --- | --- |
| Foundation | A finite-context language model motivates virtual context management. |
| Perception | The model sees the active prompt and retrieved results. |
| Memory | Memory is tiered. Data moves between limited active context and external storage. |
| Reasoning | The model chooses when retrieved context is relevant to its task. |
| Planning | Interrupts support multi-step control flow around memory operations and user interaction. |
| Action | Memory tools allow paging and retrieval rather than placing the entire archive in the prompt. |
| Runtime and operations | External memory adds lookup, storage, and prompt overhead. |
| Evaluation and feedback | The paper studies document analysis and multi-session chat. An observed recall still needs a control for other access paths. |
| Governance and human interface | Users interact across sessions. An application deploying memory must decide separately what may be retained, removed, or exposed. |

MemGPT makes context available across a limited window, at the cost of extra
tool calls and stored data. E7 uses a smaller retriever for its controlled
experiment. OFF, absent, and eviction conditions answer distinct questions.
OFF rules out another access path, absent tests unsupported output, and
eviction tests whether forgotten data can still surface. The historical
ABORT remains an evidence gap. [MemGPT paper](https://arxiv.org/abs/2310.08560)

**Judgment loop** · Use explicit retrieval, privilege observable provenance,
pay storage and lookup costs, test fabrication when recall returns nothing
(Appendix C mode 3), and preserve condition and retrieval records separately.
