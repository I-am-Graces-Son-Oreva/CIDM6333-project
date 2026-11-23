# Design Analysis — Anthropic’s multi-agent research system

| Dimension | Observation |
| --- | --- |
| Purpose | Research queries whose subquestions can be investigated independently. |
| Environment | Open-ended information retrieval with multiple sources and uncertain evidence. |
| Inputs | A user question and access to search and retrieval tools. |
| Outputs | A synthesized research response with citations. |
| Reasoning | The lead forms a research plan, adjusts it as findings arrive and decides whether more investigation is useful. |
| Coordination | A lead agent delegates scoped questions to parallel subagents. Subagents explore distinct leads and report findings. The lead has to resolve disagreement and synthesize across results. Overlap wastes work. |
| Memory and context | Plans and intermediate findings are preserved across limited agent context. Short handoffs help the lead, but can conceal gaps in primary evidence. |
| Evaluation and feedback | Anthropic reports a 90.2% improvement over its single-agent baseline on an internal research evaluation. That finding concerns its research workload. For E9, pair each narrowly scoped claim with machine-produced evidence and test whether an adversary can refute it. |
| Runtime and operations | Anthropic measured roughly 15 times chat token usage for its multi-agent system. Parallelism can shorten elapsed time while increasing aggregate token use. Narrow tasks need a cost ceiling and fewer calls. |

**Why.** Parallel specialists make sense when the question separates cleanly
and evidence can be checked. E9 has one narrow contradiction, so adding more
workers would increase coordination cost with little benefit. A polished
summary that claims the tests passed is a risk under MAST FM-3.3, incorrect
verification, if an evaluator reads the summary in place of the command
result. The course’s Appendix C #3 calls out fabrication. Preserving the
worker report as an unverified claim keeps it available for inspection while
preventing it from acquiring the authority of a receipt.

**Judgment loop.** Use a small cross-family review and a deterministic receipt.
Privilege independent verification and traceability. Accept the cost of a
separate call under a fixed budget. The failure mode is approving a plausible
summary that contradicts the test result. Preserve the command output hash,
model identity, verdict citation, and separate Chase attestation.

Sources for reported measurements and taxonomy are [Anthropic’s engineering
report](https://www.anthropic.com/research/multi-agent-research-system),
[Cemri et al.’s MAST paper](https://arxiv.org/abs/2503.13657), and the
[course figure](https://ahuimanu.github.io/CIDM6333/figures/claim-receipt-verdict.html).
