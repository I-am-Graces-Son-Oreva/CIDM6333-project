# Does the independent Reviewer earn its place?

This log records the collaboration that led from Joseph's original question to an offline test. The questions are quoted or lightly edited for readability. The answers are summarized.

## Conversation and design decisions

| What Joseph asked or clarified | What we concluded |
| --- | --- |
| “Is the snapshot part deterministic Python? What belongs to deterministic rule enforcement and what is agentic?” | Python governs whether a snapshot counts, applies player and exact market/direction grants, calculates historical comparisons, and preserves receipts. Agent roles prepare and review artifacts. Joseph makes the final decision. |
| “As an independent reviewer, do you think it’s worth it? Could deterministic Python have accomplished it?” | Python can handle the core workflow by itself. The tool has value as a discipline and audit aid. The strongest case for an agent is to challenge reasoning that satisfies the mechanical checks. |
| “Do you know the major inspiration behind building this tool?” | Joseph wanted to resist tempting weaker picks, accept zero when warranted, and teach a process that others kept asking him to explain. The tool should let beginners see why they might consider or pass on a pick and decide for themselves. A Trusted Player can still miss. The tool makes no outcome prediction or guarantee. |
| “What percent is agentic, and does it earn its place? Honest review, I’m looking to improve.” | The assistant gave an illustrative 80/20 architecture estimate. This was a design judgment, with no measured percentage behind it. The offline demo makes zero model calls. A Reviewer is easier to justify than extra agents on every routine slate, but its value has to be demonstrated. |
| “What does testing against a Python-only baseline mean, and can we run it now?” | Use the same synthetic decision cases. Send only the ones that pass Python’s gates to a local Reviewer. Keep the answer key out of the model input. Count extra catches, misses, false alarms, and elapsed time. |
| “Explain the result further.” | The Reviewer sometimes softened an overclaim in its own explanation while still passing the original wording. That behavior is particularly important when beginners may read PASS as a check of what the proposal actually says. |

## How the test ran

The pilot used eight variants of existing synthetic classroom cases. The Python
baseline invoked the real [T‑20 evaluator](../../src/fifth_pick/t20_review.py)
in a temporary run store. Two cases planted mechanical failures. Six kept their
mechanical evidence intact, with three sound rationales and three planted
reasoning errors. These cases tested proposal reasoning, not player outcomes or
LIVE performance.

The first local Ollama attempt used Qwen3 4B and a fuller Reviewer prompt. It
returned no usable verdict for its first case in about 85 seconds. We stopped
that attempt and scored no results from it.

The completed attempt used Qwen3 1.7B through local Ollama, with a shorter prompt,
a compact batch of six shuffled cases, and structured output. It took 22.95
seconds. The model did not receive the issue labels or expected verdicts. Both
the model and prompt changed between attempts, so the timings do not isolate
the effect of either. This was a local reasoning pilot. The native OpenCode
Reviewer dispatch and receipt binding were outside this test.

## What actually happened

| Case | Proposal or planted issue | Python at T‑20 | Local Reviewer |
| --- | --- | --- | --- |
| P1 | Two head-to-head meetings prove Embiid will clear 28.5 points. | Still strong | PASS. Reframed the claim as a potential high-scoring matchup. |
| P2 | Snapshot 3 is missing. | Remove recommended | Outside the review queue. |
| P3 | The seed gap makes early rest possible for Tatum, but the coach’s rotation is uncertain. | Still strong | PASS. |
| P4 | Early fouls could cut Davis’s minutes, and a full rotation could let him clear the line. | Still strong | PASS. |
| P5 | Luka cleared 9.5 assists in all eight games, versus Python’s verified six of eight. | Still strong | PASS. Said “most games” without flagging the wrong count. |
| P6 | The judgment cites a nonexistent evidence item. | Remove recommended | Outside the review queue. |
| P7 | Two same-opponent games support considering Embiid Higher, with a limited sample. | Still strong | PASS. |
| P8 | The seed gap establishes that Tatum’s coach will sit him early. | Still strong | PASS. Reframed early rest as something the coach may do. |

Python blocked **2 of 2** mechanical failures. The Reviewer caught **0 of 3**
planted reasoning flaws and raised **0 false alarms on 3** sound rationales.
The most revealing case was Luka. Python already had the correct 6/8 count,
but its gates did not compare that count to the prose claim. The model’s
response showed it could use a weaker claim without identifying the original
as false.

[Preserved pilot evidence](evidence/reviewer-pilot.json) includes the Python
results, the exact compact model request, and the returned verdicts. The
evaluation used synthetic records and no external API credits.

## What this means for The Fifth Pick

The tool is useful when people can understand the case for a selection,
understand why they might pass, and accept **NO ENTRY** when the evidence
falls short. Python’s checks and the owner’s final decision are central to
that purpose. This pilot gives no evidence that the tested Reviewer improved
those decisions.

The next improvement to test is to let Python render verifiable counts directly
and give the Reviewer a narrower claim-checking task. It should identify the
exact claim, cite what supports or contradicts it, and state whether the claim
overreaches. A future comparison should use fresh cases and score both missed
issues and false alarms. A small pilot with one completed model configuration
cannot establish how other models or review designs would perform.

### Presentation takeaway

> I gave the agent a job Python doesn’t currently do: challenge the reasoning.
> Then I tested whether it did that job well. In this pilot, it didn’t catch the
> problems I planted. That’s why Python enforces the rules, and why the Reviewer
> has to prove it adds value.
