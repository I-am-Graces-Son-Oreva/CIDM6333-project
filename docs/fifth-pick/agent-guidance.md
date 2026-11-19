# The Fifth Pick — NBA Fantasy Selection & Discipline

The Fifth Pick is a human-governed NBA fantasy-selection CLI that applies Joseph's approved methodology; it must never change that methodology, authorize outside his universe, or finalize a slate without his authority.

## Run and test

The Fifth Pick M1 health-only, M2 model/receipt/storage, M3 configuration/registry/identity/authorization, M4 source, M5 snapshot, M6 methodology/ranking, M7 T-20, and M8 finalization/approval foundations exist. M9 result settlement and grading is complete under offline fixture and manual-provenance scope. No live player-result retrieval is authorized. Joseph accepted M10 **WITH QUALIFICATION** for OpenCode 1.18.20 after the final Task 7 independent recheck PASS. The roadmap's course closeout has not been authorized. See `docs/fifth-pick/gates.md` for the formal decision and evidence.

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

All four must exit `0`. Show a failing gate before claiming the gates as evidence. Use Python, `uv`, `ruff`, `ty`, and `unittest`; not pytest. The M1 console command is `fifth-pick health`; M8 adds interactive `fifth-pick decide --run-id RUN_ID`; M9 adds `fifth-pick result record --run-id RUN_ID --selection SELECTION_ID`.

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
- No methodology or authorization change. Control: frozen spec, digest-pinned M3 universe, exact `AuthorizationGate`, M6 evidence-citation/confidence guards, M7 receipt-bound T-20 review, M8 finalization that accepts only `CandidateCase` inputs and runs ranking internally, and M9 results bound to receipt-verified M8 approval; M10 applies the bounded review workflow within those controls.
- No outside-universe or trust-tier authorization. Control: digest-pinned allow-list and authorization-first exact-grant validation.
- No name-only or ambiguous identity. Control: canonical registry, provider-alias-only resolution, and M5 authoritative-player equality check.
- No combined platform projections. Control: platform-scoped source, observation, and snapshot records; verified offline.
- No invented evidence; missing evidence fails closed. Control: typed M6 source/provenance validation, exact three-snapshot checks, LIVE cases bound by run ID to the application-owned M5 ledger and accepted/missed receipts, explicit fixture mode, evidence excerpts, and named gaps/missed-slot receipts; configured live supporting-source access remains unavailable and fails closed.
- Ceilings: HALF 1–4 / max 4; FULL 5+ / max 5; zero valid; never fill slots. Control: M8 derives the slate only from the receipt-bound run-start M4 manifest, requires the application-owned store for LIVE runs, rejects mixed LIVE/FIXTURE inputs, freezes the M6 ceiling pool before M7 removals, and never promotes replacements.
- No snapshot backfill or fabricated T-20. Control: M5 snapshot ledger, target validation, missed-slot markers, and receipts.
- No HIT/MISS without trustworthy result. Control: M9 binds each result to the receipt-verified M8-approved `candidate_key`, requires provenance for determinate outcomes, records result receipts, and uses `RESULT UNAVAILABLE` when settlement is untrustworthy; no automatic player-result retrieval is built.
- Reviewer cannot edit Builder work; malformed verdicts fail closed; one correction, then Joseph. Control: native Reviewer permissions remain configured; `src/fifth_pick/review.py` and `src/fifth_pick/review_bridge.py` implement and test strict parsing, review-material digest binding, M2 receipt history, and bounded transitions under a per-run OS lock. `.opencode/plugin/fifth-pick-review-adapter.ts` remains a non-authoritative transport adapter; only the response that newly persisted `REVISION_ATTEMPT` authorizes the controller to dispatch Builder. Replay or uncertain launch stops for Joseph. Isolated host activation, event delivery, PASS receipt, and invalid-verdict STOPPED are recorded in `docs/fifth-pick/gates.md`. Under the approved OpenCode 1.18.20 addendum, **NATIVE TOOL WITHHOLDING VERIFIED** for edit and Bash/shell-write. Read-oriented tools were exposed, while write-capable tools were withheld. Route A only: Correlated native-denial evidence remains BLOCKED. **REQUEST-TO-DENIAL BEHAVIOR UNVERIFIED**. Live second-FAIL/CONCERNS escalation remains **UNVERIFIED**, with offline regression coverage. See the current evidence in `docs/fifth-pick/gates.md`. Joseph accepted M10 with these qualifications on 2026-11-18.
- Joseph approval before official final state. Control: interactive `decide` is the only supported Joseph decision path and accepts exact `APPROVE`, `REJECT`, or `MODIFY`; the receipt is persisted before an approved/rejected state, and MODIFY can retain only a subset of the displayed proposal while preserving NO ENTRY.
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
