# AGENTS.md Measurement

## Setup
- OpenCode version: 1.18.20
- Model: `opencode/big-pickle`

## File Size
- `wc -c AGENTS.md`: 852 bytes
- Budget: 4,000 characters

## Loaded Context Measurement
- Baseline without `AGENTS.md`: 8.5K input tokens (displayed)
- With `AGENTS.md`: 8.7K input tokens (displayed)
- Displayed difference: approximately 0.2K (~200 tokens)

## Read Check
- Prompt: `What does this project's AGENTS.md say the test command is?`
- OpenCode response: `It doesn't specify a test command.`
- Result: Finding — the current `AGENTS.md` does not specify a test command, so there was no verbatim test command to recall.

## /init Comparison
- Hand-written `AGENTS.md`: 852 bytes
- `/init` generated `AGENTS.md`: 1,923 bytes

## Chase Review
- Probe 1 — Encyclopedia: No encyclopedia entry found. The “Where the truth lives” lines are pointers to source files.
- Probe 2 — Wishful rule: `No automatic applicant rejection or fraud declaration. Enforced by: nothing yet — see GHI #1.` GHI #1 tracks the missing enforcement.
- Probe 3 — Unverifiable instruction: Revised to define each required technical term in plain English the first time it appears.
- Final Chase verdict: Pending partner's final confirmation.
## Reassessment

The historical file was added in `fe1f1d2`. The [reassessment ledger](reassessment-ledger.jsonl)
records the observed Git event with the current record date. The rounded
interface readings establish an approximate difference of 200 tokens.
If each value was rounded to the nearest 100, the difference could range
from about 100 to 300 tokens. Session identifiers for that before/after
pair are absent from this record, so an exact provider-counter difference
is unverified. The original partner verdict remains pending.

### Recovered exact counters

A read-only inspection of OpenCode's retained message records found two
chronological pairs of Big Pickle calls with the same single-word prompt
and matching rounded display counts. The original worksheet did not record
the IDs needed to identify which pair it used.

| Candidate pair (UTC, September 23, 2026) | Baseline candidate | With-file candidate | Exact observed difference |
|---|---:|---:|---:|
| 03:05:33 → 03:12:42 | 8,530 | 8,720 | +190 |
| 03:24:40 → 03:27:33 | 8,530 | 8,704 | +174 |

The [sanitized measurement receipt](recovered-token-counts.json) preserves
session and message IDs, prompt hashes, and exact counters. Input includes
uncached and cache-read tokens. Cache writes were zero and output is excluded.
The exact observed differences corroborate the estimate of about 200 tokens.
The original record cannot bind either pair to the reported file toggle.

### Carry-forward question

The current rule has an enforcement point in
[`_finalize_locked_slate`](../../../final-project/src/fifth_pick/finalization.py).
When finalization has no blocking reasons and the proposed set is empty,
Python assigns `NO_ENTRY` and the exact recommendation text. A blocked
finalization follows a separate branch. The
[zero-game regression test](../../../final-project/tests/test_finalization.py)
asserts both the state and the exact sentence.

### Independent reassessment verdict

**Scoped PASS — Codex independent Chase — November 25, 2026 — `8b2cbc9`.**
The 852-byte file passed the budget and concise-pointer check. It explicitly
marked the admission rule as unenforced and pointed to GHI #1. The
first-use definition instruction provides a specific output reviewers can
check. The recorded read check correctly found no test command. This
archival verdict covers the three probes. The original partner's
confirmation remains pending.
