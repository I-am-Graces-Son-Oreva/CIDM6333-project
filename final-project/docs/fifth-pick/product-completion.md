# Product completion coverage and decisions

This matrix follows the frozen [Part II and Part III design](../superpowers/specs/2026-11-13-fifth-pick-design.md) and the [PRD](../PRD.md). It records product coverage separately from [historical M1–M10 acceptance](gates.md). Offline verification does not establish current provider coverage or change the qualified OpenCode 1.18.20 security evidence.

## Personal launch status

- The fixture CLI exercises board ingestion, three observations, M6 ranking,
  M7 review, an explicit Joseph decision, settlement, audit, and evaluation.
  Native M10 verification remains separate from review of a real NBA proposal.
- Joseph verified authenticated NBA event discovery and quota reporting over
  TLS on November 18. This established a 491-credit balance at that check and
  a zero-credit discovery charge. The complete response was not saved in the
  workspace. The new preflight path persists future successful responses and
  displays event-local deadlines offline.
- One-event LIVE collection and replay are verified offline. A real response
  must still establish both platforms, market availability, identity coverage,
  accepted observations, and the measured charge. The LIVE approval path
  now requires a matching completed M10 PASS for the exact nonempty proposal
  before Joseph can approve selected lines. Corrected proposals and escalated
  findings still require an explicit release policy.
- Minimum product validation uses one authorized event and all three genuine
  observation windows under one pinned live run. Reserve up to 15 board
  credits. This excludes any separately approved game-lines or player-data
  cost. The terminal defaults to a Snapshot 1 pilot and supports a separately
  confirmed three-slot series. A full validation
  also requires an approved live evidence route and timing/release policy.

## Part II sections

| Section | Status | Implementation or limitation |
| --- | --- | --- |
| 1 — Project Identity | Offline verified | Python CLI, explicit Joseph decision and no submission path. `cli.py`, `approval.py`. |
| 2 — Course and Harness Constraints | Partial / course | Existing roadmap, assurance, gates and M10 history remain separate from submission and product acceptance. |
| 3 — Governance Zero | Offline verified | Python CLI, explicit Joseph decision and no submission path. `cli.py`, `approval.py`. |
| 4 — No Automatic Entry or Wager Execution | Offline verified | Python CLI, explicit Joseph decision and no submission path. `cli.py`, `approval.py`. |
| 5 — Slate-Size Discipline | Offline verified | Full run-start manifest, ceilings, and one slot per player. `slate_manifest.py`, `finalization.py`. |
| 6 — One Player Equals One Final Slot | Offline verified | Full run-start manifest, ceilings, and one slot per player. `slate_manifest.py`, `finalization.py`. |
| 7 — Approved Candidate Universe and No Do-Not-Pick List | Offline verified | Digest-pinned universe, category map, exact grants and trust-as-context. `config.py`, `authorization.py`. |
| 8 — Persistent Universe, Not a Daily List | Offline verified | Digest-pinned universe, category map, exact grants and trust-as-context. `config.py`, `authorization.py`. |
| 9 — Approved Universe — Current Authoritative Input | Offline verified | Digest-pinned universe, category map, exact grants and trust-as-context. `config.py`, `authorization.py`. |
| 10 — Player Identity | Partial | Canonical registry and exact verified labels. Production identity evidence and actual LIVE coverage pending. |
| 11 — Category Normalization | Offline verified | Digest-pinned universe, category map, exact grants and trust-as-context. `config.py`, `authorization.py`. |
| 12 — Trust-Tier Categories Do Not Authorize (Superseded by Part III E4) | Offline verified | Digest-pinned universe, category map, exact grants and trust-as-context. `config.py`, `authorization.py`. |
| 13 — Senior Players | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 14 — Senior Lower Philosophy | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 15 — Senior Projection-Movement Heuristic | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 16 — PRA Trust | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 17 — Assist Trust | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 18 — Rebound Trust | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 19 — Non-Senior / Showoff Heuristic | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 20 — Foul-Trouble Annotation | Offline verified | Typed M6 judgments, confidence constraints, Senior precedence and risk disclosures. `methodology.py`, `ranking.py`. |
| 21 — Matchup Analysis | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 22 — High-Scoring Game Environment | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 23 — Game Spread / Blowout Signal | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 24 — Last-8 Analysis | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 25 — Same-Season Head-to-Head | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 26 — Player Trades / Roster Changes | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 27 — Role and Minutes Security | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 28 — Suspiciously Attractive Projections | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 29 — Automatic Fantasy-Board Retrieval | Partial | M4/Stage 1 and guarded event discovery. First product LIVE smoke not performed. |
| 30 — Access Policy | Implemented | Only approved route in code; no platform scraping, login or entry submission. |
| 31 — Supporting NBA Sources | Partial / source blocked | Supporting source policy and sport-level game-line validation offline. Compliant routes and live policies pending. |
| 32 — Game Totals and Spread Source | Partial / source blocked | Supporting source policy and sport-level game-line validation offline. Compliant routes and live policies pending. |
| 33 — Three Projection Snapshots | Partial / policy blocked | M5/M7 enforce frozen slot rules offline; schedule view reports event readiness. Real-time T-20 closure and release across staggered games need owner policy. |
| 34 — Required Candidate Evidence | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 35 — Missing Evidence Rule | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 36 — Conflicting Evidence / Risk | Partial / source blocked | M6 typed evidence, gap handling and fixture history. LIVE quantitative and contextual facts require authorized provenance. |
| 37 — Confidence System | Offline verified | M6 confidence, rank and named gaps. M8 freezes the ranked ceiling pool and never refills. |
| 38 — Rejection / Status Reasons | Offline verified | M6 confidence, rank and named gaps. M8 freezes the ranked ceiling pool and never refills. |
| 39 — Ranking | Offline verified | M6 confidence, rank and named gaps. M8 freezes the ranked ceiling pool and never refills. |
| 40 — Replacement / Displacement | Offline verified | M6 confidence, rank and named gaps. M8 freezes the ranked ceiling pool and never refills. |
| 41 — T-20 Final Review | Partial / policy blocked | M5/M7 enforce frozen slot rules offline; schedule view reports event readiness. Real-time T-20 closure and release across staggered games need owner policy. |
| 42 — Final CLI Output | Offline verified | Existing Demo Mode, CLI steps, current reviewed values, explicit approval, and exact grading binding. Live journey is partial. |
| 43 — CLI Command Concept | Offline verified | Existing Demo Mode, CLI steps, current reviewed values, explicit approval, and exact grading binding. Live journey is partial. |
| 44 — Finalization Requires Joseph | Offline verified | Existing Demo Mode, CLI steps, current reviewed values, explicit approval, and exact grading binding. Live journey is partial. |
| 45 — Normal Board Filter Output | Partial | M4/Stage 1 and guarded event discovery. First product LIVE smoke not performed. |
| 46 — Universe Change Control | Offline verified | Digest-pinned universe, category map, exact grants and trust-as-context. `config.py`, `authorization.py`. |
| 47 — Planner | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 48 — Builder | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 49 — Reviewer | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 50 — Controller | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 51 — One Correction Attempt | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 52 — Current Typed Agent Statuses | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 53 — Permissions | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 54 — AGENTS.md | Partial / course | Existing roadmap, assurance, gates and M10 history remain separate from submission and product acceptance. |
| 55 — Authoritative Config / Spec Structure | Offline verified | Digest-pinned universe, category map, exact grants and trust-as-context. `config.py`, `authorization.py`. |
| 56 — Skills | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 57 — Standard Technical English | Implemented | Typed application checks and deterministic fixtures with actual source and retrieval timestamps retained. |
| 58 — Determinism | Implemented | Typed application checks and deterministic fixtures with actual source and retrieval timestamps retained. |
| 59 — Hooks and Receipts | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 60 — Assurance Table | Partial / course | Existing roadmap, assurance, gates and M10 history remain separate from submission and product acceptance. |
| 61 — Quality Gates | Partial / course | Existing roadmap, assurance, gates and M10 history remain separate from submission and product acceptance. |
| 62 — Fifth Pick Governance Tests | Partial at product level | Accepted M10 controls and qualified host evidence preserved; product review binds real NBA fixture evidence to native command/receipts. Native product run and correction-to-proposal binding unverified/incomplete. |
| 63 — Post-Game Result Collection | Offline verified under E12 | Receipt-bound, provenance-confirmed settlement; unavailable results remain unavailable. No automated result retrieval. |
| 64 — Experiment Evaluation | Partial | Separate process and outcome evaluation and receipted displayed proposal history. Historical gaps and counterfactuals remain explicitly unknown. |
| 65 — Track Joseph's Overrides | Partial | Separate process and outcome evaluation and receipted displayed proposal history. Historical gaps and counterfactuals remain explicitly unknown. |
| 66 — Project Success | Partial / course | Existing roadmap, assurance, gates and M10 history remain separate from submission and product acceptance. |
| 67 — Repository Philosophy | Partial / course | Existing roadmap, assurance, gates and M10 history remain separate from submission and product acceptance. |
| 68 — Current Conceptual Project Shape | Partial | Python CLI and fixture workflow, plus guarded LIVE board preparation. Supporting/live workflow blockers below. |
| 69 — Items That May Still Require Resolution | Historical | Part III supersedes conflicting unresolved entries. No additional authority inferred. |
| 70 — Source-Retrieval Failure | Offline verified | Named errors, stop receipts, no retry or backfill and exact no-entry behavior. Live source failures not observed by this work. |
| 71 — Design Principle | Offline verified | Named errors, stop receipts, no retry or backfill and exact no-entry behavior. Live source failures not observed by this work. |

## PRD acceptance criteria

| Criterion | Status | Implementation or limitation |
| --- | --- | --- |
| 1 — The system provides a CLI for analyzing a slate, ranking candidates, producing a final slate, performing a T-20 review, and showing an audit trail. | Implemented / offline verified | `cli.py`, `menu.py`, `tests/test_fixture_cli.py`. |
| 2 — The system applies only Joseph's approved player universe and authorized categories and directions. | Implemented / offline verified | `authorization.py`, digest-pinned `approved-universe.yaml`. |
| 3 — The system retrieves current fantasy projections from an approved source and never depends on Joseph manually supplying the board. | Partial | Approved provider and adapter plus offline discovery; production event/alias coverage and smoke approval remain open. |
| 4 — The system never submits entries, places wagers, logs in, or moves money. | Implemented / offline verified | `cli.py` commands terminate at local decision and settlement artifacts. |
| 5 — The system gathers supporting evidence from approved sources and records source identity, retrieval time, source timestamp, access method, and relevant provenance. | Partial / source blocked | Typed and fixture-verified supporting evidence. No approved automated player history; remaining access routes and judgments require a decision. |
| 6 — The system evaluates candidates using Joseph's approved methodology, including: | Partial / source blocked | Typed and fixture-verified supporting evidence. No approved automated player history; remaining access routes and judgments require a decision. |
| 7 — The system assigns confidence as HIGH, MEDIUM, or LOW according to Joseph's approved criteria. | Implemented / offline verified | `methodology.py` verifies confidence and evidence citations. |
| 8 — The system produces a ranked final slate, or `NO ENTRY RECOMMENDED TODAY.`. | Implemented / offline verified | `finalization.py` writes the ranked proposal or exact no-entry output. |
| 9 — The system applies the stop gate: | Implemented / offline verified | `slate_manifest.py` and M8 ceiling, deduplication, and frozen-pool tests. |
| 10 — The system performs a T-20 review and can retain, downgrade, or remove a candidate. | Partial / timing blocked | Fixture review and event-local schedule status. Exact real-time review remains gated by frozen policy. |
| 11 — The system provides a durable, reviewable audit trail that distinguishes process quality from outcome. | Implemented / offline verified | `audit_view` and `evaluation_view` separate process, human decisions, and recorded outcomes. |
| 12 — The system never guarantees wins and never claims a hit-rate advantage without evidence. | Implemented / offline verified | M6 confidence and history emit qualitative judgments and descriptive counts. Evaluation reports no hit-rate claim. |
| 13 — The system uses Standard Technical English in human-facing output and defines specialized terms. | Implemented / offline verified | Menu labels and the [operator walkthrough](runbook.md) explain workflow status and actions. |
| 14 — The system uses The Odds API `us_dfs` as the approved MVP board source for PrizePicks and Underdog data, unless Joseph explicitly changes the source. | Partial | Approved provider and adapter plus offline discovery; production event/alias coverage and smoke approval remain open. |
| 15 — The system retrieves only the approved live markets: `player_points`, `player_assists`, `player_rebounds`, `player_points_rebounds_assists`, and `player_rebounds_assists`. | Implemented / offline verified | `sources/odds_api.py` pins the five approved markets and two bookmakers. |
| 16 — The system does not retrieve or evaluate `THREE_POINT_ATTEMPTS` in the live MVP and does not substitute threes made or fabricate attempts. | Implemented / offline verified | `sources/normalize.py` and `authorization.py` exclude three-point attempts from live eligibility. |
| 17 — The system keeps PrizePicks and Underdog projections platform-specific and never synthesizes a combined line. | Implemented / offline verified | M4–M7 candidate identity and snapshots retain platform. |
| 18 — The system uses a local canonical player registry and fails closed on unknown or ambiguous identity. | Partial | Approved provider and adapter plus offline discovery; production event/alias coverage and smoke approval remain open. |
| 19 — The system enforces authorization before methodology and ranking; trust tiers never create authorization. | Implemented / offline verified | `methodology.py` checks exact authorization before ranking and trust classification. |
| 20 — The system records Malik Monk as in-registry but unselectable until Joseph defines both category and direction. | Implemented / offline verified | `approved-universe.yaml` and `authorization.py` deny unresolved category/direction grants. |
| 21 — The system emits a named missing-evidence reason when required evidence is unavailable and does not proceed on invention. | Implemented / offline verified | M5–M8 typed reason codes and missing-evidence/no-entry regressions. |
| 22 — The system records exactly three legitimate projection observations per relevant candidate, with Snapshot 3 at T-20, and never backfills a missed observation. | Partial / timing blocked | Fixture review and event-local schedule status. Exact real-time review remains gated by frozen policy. |
| 23 — The system blocks finalization when T-20 review is unavailable and records `T20_CHECK_UNAVAILABLE`. | Partial / timing blocked | Fixture review and event-local schedule status. Exact real-time review remains gated by frozen policy. |
| 24 — The system treats multiplier data as optional metadata and remains able to evaluate a valid projection when no multiplier is available. | Implemented / offline verified | M4 normalization and M5 snapshots permit absent multiplier. |
| 25 — The system never marks HIT or MISS without a trustworthy result; DNP and void are not MISS; unavailable settlement produces `RESULT UNAVAILABLE`. | Implemented / offline verified | `results.py` verifies exact approved selection, source, excerpt and confirmation. |
| 26 — The system does not query alternate markets by default and tracks API usage against a configurable budget. | Implemented / offline verified | M4 quota estimates, `board_collection.py` budget, and `board_smoke.py` fixed smoke ceiling. |
| 27 — The system distinguishes live evidence from deterministic fixtures and never presents fixture data as live evidence. | Implemented / offline verified | M4 transport classification, M5 source mode, M6 source guard, and M9 grade binding. |
| 28 — The system requires Joseph's explicit `APPROVE`, `REJECT`, or `MODIFY` decision before any official finalization. | Implemented / offline verified | `approval.py` requires a typed interactive Joseph decision and writes its receipt before state. |
| 29 — The system exposes `fifth-pick health` as a mechanical health check. | Implemented / offline verified | `fifth-pick health` and `tests/test_cli.py`. |
| 30 — The system passes all four required mechanical gates before implementation is claimed complete. | Verification | Four mechanical gates reported with the delivery; gate results do not attest live coverage. |
| 31 — The system distinguishes verified current information from uncertainty and discloses missing, outdated, or conflicting evidence rather than treating it as verified. | Implemented / offline verified | Evidence gaps, source freshness/availability checks, and audit disclosures; live routing subject to source decisions. |
| 32 — The system records reasons for important recommendations, exclusions, and stop decisions. | Implemented / offline verified | M7 reason codes and M8 exclusions, rank rationale and stop records; evaluation preserves them. |
| 33 — If a late change removes a candidate, the system does not automatically replace that candidate merely to maintain the previous selection count. | Implemented / offline verified | M8 freezes membership before T-20 removals; no-refill regression retained. |
| 34 — The system follows a bounded execution process: it stops when it reaches a final recommendation, a no-entry decision, or cannot obtain required information, rather than continuing unnecessary tool calls. | Implemented / offline verified | Bounded collection reservations, review cycle, no-entry and stopped-state receipts. |

## Part III authority carried forward

| Decisions | Governing effect |
| --- | --- |
| A1–A6, A17; E4–E5, E8 | Exact direction/category grants take precedence over trust context. Retain Senior priority, foul-trouble treatment, Senior LOWER risk disclosure, and unresolved Malik Monk authorization. |
| A7–A10, A18; E6–E10, E13–E14 | Owner-only exceptions and final approval, material evidence and confidence guards, T-20 and no backfill, bounded review, unchanged slate ceilings and no-entry. See the open override, review and timing decisions below. |
| A11–A15; D1–D5, D7–D9; E1–E3, E11 | Approved board markets and game-line roles, verified identity, source precedence, optional multipliers, compliant access, quota authorization, and fixture/live separation. Research candidates create no approved source route. |
| A16; D6; E12 | Provenance and exact approved-line settlement. Preserve void, push, DNP and unavailable outcomes. No automated player-result retrieval. |
| B–C | Historical research scope and accepted defaults. Neither creates a credential, licenses a source, authorizes an infrastructure provider, nor grants spending. |

## Decisions and verification boundaries

- **LIVE smoke.** The provider documents free event discovery and event-odds billing by markets returned and bookmaker groups. The one-event pilot covers one required discovery recheck and one odds request, up to five credits, zero retries, and 30-minute freshness. Approval must specify the event and slot. A one-platform response is partial coverage. End at Snapshot 1 unless a separately scoped complete validation has already been authorized.
- **Provider identities.** Recover the full preflight output if it is still available, or initialize the next suitable slate through persisted discovery. The event list carries no player labels. Seek provider-supplied roster-linked mappings or equivalent trustworthy evidence for scoped players. Keep verified mappings with source, review, date, team context and a digest, and revalidate on roster or label changes. Unknown and ambiguous labels remain blocked. A coverage-only paid response, if ever separately authorized, cannot promote name matches or count as an accepted observation without qualifying identity evidence.
- **Supporting facts.** The Odds API normal NBA odds source is approved for game environment under D3. To enable a live adapter, approve the region, bookmaker precedence, freshness and budget. Game `h2h` does not provide player H2H. No approved automated player performance/history source exists. An eligible source needs licensed fantasy-analysis access, canonical player/game/team identifiers, completed-game and season coverage, per-game points/rebounds/assists/minutes, correction provenance, stable timestamps, and review of cost and storage terms. PreciseAPI is research-only under D7. NBA statistical endpoints are prohibited. NBA.com schedule/general information, the Official NBA Injury Report, and SI context need compliant access methods and freshness policies. Missing required evidence stays blocked.
- **T-20.** M5 records on-time Snapshot 3 between T−25 and T−20. M7 requires a review timestamp equal to T−20 and cited changing evidence acquired no earlier than T−20. Keep those rules until Joseph decides. The conservative alternative is to keep exact timing and accept that live reviews may stop. The proposed operational alternative keeps the M5 snapshot window, permits a narrowly bounded evidence and review window around T−20 with explicit aging limits, and prohibits review or approval at or after tipoff. All real timestamps remain unchanged. Start with a single event or common-tipoff cohort. A full staggered slate still requires a release and frozen-pool policy for games whose T-20 comes after earlier games start.
- **Owner overrides.** Frozen A7 reserves LOW promotion to Joseph, while accepted M8 MODIFY can only retain a subset of the displayed proposal and current M7 only retains qualified candidates. No agent promotion exists. Decide how a separately receipted human exception interacts with M7, the frozen pool, and the earlier approved MODIFY restriction before adding it. Historical rejected selections have no official M9 settlement or reconstructed counterfactual.
- **Product Reviewer.** The product evidence bundle and exact review status reuse M10 digest and receipt validation. A native product run is unverified. A corrected artifact cannot be treated as the initial receipted proposal. Decide the release workflow for a recreated, receipt-bound corrected proposal, and show original CONCERNS findings to Joseph before any owner exception. Demo approval behavior is preserved and has no mandatory Reviewer dispatch. No new automatic Builder invocation is introduced.
- **Course submission.** Reconcile the PRD's exactly four sections and 4,000-character `AGENTS.md` limit with the current repository file before submission. The roadmap’s M11 closeout also calls for clean-checkout gates, final ADR and assurance/harness evidence, a reproducible demo artifact, a full read-only review, and an intended-files-only repository status. Verify current assignment packaging and professor instructions with the supplied course materials. Preserve acceptance records and M10 qualifications. Submission and publishing remain separate actions.

### Supporting-source decisions

Current terms, endpoint availability, coverage and charges were not reverified.
Fixture parsers do not establish permission to retrieve any LIVE data.

| Need | Candidate route and authority | Reliability, provenance and freshness checks | Cost and alternative |
| --- | --- | --- | --- |
| Game environment | The Odds API NBA sport-level odds, approved in D3. Use region and bookmaker policy only after owner confirmation. | Exact event/team/tipoff and bookmaker binding, opposing spread consistency, a complete total, market update and retrieval timestamps, and payload hash. Keep books separate. | Budget before any request. Current charge unverified. Leave unavailable when the approved route fails. |
| Completed games, per-game stats and actual minutes | No approved player feed. D7 records PreciseAPI as research-only; an appropriately licensed player game-log feed would require separate evaluation and approval. | Require stable player/game/team/season identities, completed-game status, game time and retrieval time, actual minutes and P/R/A, correction semantics, reliable opponent joins, and coverage checks. Define the acceptable age of corrections and refreshes before enabling it. | Current coverage, terms and cost unknown. NBA stats feeds and team scores cannot fill this gap. Remain blocked until a qualifying source is approved. |
| Availability | Official NBA Injury Report first, NBA.com official facts next when the access method is approved, SI as context under A12. | Require applicable report edition, identity, event, status, publication timestamp and actual retrieval timestamp. Same-time official contradictions cannot be silently resolved. Absence from an unavailable report proves nothing. | A compliant documented delivery or licensed access route needs approval. There is no approved fallback to an unofficial feed. |
| Schedule, matchup and context | Board schedule uses the approved Odds API event list. NBA.com schedule/general information and SI reporting are named supporting sources with access methods still unset. | Bind official schedule and roster facts to the event. Attribute editorial context separately. Keep a short excerpt or permitted payload hash, its date, retrieval timestamp, limitations and conflicts. | Current access and fees unverified. Where contextual reporting cannot establish a material fact, retain a named gap. |

## Final personal validation proposal

- **History.** Prefer the BALLDONTLIE NBA ALL-STAR tier as the lowest-cost documented candidate examined that exposes current player-game P/R/A and minutes. Its published NBA price is $9.99 per month. Its terms allow lawful personal analysis and caching subject to the agreement. The prepared parser is offline only. Before activation, authorize the provider and access method, confirm full-season and recent-game completeness, bind stable player/game/team IDs independently, and establish authoritative game timestamps and correction freshness. The stats endpoint's calendar date does not establish an exact start or completion timestamp. Reject incomplete pagination and never infer DNP from absence. Use the Official NBA Injury Report for availability under an approved access method. Published NBA injury PDFs establish that an official source exists; they do not establish automated-use authorization. Derive H2H by exact same-season opponent ID, and use approved Odds API game lines for totals and spread. Role, matchup and contextual facts retain their own evidence authorizations.
- **Board identity.** Prefer a provider-supplied mapping that connects the exact DFS label to a roster-linked identity. If unavailable, ask for independent provider evidence that associates the scoped label with the exact team and player, then have Joseph review it. Shared names, similarity, search hits and roster membership alone cannot establish the binding. The scope file retains evidence references and the collector pins their digest in the receipt-bound policy. Revalidate at team or label changes. No unverified or conflicting bindings enter analysis.
- **Timing proposal (approval required).** Keep Snapshot 3 in the closed interval from T−25 through T−20. Refresh changing supporting evidence at or after T−20. Allow actual T-20 review completion from T−20 through T−15 inclusive, require the source evidence to be available by the actual review time, and leave final approval strictly before tipoff. If the review or evidence misses that window, record T20_CHECK_UNAVAILABLE. The implementation retains the existing exact T-20 rule until Joseph approves and records a timing decision.
- **Staggering proposal (approval required).** Validate one event or a common-tipoff cohort first. Freeze the full-slate ranking and capped pool once, order retained players by that frozen rank, and evaluate each selected event at its own clock. Release one proposed slate only when each retained event has a valid T-20 and the earliest included tipoff still permits review and Joseph's approval. A candidate whose window or approval opportunity is lost is removed, with no refill. Cohort releases spanning multiple decisions would need a separate frozen-pool and receipt policy; do not enable them for the first run.
- **Reviewer.** PASS authorizes presenting the exact receipt-bound proposal for Joseph's decision. First FAIL may authorize one Controller-owned Builder dispatch only from a newly persisted revision attempt. A corrected proposal needs a distinct receipted proposal version tied to that same review cycle, matching the second PASS artifact. Never give an original proposal credit for a correction's PASS. On CONCERNS or second FAIL, stop automated correction and deliver the original findings to Joseph. Part III A18 explicitly permits Joseph to decide after reading CONCERNS. Before enabling this approval route for LIVE selections, preserve the findings and the human exception decision together in the exact proposal's audit. Until that path is implemented the LIVE PASS gate stays closed for escalated proposals.
- **Bounded validation package.** Request approval once for one exact event, three operator-invoked observations on the same pinned run, up to 15 board credits, at most three paid board calls, and zero retries. Each call rechecks the provider's event list without charge. Game lines would need a separate stated maximum under a selected refresh policy; for example, two approved markets in one group on two approved refreshes would reserve up to four more credits. A $9.99 player-history plan, if selected, is a separate subscription decision. No purchase, provider credential transfer or paid request is implicit.

## November 18 implementation reconciliation

The [approved operational amendment](live-operational-amendment.md) supersedes
the earlier proposed timing and staggered-release decisions in this document.
M7 accepts application-clock LIVE review completion through T−15 with the
original changing-evidence freshness guard. M8 waits on unresolved in-window
reviews and excludes expired candidates without refilling. Product review now
verifies the original/corrected proposal lineage and persists escalated
findings for Joseph. The supported correction is removal-only; changes to
evidence or authorization remain outside that command.

PRD criteria 10, 22, and 23 have offline implementation evidence under the
amendment and still require live validation. Criteria 3, 5, 6, 14, and 18
remain partially verified pending real boards, stable identity evidence, and
approved supporting-source activation. The remaining 26 criteria have
offline mechanical or workflow evidence, subject to the qualifications
stated in the matrix. Course acceptance and publishing remain separate.
