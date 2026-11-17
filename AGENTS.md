# The Fifth Pick — NBA Fantasy Selection & Discipline

The Fifth Pick is a human-governed NBA fantasy-selection CLI that applies Joseph's approved methodology; it must never change that methodology, authorize outside his universe, or finalize a slate without his authority.

## Run and test

The Fifth Pick M1 health-only, M2 model/receipt/storage, M3 configuration/registry/identity/authorization, M4 source, and M5 snapshot foundations exist; the M5 reviewer returned PASS. Joseph authorized M6 evidence/methodology/confidence/ranking only. Do not begin M7 before M6 review PASS. M5/M6 acceptance uses offline boards and requires no live API request.

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

All four must exit `0`. Show a failing gate before claiming the gates as evidence. Use Python, `uv`, `ruff`, `ty`, and `unittest`; not pytest. The M1 console command is `fifth-pick health`; domain commands remain planned.

## Conventions that differ from defaults

- Python CLI only; no website, GUI, or pytest.
- Superpowers discipline; Standard Technical English; project skills for evaluation, evidence, final-slate, and T-20 review.
- The Odds API `us_dfs` is the approved board source for PrizePicks and Underdog: `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, `player_rebounds_assists`.
- `THREE_POINT_ATTEMPTS` is outside the live MVP; never substitute threes made or fabricate attempts.
- Never scrape the platforms, NBA.com, or SI; no cookies, login automation, unofficial endpoints, or NBA.com statistical feeds.
- Keep PrizePicks and Underdog lines separate; never combine them.
- Canonical player registry; no name-only matching; ambiguous identity fails closed.
- Three legitimate observations; Snapshot 3 = T-20; never backfill.
- No alternate markets by default; multipliers optional.
- DNP/void are not MISS; use `RESULT UNAVAILABLE` when no trustworthy result.
- Malik Monk is unselectable until Joseph defines category and direction.

## Rules that must hold (enforced)

- No entries, wagers, logins, or money movement. Control: no submission path or credentials.
- No methodology or authorization change. Control: frozen spec, digest-pinned M3 universe, exact `AuthorizationGate`, M6 evidence-citation/confidence guards, and ranking/persistence that accept only `CandidateCase` inputs and run methodology internally; M7+ execution is not built.
- No outside-universe or trust-tier authorization. Control: digest-pinned allow-list and authorization-first exact-grant validation.
- No name-only or ambiguous identity. Control: canonical registry, provider-alias-only resolution, and M5 authoritative-player equality check.
- No combined platform projections. Control: platform-scoped source, observation, and snapshot records; verified offline.
- No invented evidence; missing evidence fails closed. Control: typed M6 source/provenance validation, exact three-snapshot checks, LIVE cases bound by run ID to the application-owned M5 ledger and accepted/missed receipts, explicit fixture mode, evidence excerpts, and named gaps/missed-slot receipts; configured live supporting-source access remains unavailable and fails closed.
- Ceilings: HALF 1–4 / max 4; FULL 5+ / max 5; zero valid; never fill slots. Control: finalizer; not built.
- No snapshot backfill or fabricated T-20. Control: M5 snapshot ledger, target validation, missed-slot markers, and receipts.
- No HIT/MISS without trustworthy result. Control: result adjudicator; not built.
- Reviewer cannot edit Builder work; malformed verdicts fail closed; one correction, then Joseph. Control: reviewer role permissions are configured; verdict parser and correction counter remain unbuilt.
- Joseph approval before finalization. Control: approval gate/receipt; not built.
- All four gates pass before completion. Control: the four M1 commands above are runnable mechanical gates.
- Assurance table: real control and evidence per risk; prompt statements are not enforcement.
- Evaluate process separately from outcomes; no hit-rate claims without evidence; record evidence, rules, exclusions, rankings, stop reason, and outcome.

## Where the truth lives

- Frozen design: `docs/superpowers/specs/2026-11-13-fifth-pick-design.md`.
- Product requirements: `docs/PRD.md`.
- Purpose and PEAS: `evolution-00/pitch.md`; choices: `evolution-00/choices.md`; judgments: `design-analyses/LEDGER.md`.
- Strategy: skill files.
- Historical Evolution 00–08: do not rewrite.

This control map points to the spec and PRD for detailed purpose, selection, stop gate, evaluation, and context.
