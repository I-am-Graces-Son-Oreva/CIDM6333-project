# Design Analysis · SWE-bench Verified

| Component | Observation |
| --- | --- |
| Foundation | Public GitHub issues and fixes may already appear in model training data. |
| Perception | The agent receives an issue and repository snapshot. Access to answers or trusted tests changes what a pass means. |
| Memory | The checked-out repository supplies task context. |
| Reasoning | The agent traces the issue and proposes a patch. |
| Planning | It decides which files to inspect and tests to run. |
| Action | The harness applies the proposed patch. |
| Evaluation and feedback | Fail-to-pass and pass-to-pass tests check sampled behavior. Weak tests can accept shortcuts, and overly specific tests can reject valid fixes. |
| Governance | Humans curate tasks and interpret what the execution verdict establishes. |
| Interface | Repository issues enter the system and patch results leave it. |

Verified's human curation improved task quality, but the February 2026
retirement analysis documented remaining grading flaws and contamination.
Our gate must rule out answer-derived expectations and constant outputs
that satisfy an under-specified assertion. [SWE-bench paper](https://arxiv.org/abs/2310.06770) · [Verified introduction](https://openai.com/index/introducing-swe-bench-verified/) · [February 2026 reassessment](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/)

**Judgment loop** · Use requirement-derived cases and an exact mutation.
Prioritize reproducibility at the cost of narrow coverage. Counter hollow
passes with both Boolean stubs and preserve the card, receipts, and Chase
verdict in Git.
