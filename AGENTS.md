# The Fifth Pick — NBA Fantasy Selection & Discipline

## Run and test

Launch `uv run --offline --no-sync fifth-pick menu`. Demo is default. Use Python, uv, Ruff, ty, and unittest. Run all four gates and record exit codes. Show a failing gate before claiming the gates as evidence.

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

M1–M9 remain accepted under their recorded scopes. M10 is ACCEPTED WITH QUALIFICATION under the OpenCode 1.18.20 addendum. See the gate record and complete operational guidance below.

## Conventions that differ from defaults

- Python CLI only. Follow Superpowers discipline, Standard Technical English, and project evaluation, evidence, final-slate, and T-20 skills.
- The Odds API `us_dfs` is the sole approved board route. Keep PrizePicks and Underdog lines separate. Use points, assists, rebounds, PRA, and rebounds+assists. No alternate markets by default. Multipliers are optional. THREE_POINT_ATTEMPTS is outside the live MVP.
- No scraping the platforms, NBA.com, or SI. No account cookies, login automation, unofficial endpoints, or NBA.com statistical feeds. Keep credentials in the process environment. Approved discovery is quota-free. Paid requests require Joseph's explicit scoped budget.
- Canonical identity and exact category/direction grants precede analysis. Unknown or ambiguous provider labels fail closed. No expansion or trust-derived authorization. Malik Monk remains unselectable until Joseph defines category and direction.

## Rules that must hold (enforced)

- Governance Zero follows Joseph → Controller → Planner → Builder → independent Reviewer → Controller → Joseph. No entry submission, wagers, login, money movement, or autonomous decisions.
- Preserve frozen methodology and evidence provenance, LIVE/FIXTURE separation, exact three observations, real T-20, and receipt integrity. No backfill, invented evidence, or unapproved source. Missing evidence fails closed.
- Full receipt-bound slate governs max four picks for 1–4 games and max five for 5+. One slot per player. Freeze the pool, never refill, and retain `NO ENTRY RECOMMENDED TODAY.` Joseph alone can authorize LOW promotion.
- Malformed review fails closed. Only a newly persisted REVISION_ATTEMPT may authorize one Builder dispatch. Replay, uncertainty, second FAIL, or CONCERNS stops for Joseph. Preserve native Reviewer permissions.
- OpenCode 1.18.20 native tool withholding VERIFIED for both write routes. Read tools were exposed. REQUEST-TO-DENIAL BEHAVIOR UNVERIFIED for both routes. Live second-FAIL/CONCERNS escalation UNVERIFIED, with offline regression coverage.
- Route A only. Correlated native-denial evidence remains BLOCKED.
- `decide` requires Joseph's explicit APPROVE, REJECT, or MODIFY. MODIFY is subset-only. Approve only the exact reviewed LIVE selection before tipoff. Persist approval before settlement. DNP and void are not MISS. Use RESULT UNAVAILABLE absent trustworthy provenance.
- Record process and outcomes separately. Assurance maps risks to mechanical controls and evidence. No unsupported hit-rate claims.

## Where the truth lives

- Full operational guidance and controls: `final-project/docs/fifth-pick/agent-guidance.md`.
- Frozen design: `final-project/docs/superpowers/specs/2026-11-13-fifth-pick-design.md`. PRD: `final-project/docs/PRD.md`.
- Acceptance, runtime qualifications, and operating evidence: `final-project/docs/fifth-pick/gates.md`, `harness.md`, `assurance.md`, and `runbook.md` in that directory.
- Purpose and PEAS: `evolution-00/pitch.md`. Choices: `evolution-00/choices.md`. Judgments: `design-analyses/LEDGER.md`. Preserve Evolution 00–08.
