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

## Reassessment of the four focus components

**Evaluation and feedback.** A passing test can accept an implementation
that satisfies an assertion without satisfying the issue. A narrow test can
also reject a valid fix. OpenAI's audit found flawed tests in at least
59.4% of the audited hard subset. That denominator is the audited subset,
which covered 27.6% of the benchmark. The E10 authorization-removal witness
shows sensitivity to one production change. The separate hollow witness
shows sensitivity to one deliberately weakened assertion. Neither measures
all possible defects. [Audit](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/)

**Perception.** A coding agent can inspect repository files and run commands
its harness exposes. A tester needs to know which assertions, expected
answers and prior patches are visible. A visible answer can explain a pass
even if the intended reasoning never occurred. E10 freezes the answer set
before GO. The deterministic gate then produces results from the code
without an answer-generating model.

**Foundation.** Public issue and patch material can enter training. The audit
recovered reference patches or issue details from the tested models on some
items, and linked exposure with improved success on underspecified tests.
Prior exposure and new reasoning therefore cannot be distinguished by one
green test result. [Audit](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/#contamination)

**Governance and human interface.** Curators decide the benchmark membership,
a code runner produces the pass signal, and evaluators decide what the
signal supports. E10 keeps those responsibilities separate through a frozen
prediction, an executable gate, receipts, and a Chase verdict bounded to
those receipts. The automatic workflow reruns the gate on relevant pushes.
[Class push-triggered run](https://github.com/WTAMU-CIDM6333/CIDM6333-Fall2026-Joseph-Edafiadhe/actions/runs/45552174473)
