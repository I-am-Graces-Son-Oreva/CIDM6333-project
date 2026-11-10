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