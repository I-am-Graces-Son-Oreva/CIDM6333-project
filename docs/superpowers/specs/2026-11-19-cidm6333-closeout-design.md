# CIDM 6333 Closeout Walkthrough Design

## Intent

Complete the official Closeout Walkthrough as a standalone Python project in the already initialized `/Users/orevisco/multitool` repository. Preserve prior coursework by never accessing or modifying the home-level coursework repository. Keep a human-readable evidence ledger that distinguishes real command output from TUI-only observations that this interface cannot produce.

## Goals

- Implement the five `mt` subcommands and all specified project harness files.
- Use Python 3.14, uv, Ruff, ty, argparse, and standard-library unittest.
- Keep the six required commit messages and run the four gates in order at required checkpoints.
- Preserve real failing and passing test output, tool receipts, and explicit `NOT OBSERVED` results.
- Complete an assurance table that separates instructions from enforceable controls.

## Non-goals and anti-goals

- Do not access or modify the parent home directory or `CIDM6333-project`.
- Do not change Git remotes, push, create a GitHub repository, rewrite history, or bypass a push denial.
- Do not claim a TUI prompt, permission decision, fresh session, skill load, or subagent action without a trace from that interaction.
- Do not weaken tests or permissions to manufacture a pass.

## Constraints

- The current directory is already an empty standalone Git repository named `multitool`; retain it and do not initialize another repository.
- The official walkthrough's exact prompt text is the source of truth for ordering and expected behavior.
- This execution interface can run shell commands and edit project files but does not expose an interactive OpenCode TUI transcript or its live permission controls. Such demonstrations must remain unobserved unless a genuine trace is available.
- The school repository and remote are intentionally out of scope under the user's latest isolation instruction; submission remains pending an authorized destination.

## Approaches

- Nest the project in the coursework repository: rejected because it risks changing unrelated coursework and contradicts the isolated-project setup.
- Search the home directory for a school remote: rejected because the user explicitly prohibited that access.
- Preserve the existing standalone repository, implement and verify locally, and record interaction/submission limits honestly: selected because it follows the professor's isolated setup and the user's scope boundary.

## Implementation choices

- Keep package code in `src/multitool/`, with tests and harness files at the repository root.
- Use the six required commit messages in sequence, with checkpoint/evidence updates included in the relevant commits.
- Capture command output and exit status as actual artifacts; do not synthesize terminal or agent transcripts.
- Do not push. Report that submission requires a user-authorized remote and process after the local work is complete.
