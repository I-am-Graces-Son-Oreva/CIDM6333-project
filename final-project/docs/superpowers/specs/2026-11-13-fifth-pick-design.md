# The Fifth Pick — Design Specification

**Status:** DESIGN FREEZE DECISIONS APPROVED — IMPLEMENTATION NOT AUTHORIZED  
**Date:** 2026-11-13  
**Owner:** Joseph Edafiadhe (Governance 0)  
**Purpose:** Define the smallest defensible Fifth Pick MVP. Do not implement until the owner approves this specification.

**Consolidated Update:** Part II, the Consolidated Specification Update, starts at Part II Section 1. Part II supersedes Part I where they conflict. Part I remains for history and for requirements that Part II does not replace. Part III records Joseph's approved resolutions, the authorized research findings, the source decisions, and the design freeze decisions.

## 1. Purpose

The Fifth Pick is a Python CLI system for NBA fantasy Higher/Lower selection.

The system applies the owner's documented selection methodology.

The system enforces decision discipline.

The system does not invent the methodology.

The system does not invent data.

The system does not submit entries.

The research question is:

**Can an agent learn and consistently apply the owner's NBA fantasy-selection methodology while enforcing decision-discipline constraints that reduce over-selection?**

## 2. Glossary

- **Approved player list (allow list):** The owner-controlled list of players and authorized categories and directions. It is the sole candidate universe and exclusion boundary.
- **Authorized category:** A stat category the owner permits for a specific approved player.
- **Authorized direction:** Higher or Lower, as permitted for a specific approved player and category.
- **Projection board:** The current NBA fantasy projections retrieved from the approved fantasy platform.
- **Candidate:** An approved player, an authorized category, an authorized direction, and a current platform line.
- **Eligible candidate:** A candidate that passes the allow-list and category/direction checks.
- **Qualifying candidate:** An eligible candidate that satisfies the owner's methodology.
- **Finalist:** A qualifying candidate that survives the Stop Gate and review.
- **Selection:** A finalist the owner approves for the final recommendation.
- **Ineligible by default:** A player, category, or direction not authorized by the approved player list.
- **Evidence:** Factual information retrieved from an approved source.
- **Receipt:** Machine-readable evidence that a control operated.
- **T-20:** The final review approximately 20 minutes before the relevant game.
- **Small slate:** Superseded by HALF SLATE in Part II Section 5.
- **Large slate:** Superseded by FULL SLATE in Part II Section 5.
- **Stop Gate:** The decision-discipline rules that limit final selections and permit no entry.
- **No entry:** The valid outcome `NO ENTRY RECOMMENDED TODAY.`

## 3. Confirmed Decisions

### D-001 — Source approval and data retrieval are separate responsibilities

**HUMAN APPROVES THE SOURCES. SYSTEM RETRIEVES THE DATA.**

The owner approves each source and its access method.

The system retrieves the data automatically from each approved source.

The normal workflow does not depend on the owner manually supplying projection data.

### D-002 — MVP fantasy platform scope

The MVP uses The Odds API as the approved board source. PrizePicks and Underdog data are retrieved through the `us_dfs` sport key.

Earlier text named Underdog Fantasy and PrizePicks as candidate platforms and left the source unapproved. That earlier status is superseded by Part III E1. Direct access to the platforms remains prohibited.

### D-003 — Legitimate access only

The source adapter must use a legitimate supported access method.

The system must not scrape, bypass controls, or substitute another source without owner approval.

If a legitimate automated access method is unavailable or inappropriate, the system must report the limitation.

The system must not silently fall back to manual entry, scraping, or another source.

### D-004 — T-20 refresh

The system must observe the projection board before the final evaluation.

The system must retrieve or refresh the projection board at T-20.

The system must record the comparison between observed snapshots when the methodology requires it.

### D-005 — Provenance

Every retrieved item must preserve provenance.

Provenance includes the source identifier, retrieval time, source timestamp, access method, raw payload or excerpt, and payload hash.

### D-006 — Approved supporting sources and roles

The owner has approved these sources:

1. **The Odds API** (`us_dfs`) — supplies the projection board for PrizePicks and Underdog. Direct platform access remains prohibited.
2. **NBA.com** — supplies schedules and general player/team information. NBA.com statistical endpoints are not approved for automated fantasy analysis.
3. **Official NBA Injury Report, 2026–27 season** — supplies injury and availability information.
4. **Sports Illustrated NBA** — supplies contextual and editorial NBA information.

The fantasy platform and supporting sources have different roles.

The fantasy platform supplies the projection board.

Supporting sources supply factual, injury, game, player, and contextual evidence required by the methodology.

A supporting source must not be used as a substitute for the projection board.

An unapproved source must not be substituted.

The system must determine a legitimate access method for each approved source.

The system must preserve source-specific provenance.

### D-007 — Approved player list (allow list) and candidate universe

The owner provides a specific list of players and the stat categories and directions permitted for each player.

This is a hard methodological boundary.

**Rule 1:** If a player is not on the approved player list, ignore that player completely, even if the fantasy platform contains a projection for that player.

**Rule 2:** For an approved player, only consider the stat categories and directions the owner explicitly authorizes.

Example: If the owner specifies Mitchell Robinson = lower points, then Mitchell Robinson may only be considered for Lower Points. The system must not consider Higher Points, PRA, assists, rebounds, or another category.

Example: If the owner specifies Jayson Tatum = higher/lower points / PRA, then the system may consider Higher Points, Lower Points, and PRA for Jayson Tatum, subject to the exact category representation agreed with the owner.

**Rule 3:** If an approved player does not appear on the current fantasy board, do not substitute another player. The player may be unavailable, injured, not playing, or not offered by the platform. Absence is acceptable.

**Rule 4:** A small number of qualifying candidates is acceptable. The system must not weaken the methodology or expand the candidate universe merely to fill the slate.

**Rule 5:** Zero qualifying selections remains a valid result.

**Rule 6:** The allow list and permitted-category restrictions must ultimately be enforced deterministically, not merely written as prompt instructions.

Conceptual pipeline:

```
platform projection board
→ approved-player check
→ approved-category/direction check
→ eligibility result
→ methodology evaluation
```

A projection that fails the approved-player or approved-category check must not enter the candidate-evaluation pipeline.

The system must preserve evidence of exclusions where appropriate.

### D-008 — Foul-trouble annotations

The owner uses annotations such as "foul trouble" for some players.

The operational meaning of these annotations is not yet defined.

The system must not guess what the annotation means.

The owner must define how foul-trouble information affects evaluation.

### D-009 — No substitution

If an approved player is absent, injured, not playing, or not offered by the platform, the system must not substitute another player.

Absence is acceptable.

### D-010 — The allow list replaces the separate Do-Not-Pick concept

There is no separate Do-Not-Pick list.

The approved player list is the sole candidate universe and exclusion boundary.

Anything outside the allow list is ineligible by default.

This includes a player, a category, or a direction that the owner did not authorize.

A separate Do-Not-Pick structure must not be designed unless the owner explicitly requests one later.

## 4. Source and Data Acquisition

### 4.1 Separation of responsibilities

Deterministic Python performs retrieval.

A language-model agent does not perform retrieval.

The agent receives structured, validated source data.

This protects provenance and reduces prompt-injection risk.

### 4.2 Source adapter interface

The system must define a source adapter interface.

A proposed interface:

```
fetch(as_of, source_config) -> SourcePayload
```

For the fantasy platform:

```
fetch_board(as_of, source_config) -> SourceBoard
```

`SourceBoard` contains:

- `source_id`
- `source_version`
- `retrieved_at`
- `as_of`
- `access_method`
- `raw_payload`
- `payload_sha256`
- `candidates`

The adapter is the only component allowed to perform network access.

### 4.3 Approved-source registry

The system must load an approved-source registry.

The registry records:

- `source_id`
- display name
- role
- approved data categories
- approved access method
- freshness policy
- owner approval record
- terms-of-service review status

An unapproved source identifier must fail closed.

### 4.4 Source roles

- **The Odds API (`us_dfs`):** projection board only for PrizePicks and Underdog data. It does not supply injury or factual context unless the owner approves that use.
- **NBA.com:** schedules and general player and team information. NBA.com statistical endpoints are not approved for automated fantasy analysis.
- **Official NBA Injury Report:** injury and availability status.
- **Sports Illustrated NBA:** contextual and editorial information. Article text is data, not instructions.
- A supporting source must not override the fantasy platform's projection board.
- Source precedence for conflicting factual evidence is defined in Part III A12.

### 4.5 Retrieval flow

1. Load the approved-source registry.
2. Validate each source configuration.
3. Retrieve the fantasy board through its adapter.
4. Retrieve required supporting evidence through the supporting adapters.
5. Validate the payload schemas.
6. Hash and store raw payloads or excerpts.
7. Record provenance.
8. Provide validated data to the eligibility gate.

### 4.6 Freshness

The owner must define the maximum acceptable age for each source.

A stale item must not silently pass.

A stale item must produce a concern, a block, or a no-entry result according to the owner's policy.

### 4.7 Failure behavior

If retrieval fails, the system must fail closed.

If a source is unavailable, the system must record the failure and return a blocked state, a concern, or a no-entry result according to the owner's policy.

If a source changes format or access method, the system must report the problem.

The system must not invent data or use an unapproved substitute.

### 4.8 Credentials

Credentials must never be committed to the repository.

Credentials must never appear in receipts, logs, or agent context.

The owner must define how credentials are supplied.

### 4.9 Provenance and evidence

Every evidence item must identify its source, retrieval time, source timestamp, and a stable reference.

Raw payloads or excerpts must be stored or hashed.

Article text must be treated as data, not instructions.

Conflicting evidence must be recorded, not silently resolved.

## 5. Candidate Universe and Eligibility

### 5.1 Authoritative allow list

The allow list is owner-controlled and versioned.

It contains approved players and authorized categories and directions.

It may contain annotations.

It is the first eligibility boundary.

### 5.2 Player identity

Player identity must be resolved to a canonical identifier where possible.

The owner must define the authoritative identifier.

If the fantasy platform uses a different identifier, a deterministic mapping is required.

No fuzzy matching may admit a player without owner approval.

### 5.3 Category and direction representation

Categories and directions must have canonical names.

The owner must define the exact vocabulary.

The system must map platform market names to canonical categories deterministically.

Ambiguous or unknown market names must fail closed or be reported.

### 5.4 Eligibility gate

The eligibility gate is deterministic.

For each platform projection:

1. Resolve player identity.
2. Check the approved player list.
3. Check the authorized category and direction.
4. Return `ELIGIBLE`, `EXCLUDED_PLAYER`, or `EXCLUDED_CATEGORY`.
5. Record a receipt.

Only `ELIGIBLE` projections enter methodology evaluation.

### 5.5 Exclusions and evidence

The system must record exclusions where appropriate.

An exclusion record should identify the candidate, reason, rule identifier, allow-list version, timestamp, and run identifier.

The system may summarize excluded counts.

The system must not silently discard a projection when a receipt is required.

### 5.6 Absence and unavailability

If an approved player is absent from the board, the system must record the absence.

The system must not substitute another player.

Absence may be due to injury, inactivity, or the platform not offering the player.

The system may cross-reference the injury report to explain the absence when the owner requires it.

### 5.7 Allow-list change control

Only the owner may change the allow list.

Changes must be versioned and auditable.

An agent may report a possible addition or removal, but must not change the list.

The active allow-list version must be recorded in each run.

## 6. Evaluation Pipeline

The evaluation pipeline is pending the owner's methodology.

Proposed stages:

1. Load the methodology version.
2. Load the allow-list version.
3. Load the approved-source registry.
4. Retrieve the projection board and supporting evidence.
5. Apply the eligibility gate.
6. Evaluate eligible candidates.
7. Apply deterministic controls.
8. Rank candidates.
9. Apply the Stop Gate.
10. Run independent review.
11. Stop for human decision.
12. Finalize the recommendation or return **NO ENTRY RECOMMENDED TODAY.**

The methodology defines qualification, evidence, confidence, ranking, replacement, and rejection.

This specification does not invent those rules.

## 7. Deterministic Controls

The following controls must be enforced by code, not only by prompts:

- Approved-player check.
- Approved-category and direction check.
- Small-slate ceiling of 4.
- Large-slate ceiling of 5.
- Approved-source validation.
- Evidence-presence validation.
- Closed-set reviewer verdict parsing.
- Bounded revision count.
- Human approval before finalization.
- Configuration hashes in the run manifest.
- Receipt writing.

## 8. Human Authority

The owner remains Governance 0.

The owner controls:

- the selection methodology;
- the approved player list;
- approved data sources;
- access methods;
- methodology changes;
- allow-list changes;
- unresolved decisions;
- final real-world decisions.

The system must not submit entries, place wagers, or move money.

## 9. Non-Goals

- No website or GUI.
- No automated wagering or submission.
- No bankroll management.
- No unapproved scraping.
- No invented projections, injuries, lineups, or evidence.
- No invented methodology rules.
- No unapproved source substitution.
- No machine-learning platform.
- No expansion of the candidate universe to fill the slate.
- No separate Do-Not-Pick list. The allow list is the sole exclusion boundary.

## 10. Source Approval Record

This record is incomplete.

| Source | Role | Owner approval | Access method | Data categories | Freshness | Terms review |
|---|---|---|---|---|---|---|
| The Odds API (`us_dfs`) | Projection board for PrizePicks and Underdog | Approved | TBD | Approved markets only | TBD | TBD |
| NBA.com | Schedules and general player/team information | Approved | TBD | No statistical endpoints | TBD | TBD |
| Official NBA Injury Report 2026–27 | Injury and availability | Approved | TBD | TBD | TBD | TBD |
| Sports Illustrated NBA | Context and editorial | Approved | TBD | TBD | TBD | TBD |

## 11. Allow-List Approval Record

This record is incomplete.

| Field | Value |
|---|---|
| Owner | Joseph Edafiadhe |
| Approval date | TBD |
| Version | TBD |
| Delivery format | TBD |
| Authoritative player identifier | TBD |
| Canonical categories | TBD |
| Direction vocabulary | TBD |
| Annotation vocabulary | TBD |
| Effective dates | TBD |
| Change record | TBD |

## 12. Open Questions

### 12.1 Allow list and categories

1. How will the owner provide the list?
2. Which player identifier is authoritative?
3. Which canonical stat categories are allowed?
4. What does PRA mean?
5. Does PRA require an explicit direction?
6. Are directions specified per category?
7. How are annotations represented?
8. Is the list season-long, per-slate, or both?
9. How often may the list change?
10. How are trades and name changes handled?
11. How are multiple lines for one category handled?
12. Can one player occupy multiple selection slots?
13. Can a player be authorized for both Higher and Lower in the same category?
14. What happens when an authorized category is not offered?
15. What happens when an approved player is absent?
16. Should the system report excluded board players?
17. Should the eligibility gate record both the player check and the category/direction check even when the player check already excludes the projection?
18. Are there annotations other than foul trouble?

### 12.2 Foul trouble

1. What does foul trouble mean operationally?
2. Which indicators are used?
3. Is it a hard filter, a signal, or a tie-breaker?
4. What thresholds apply?
5. Which source supplies the data?
6. Does it apply to all categories or specific categories?
7. Does it apply to all players or only annotated players?
8. What happens when foul-trouble data is missing?

### 12.3 Supporting sources

**Resolved by Part III D/E:** The Odds API (`us_dfs`) is the approved board source; NBA.com is limited to schedules and general player/team information; NBA.com statistical endpoints are not approved for automated fantasy analysis. The questions below are retained as historical context.

1. Which NBA.com data categories are approved?
2. Which injury-report statuses matter?
3. What is Sports Illustrated NBA used for?
4. What is the source precedence when sources conflict?
5. What are the approved access methods?
6. What freshness is required for each source?
7. What excerpts must be retained?
8. How is prompt injection from source text handled?

### 12.4 Projection changes

1. Which changes matter?
2. Which snapshot is the baseline?
3. What movement is material?
4. Is movement toward the authorized direction confirmation or irrelevant?
5. Is movement against the authorized direction a removal trigger?
6. What happens if the line moves after finalization?

### 12.5 T-20

1. What exactly is checked at T-20?
2. Which sources are refreshed?
3. In what order?
4. How are Questionable, Doubtful, Probable, and Available handled?
5. What happens if a player is not listed on the injury report?
6. What happens if a late scratch occurs after T-20?
7. What is the finalization cutoff?
8. Is explicit human approval required at T-20?
9. What happens if the owner is unavailable at T-20?

## 13. Approval

Part III A–E record Joseph's approved decisions and design freeze. This specification is the approved design basis to the extent reconciled with Part III.

Implementation is still not authorized. No implementation may begin until Joseph explicitly authorizes it.

---

# Part II — Consolidated Specification Update

**Status:** DRAFT — NOT APPROVED  
**Owner:** Joseph (Governance Zero)  
**Date:** 2026-11-13  
**Implementation status:** None. No code, tests, configuration, or runtime artifacts have been created.  
**Approval:** Joseph must approve this specification before planning or implementation.

## Part II Requirement Language

- **MUST** and **MUST NOT** state mandatory requirements.
- **SHOULD** states a strong requirement that needs a recorded reason to omit.
- **MAY** states a permitted option.
- **TELL** means an instruction to an agent.
- **ENFORCE** means a mechanical control that the agent cannot simply ignore.
- A prompt is not enforcement.

## Part II Glossary

- **Governance Zero:** Joseph. Joseph owns the methodology and makes every final decision.
- **Approved Candidate Universe (allow list):** Joseph's authoritative list of players and authorized categories and directions. It is the sole candidate universe and exclusion boundary.
- **Authorized player:** A player in the approved candidate universe.
- **Authorized category:** A stat category Joseph permits for a specific authorized player.
- **Authorized direction:** Higher or Lower, as permitted for a specific authorized player and category.
- **Projection board:** The current NBA fantasy projections retrieved from the approved fantasy platform.
- **Candidate:** An authorized player, an authorized category, an authorized direction, and a current platform line.
- **Eligible candidate:** A candidate that passes the player, category, and direction authorization checks.
- **Qualifying candidate:** An eligible candidate that satisfies Joseph's methodology.
- **Finalist:** A qualifying candidate that survives the Stop Gate and T-20 review.
- **Selection:** A finalist Joseph approves for the final recommendation.
- **Trust tier:** A Joseph-approved classification used only as evaluation context. It does not add a category to the authorized universe; see Part III E4.
- **Senior:** A player on Joseph's Senior list. Senior status is a real priority tier.
- **Foul-trouble annotation:** A Joseph annotation that a player can commit early fouls and lose meaningful playing time. It is not a deterministic block.
- **Projection snapshot:** A timestamped observation of a platform projection.
- **T-20:** The final review approximately 20 minutes before the relevant game. Snapshot 3 is the T-20 snapshot.
- **HALF SLATE:** A slate with 1–4 NBA games. Maximum final selections is 4.
- **FULL SLATE:** A slate with 5 or more NBA games. Maximum final selections is 5.
- **Stop Gate:** The decision-discipline rules that limit final selections and permit no entry.
- **No entry:** The exact valid output `NO ENTRY RECOMMENDED TODAY.`
- **Receipt:** Machine-readable evidence that a control operated or an observable event occurred.
- **Ineligible by default:** A player, category, or direction not authorized by the approved candidate universe.

## Part II Preserved Earlier Requirements

The following earlier requirements remain in force:

- Joseph is Governance Zero and makes every final decision.
- The system does not submit entries, place wagers, log into accounts, or move money.
- The human approves the sources. The system retrieves the data.
- The normal workflow does not depend on manual projection entry.
- Deterministic Python performs retrieval. Language-model agents do not browse or fetch source data.
- Approved supporting sources are NBA.com for schedules and general information, the Official NBA Injury Report 2026–27, and Sports Illustrated NBA. NBA.com statistical endpoints are not approved for automated fantasy analysis.
- The Odds API (`us_dfs`) is the approved MVP board source for PrizePicks and Underdog. The earlier “not yet approved” status is superseded by Part III E1.
- Automated retrieval must use a legitimate supported access method. No scraping, bypassing controls, or silent substitution.
- Provenance must be recorded: source ID, retrieval time, source timestamp, access method, raw payload or excerpt, and payload hash.
- The T-20 review refreshes current projection, availability, role, and relevant conditions.
- A candidate identified earlier must survive T-20 to remain final.
- The system must not weaken the methodology or expand the candidate universe to fill a slate.
- Fewer selections are valid. Zero selections are valid.
- The exact no-entry output is `NO ENTRY RECOMMENDED TODAY.`
- The project is a Python CLI. It is not a website or GUI.
- The toolchain is `uv`, `ruff`, `ty`, and Python `unittest`. Do not use pytest for the final system.
- The four mechanical gates are:
  - `uv run ruff check`
  - `uv run ruff format --check`
  - `uv run ty check`
  - `uv run python -m unittest discover -s tests`
- All four gates must exit `0`.
- At least one gate must be shown to fail before the gates are claimed as evidence.
- Standard Technical English applies to agent-facing documents.
- Superpowers discipline applies to development.
- Historical Evolution evidence remains historical. Do not rewrite Evolutions 00–08.
- Existing project context includes `evolution-00/pitch.md`, `docs/PRD.md`, `evolution-00/choices.md`, and `design-analyses/LEDGER.md`.

## Part II Section 1 — Project Identity

Project name:

**The Fifth Pick — An NBA Fantasy Selection & Discipline Experiment**

Primary research question:

> Can an agent learn and consistently apply Joseph's NBA fantasy-selection methodology while enforcing decision-discipline constraints that reduce over-selection?

This is not primarily a project about predicting basketball better than everyone else.

It is an agentic systems project. It studies whether an agent can:

- consistently apply a human-defined methodology;
- stay inside deterministic constraints;
- retrieve and evaluate evidence;
- avoid over-selection;
- explain recommendations;
- submit its work to independent review;
- preserve receipts and evidence;
- return final authority to the human.

Joseph is the author and owner of the selection methodology.

The agent must never invent its own methodology and present it as Joseph's.

## Part II Section 2 — Course and Harness Constraints

The project must follow the CIDM 6333 Final System architecture. It must not become a normal website or an ordinary AI application.

This project is a CLI tool.

Do not turn it into a website.

Use Python for project logic.

Use the Astral toolchain:

```text
uv
ruff
ty
```

Use the Python standard library `unittest`.

Do not use pytest for this final system.

The mechanical definition of healthy and done must include these four gates:

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

All four must exit `0`.

The project must demonstrate that at least one gate can fail before claiming the gates provide evidence.

The harness should demonstrate:

```text
AGENTS.md
permissions
skills
agent personas
multi-agent control
hooks
receipts
typed results
mechanical gates
human authority
assurance evidence
```

The central conceptual distinction is:

```text
TELL != ENFORCE
```

AGENTS.md, skills, and persona instructions can tell an agent what to do.

Python validators, OpenCode permissions, hooks, typed parsers, tests, and other harness mechanisms should enforce rules that must not be violated.

## Part II Section 3 — Governance Zero

Joseph must exist at both the beginning and the end of the system.

The intended authority loop is:

```text
JOSEPH
   ↓
CONTROLLER
   ↓
PLANNER
   ↓
BUILDER
   ↓
REVIEWER
   ↓
CONTROLLER
   ↓
JOSEPH
```

Joseph is Governance Zero.

At the beginning, Joseph defines and approves:

- methodology;
- candidate universe;
- player, category, and direction authorization;
- trust tiers;
- Senior designation;
- approved data sources;
- selection ceilings;
- confidence rules;
- risk philosophy;
- methodology changes.

The harness then executes inside those boundaries.

At the end, the recommendation returns to Joseph.

The system must never transform its own recommendation into Joseph's official final slate automatically.

Joseph may:

```text
APPROVE
REJECT
MODIFY
```

the recommendation.

Joseph's decision is final.

## Part II Section 4 — No Automatic Entry or Wager Execution

The Fifth Pick is an analysis and recommendation system.

It must not:

```text
log into Joseph's fantasy account
submit entries
deposit money
move money
connect to banking
automatically place a wager or fantasy entry
```

The final product is a recommendation for Joseph's review.

## Part II Section 5 — Slate-Size Discipline

Slate classification is determined by the number of NBA games scheduled that day.

```text
1–4 NBA games = HALF SLATE
maximum final selections = 4

5+ NBA games = FULL SLATE
maximum final selections = 5
```

These are ceilings, not targets.

The agent does not need to produce four or five selections.

Examples:

```text
Full slate + 3 strong candidates = recommend 3.
Full slate + 1 strong candidate = recommend 1.
Full slate + 0 strong candidates = recommend 0.
```

The system must never manufacture selections merely to fill empty slots.

When nothing meets the required standard, the exact output is:

```text
NO ENTRY RECOMMENDED TODAY.
```

## Part II Section 6 — One Player Equals One Final Slot

A player can occupy only one final selection slot.

If the same player has several authorized categories that qualify strongly, the agent may choose the single strongest category for that player.

Example:

```text
Nikola Jokic Points
Nikola Jokic PRA
Nikola Jokic Assists
```

These cannot occupy three final slots.

The agent chooses the strongest authorized candidate for Jokic and uses only that one final slot.

## Part II Section 7 — Approved Candidate Universe and No Do-Not-Pick List

There is no separate Do-Not-Pick list.

The system uses an Approved Candidate Universe.

The rule is:

> The agent does not decide who enters its universe. Joseph does.

The universe controls:

```text
Player
Category
Direction
```

A fantasy-board entry is eligible only when all applicable authorization checks pass.

Conceptually:

```text
PLAYER AUTHORIZED?
        ↓
CATEGORY AUTHORIZED?
        ↓
DIRECTION AUTHORIZED?
        ↓
ELIGIBLE FOR ANALYSIS
```

Players outside the universe must be deterministically blocked.

A player being famous, statistically attractive, popular, or present on the fantasy platform does not authorize that player.

Anything outside the allow list is ineligible by default.

A separate Do-Not-Pick structure must not be designed unless Joseph explicitly requests one later.

## Part II Section 8 — Persistent Universe, Not a Daily List

The approved player list is the overall universe.

Joseph should not have to construct a new list every day.

Daily workflow:

```text
Fantasy board retrieved automatically
        ↓
Board compared with approved universe
        ↓
Unauthorized entries blocked
        ↓
Eligible entries continue to analysis
```

An approved player who does not appear on today's board simply produces no candidate.

The system must not substitute an unauthorized player because an approved player is unavailable.

Having only a few eligible candidates is acceptable.

Having zero eligible candidates is acceptable.

## Part II Section 9 — Approved Universe — Current Authoritative Input

### Part II 9.1 — Explicit Universe

The following is Joseph's currently approved universe, subject to normalization. Trust-tier classification does not add authorization; see Part III E4.

Malik Monk remains in the registry but has no approved category or direction. He is unselectable until Joseph defines both. This supersedes the earlier statement that he was explicitly removed.

Do not infer an unspecified direction merely to complete configuration. If a direction remains genuinely ambiguous after applying the explicit universe and Part III A1–A2, identify it as an unresolved configuration item rather than guessing.

```text
Jayson Tatum = higher/lower points / PRA
Derrick White = higher/lower points
Payton Pritchard = higher/lower points
Paul George = higher/lower points
Mitchell Robinson = lower points
Michael Porter Jr. = higher/lower points / PRA
Julius Randle = higher/lower points / PRA
Miles McBride = higher/lower points
Josh Hart = higher/lower points
Dalton Knecht = higher/lower points
OG Anunoby = higher/lower points
Jalen Brunson = higher/lower points
Mikal Bridges = higher/lower points
Karl-Anthony Towns = higher/lower points / PRA / foul trouble
Tyrese Maxey = higher/lower points
Anfernee Simons = higher/lower points
Jaylen Brown = higher/lower points / PRA
Joel Embiid = higher/lower points
LeBron James = higher/lower points / rebounds+assists
VJ Edgecombe = higher/lower points
Kawhi Leonard = higher/lower points
Scottie Barnes = higher/lower points / PRA / foul trouble
Immanuel Quickley = higher/lower points
RJ Barrett = higher/lower points
Josh Giddey = higher/lower points / PRA
Caleb Wilson = higher/lower points
Matas Buzelis = higher/lower points
Norman Powell = higher/lower points
James Harden = higher/lower points
Evan Mobley = higher/lower points / rebounds
Peyton Watson = higher/lower points
Jarrett Allen = higher/lower points / foul trouble
Donovan Mitchell = higher/lower points / PRA
Jalen Duren = higher/lower points / PRA / foul trouble
Cade Cunningham = higher/lower points / foul trouble
Ausar Thompson = higher/lower points
Taurean Prince = higher/lower points
Tyrese Haliburton = lower points / assists higher/lower
Obi Toppin = higher/lower points
Andrew Nembhard = assists / PRA
Ivica Zubac = points / rebounds / foul trouble
Pascal Siakam = higher/lower points
Tyler Herro = higher/lower points / foul trouble
Kyle Kuzma = higher/lower points
Jaime Jaquez Jr. = higher/lower points / foul trouble
Ryan Rollins = higher/lower points
Kel'el Ware = points / rebounds
Myles Turner = higher/lower points
Jalen Johnson = higher/lower points / PRA / foul trouble
CJ McCollum = higher/lower points
Kingston Flemings = higher/lower points
Dyson Daniels = points lower / assists higher/lower
Nickeil Alexander-Walker = higher/lower points
Onyeka Okongwu = higher/lower points
Naz Reid = higher/lower points / 3-point attempts / foul trouble
Coby White = higher/lower points
Kon Knueppel = higher/lower points
Grayson Allen = higher/lower points / 3-point attempts
Dennis Schroder = higher/lower points / foul trouble
Brandon Miller = higher/lower points / foul trouble
Giannis Antetokounmpo = higher/lower points / PRA
Tim Hardaway Jr. = higher/lower points
Klay Thompson = higher/lower points
Bam Adebayo = higher/lower points / rebounds higher/lower
Andrew Wiggins = higher/lower points
Bobby Portis Jr. = higher/lower points
Anthony Black = higher/lower points / PRA / foul trouble
Desmond Bane = higher/lower points / foul trouble
Jalen Suggs = higher/lower points
Paolo Banchero = higher/lower points
Franz Wagner = higher/lower points
Tristan da Silva = higher/lower points
Wendell Carter Jr. = PRA
Trae Young = higher/lower points / PRA
AJ Dybantsa = higher/lower points
Alex Sarr = higher/lower points / foul trouble
Anthony Davis = higher/lower points / PRA / foul trouble
DeMar DeRozan = higher/lower points
Nikola Jokic = higher/lower points / assists / rebounds / PRA
Cameron Johnson = higher/lower points
Jamal Murray = higher/lower points / PRA
Aaron Gordon = higher/lower points
LaMelo Ball = higher/lower points / assists / foul trouble
Jaden McDaniels = higher/lower points
Anthony Edwards = higher/lower points
Ayo Dosunmu = higher/lower points
Jonathan Kuminga = higher/lower points
Rudy Gobert = lower points / rebounds higher / foul trouble
Shai Gilgeous-Alexander = higher/lower points
Chet Holmgren = higher/lower points / foul trouble
Isaiah Hartenstein = points lower
Aday Mara = points lower
Damian Lillard = higher/lower points
Scoot Henderson = points lower
Ja Morant = higher/lower points / foul trouble
Jrue Holiday = higher/lower points
Deni Avdija = higher/lower points / PRA
Toumani Camara = higher/lower points / PRA
Donovan Clingan = rebounds higher/lower / points lower
Keyonte George = higher/lower points / assists / PRA / foul trouble
Ace Bailey = higher/lower points
Jaren Jackson Jr. = higher/lower points / foul trouble
Darryn Peterson = higher/lower points
Lauri Markkanen = higher/lower points
Yaxel Lendeborg = higher/lower points / PRA
Brandin Podziemski = PRA lower
Jimmy Butler III = higher/lower points
Draymond Green = points lower / foul trouble
Stephen Curry = higher/lower points
Keaton Wagler = higher/lower points
Brandon Ingram = higher/lower points
Darius Garland = higher/lower points
Rui Hachimura = higher/lower PRA
Collin Sexton = higher/lower PRA
Walker Kessler = lower points
Austin Reaves = higher/lower points / PRA
Luka Doncic = higher/lower points / assists / rebounds / PRA
Dillon Brooks = lower PRA
Jalen Green = lower PRA
Collin Gillespie = lower PRA
Devin Booker = higher/lower points
Miles Bridges = higher/lower points / PRA
Darius Acuff Jr. = higher/lower points
Zach LaVine = higher/lower points
Domantas Sabonis = higher/lower PRA / foul trouble
Keegan Murray = higher/lower PRA
Kyrie Irving = higher/lower points
PJ Washington = higher/lower points
Cooper Flagg = higher/lower points / PRA
Amen Thompson = higher/lower points / PRA
Fred VanVleet = lower PRA
Kevin Durant = higher/lower points / PRA
Jabari Smith Jr. = higher/lower points / PRA
Reed Sheppard = lower PRA
Alperen Sengun = higher/lower points / PRA / foul trouble
Marcus Smart = lower points
Ty Jerome = higher/lower points
Jerami Grant = lower points / PRA
Zach Edey = points lower
Cameron Boozer = higher/lower points / PRA
Jeremiah Fears = higher/lower points
Zion Williamson = higher/lower points / foul trouble
Jordan Poole = points lower / foul trouble
Derik Queen = higher/lower points
Trey Murphy III = higher/lower points
Saddiq Bey = higher/lower points
Victor Wembanyama = higher/lower points / PRA
Dylan Harper = higher/lower points
Keldon Johnson = lower points
De'Aaron Fox = lower points / PRA
Stephon Castle = higher/lower points / assists / PRA
Luke Kornet = rebounds higher/lower
Devin Vassell = higher/lower points
Julian Champagnie = higher/lower points
Harrison Barnes = lower points
```

### Part II 9.2 — Historical Derived Trust-Tier Additions — Not Authorization

**Superseded by Part III E4.** The following categories were derived under the earlier trust-tier rule. They are not part of the effective universe unless Joseph explicitly includes them in the approved universe. Retained as historical context; do not treat these entries as eligible.

**PRA Trust additions:**

- Paolo Banchero: PRA, Higher and Lower.
- Bam Adebayo: PRA, Higher and Lower.

**Assist Trust additions:**

- Cade Cunningham: ASSISTS, Higher and Lower.
- Jalen Johnson: ASSISTS, Higher and Lower.
- Giannis Antetokounmpo: ASSISTS, Higher and Lower.
- Trae Young: ASSISTS, Higher and Lower.
- Jamal Murray: ASSISTS, Higher and Lower.
- Isaiah Hartenstein: ASSISTS, Higher and Lower.
- Austin Reaves: ASSISTS, Higher and Lower.
- Alperen Sengun: ASSISTS, Higher and Lower.
- Kevin Durant: ASSISTS, Higher and Lower.
- James Harden: ASSISTS, Higher and Lower.
- LeBron James: ASSISTS, Higher and Lower.

**Rebound Trust additions:**

- Victor Wembanyama: REBOUNDS, Higher and Lower.
- Cameron Boozer: REBOUNDS, Higher and Lower.
- Alperen Sengun: REBOUNDS, Higher and Lower.
- Kevin Durant: REBOUNDS, Higher and Lower.
- Domantas Sabonis: REBOUNDS, Higher and Lower.
- Walker Kessler: REBOUNDS, Higher and Lower.
- Chet Holmgren: REBOUNDS, Higher and Lower.
- Isaiah Hartenstein: REBOUNDS, Higher and Lower.
- Aday Mara: REBOUNDS, Higher and Lower.
- Alex Sarr: REBOUNDS, Higher and Lower.
- Anthony Davis: REBOUNDS, Higher and Lower.
- Giannis Antetokounmpo: REBOUNDS, Higher and Lower.
- Naz Reid: REBOUNDS, Higher and Lower.
- Jalen Duren: REBOUNDS, Higher and Lower.
- Jarrett Allen: REBOUNDS, Higher and Lower.
- Scottie Barnes: REBOUNDS, Higher and Lower.
- Joel Embiid: REBOUNDS, Higher and Lower.
- Karl-Anthony Towns: REBOUNDS, Higher and Lower.
- Julius Randle: REBOUNDS, Higher and Lower.

### Part II 9.3 — Direction Ambiguities Requiring Joseph

**Resolved by Part III A1–A3.** The text below is retained as historical context and must be read subject to Part III.

Joseph explicitly instructed that an unspecified direction must not be inferred. The following ambiguities remain after applying the explicit universe and Part III A1–A2; trust tiers do not add authorization under Part III E4.

**Systematic shorthand ambiguity:**

Many entries use a direction word or words before the first category and omit them before later categories. Examples:

```text
higher/lower points / PRA
lower points / PRA
higher/lower points / assists / rebounds / PRA
higher/lower points / assists / PRA
higher/lower points / rebounds
higher/lower points / 3-point attempts
higher/lower points / rebounds+assists
```

Question: Does the direction word or words apply to every listed category, or only to the first category?

**Individual entries with no direction and no shorthand:**

- Andrew Nembhard: ASSISTS and PRA.
- Ivica Zubac: POINTS and REBOUNDS.
- Kel'el Ware: POINTS and REBOUNDS.
- Wendell Carter Jr.: PRA.
- Naz Reid: THREE_POINT_ATTEMPTS.
- Grayson Allen: THREE_POINT_ATTEMPTS.
- LeBron James: REBOUNDS_ASSISTS.
- Evan Mobley: REBOUNDS, if the shorthand does not apply.
- Jerami Grant: PRA, if the shorthand does not apply.
- De'Aaron Fox: PRA, if the shorthand does not apply.
- Keyonte George: ASSISTS and PRA, if the shorthand does not apply.
- Stephon Castle: ASSISTS and PRA, if the shorthand does not apply.
- LaMelo Ball: ASSISTS, if the shorthand does not apply.
- Nikola Jokic: ASSISTS, REBOUNDS, and PRA, if the shorthand does not apply.
- Luka Doncic: ASSISTS, REBOUNDS, and PRA, if the shorthand does not apply.

**Trust-tier direction ambiguity:**

Several players are in a trust list and also have that category explicitly listed without a direction. This historical ambiguity is resolved by Part III E4 and A2: trust-tier membership does not authorize the category, and an explicitly listed category with no explicit direction receives Higher and Lower under A2. Examples include Jayson Tatum PRA, Karl-Anthony Towns PRA, Scottie Barnes PRA, Giannis Antetokounmpo PRA, Anthony Davis PRA, Jamal Murray PRA, Deni Avdija PRA, Yaxel Lendeborg PRA, Austin Reaves PRA, Amen Thompson PRA, Kevin Durant PRA, Alperen Sengun PRA, Victor Wembanyama PRA, Nikola Jokic ASSISTS and REBOUNDS and PRA, Luka Doncic ASSISTS and REBOUNDS and PRA, LaMelo Ball ASSISTS, Keyonte George ASSISTS and PRA, Stephon Castle ASSISTS and PRA, Andrew Nembhard ASSISTS, and Kel'el Ware REBOUNDS.

## Part II Section 10 — Player Identity

Use a stable fantasy-platform player identifier when the selected platform provides one.

Also maintain Joseph's canonical player name.

The system must normalize name variants such as:

```text
Luka Doncic
Luka Dončić
```

to the same player identity when that identity is verifiably the same.

Do not rely only on display-name spelling when a stable platform identifier exists.

A player's authorization follows the player, not the player's team.

## Part II Section 11 — Category Normalization

Normalize platform-specific labels into an internal canonical vocabulary.

Initial canonical categories include:

```text
POINTS
REBOUNDS
ASSISTS
PRA
REBOUNDS_ASSISTS
THREE_POINT_ATTEMPTS
```

`THREE_POINT_ATTEMPTS` remains in the canonical vocabulary and in Joseph's methodology, but is outside the live MVP under Part III E1. The live MVP must not substitute threes made or fabricate attempts.

PRA means:

```text
Points + Rebounds + Assists
```

Platform labels may differ, but normalization must not create additional authorization.

Example: If the platform offers Luka steals, recognizing Luka's identity does not authorize steals.

Authorization remains:

```text
PLAYER + CATEGORY + DIRECTION
```

## Part II Section 12 — Trust-Tier Categories Do Not Authorize (Superseded by Part III E4)

This section is retained for historical context. Joseph's earlier rule allowed trust-list membership to add a category to a player's authorized universe. **Part III E4 supersedes that rule.**

Current rule:

```text
Trust classification → evaluation context only.
Trust classification does NOT authorize a category.
Category eligibility requires explicit inclusion in Joseph's approved universe.
```

The trust lists below are classification records. They do not make a player eligible for the listed category, do not add Higher or Lower, and do not override the approved universe. Direction rules apply only after the category is explicitly authorized: use A1, A2, or an explicit category-specific direction.

### Part II 12.1 — PRA Trust

Current PRA Trust players:

```text
Luka Doncic
Nikola Jokic
Kevin Durant
Domantas Sabonis
Alperen Sengun
Austin Reaves
Victor Wembanyama
Amen Thompson
Yaxel Lendeborg
Deni Avdija
Jamal Murray
Anthony Davis
Paolo Banchero
Giannis Antetokounmpo
Bam Adebayo
Scottie Barnes
Karl-Anthony Towns
Jayson Tatum
```

PRA Trust means elevated trust and consideration in PRA. It does not mean automatic selection.

### Part II 12.2 — Assist Trust

Current Assist Trust players:

```text
Cade Cunningham
Andrew Nembhard
Jalen Johnson
Dyson Daniels
Giannis Antetokounmpo
Trae Young
Nikola Jokic
Jamal Murray
LaMelo Ball
Isaiah Hartenstein
Keyonte George
Austin Reaves
Luka Doncic
Alperen Sengun
Kevin Durant
Stephon Castle
Tyrese Haliburton
James Harden
LeBron James
```

Assist Trust means elevated trust and consideration in assists. It does not mean automatic selection.

### Part II 12.3 — Rebound Trust

Current Rebound Trust players:

```text
Victor Wembanyama
Luke Kornet
Cameron Boozer
Alperen Sengun
Kevin Durant
Domantas Sabonis
Luka Doncic
Walker Kessler
Donovan Clingan
Chet Holmgren
Isaiah Hartenstein
Aday Mara
Rudy Gobert
Nikola Jokic
Alex Sarr
Anthony Davis
Bam Adebayo
Giannis Antetokounmpo
Naz Reid
Kel'el Ware
Jalen Duren
Jarrett Allen
Scottie Barnes
Joel Embiid
Karl-Anthony Towns
Julius Randle
```

Rebound Trust does not mean automatic Higher.

Rebounding is strongly opponent-dependent.

The system should heavily consider the opposing team's size, rebound environment, lineup, and matchup.

Example principle: Playing against a player such as Wembanyama can materially change the rebound environment.

## Part II Section 13 — Senior Players

The following players are Senior:

```text
Luka Doncic
Victor Wembanyama
Nikola Jokic
Stephen Curry
Jayson Tatum
Devin Booker
Jalen Brunson
Tyrese Maxey
Joel Embiid
Kawhi Leonard
Donovan Mitchell
Kevin Durant
Giannis Antetokounmpo
Anthony Davis
Anthony Edwards
Shai Gilgeous-Alexander
Damian Lillard
Deni Avdija
```

Senior status is a real priority tier.

It is not a tiny confidence bonus.

For authorized scoring props, Joseph's first instinct with Senior players is strongly Higher.

Senior players are viewed as players capable of explosive scoring performances.

A Senior Higher candidate that qualifies should generally receive priority over an ordinary non-Senior candidate.

Do not casually demote a strong Senior candidate beneath a regular player merely because the regular player's evidence looks slightly cleaner.

Among multiple qualifying Senior candidates, the overall evidence can still determine ordering.

## Part II Section 14 — Senior Lower Philosophy

Choosing Lower on a Senior player is considered substantially riskier under Joseph's methodology.

One of the most important reasons to consider Senior Lower is:

```text
BLOWOUT / REDUCED MINUTES RISK
```

The concern is that the Senior player might not play much of the fourth quarter.

If a Senior misses a line because a blowout reduced playing time, Joseph considers that differently from the player simply being incapable of producing.

The agent must surface this context.

## Part II Section 15 — Senior Projection-Movement Heuristic

For Senior players:

A continuously rising projection does not automatically scare Joseph away from Higher.

Joseph's instinct remains approximately:

```text
~80% lean Higher
```

because these players can produce huge performances.

This 80 percent is a heuristic, not a calibrated probability or historical hit-rate claim.

A continuously falling projection is more concerning.

Joseph's confidence may become approximately:

```text
50 / 50
```

and the agent should become skeptical and investigate why the line is falling.

This 50/50 is also a heuristic, not a calibrated probability.

A falling line can look attractive while still ending with the player finishing narrowly below it.

The system should therefore investigate movement rather than blindly treating a cheaper Senior line as better.

## Part II Section 16 — PRA Trust

See Part II 12.1 for the current PRA Trust list.

PRA Trust means elevated trust and consideration in PRA after the player and category pass authorization.

It does not mean automatic selection, and it does not authorize PRA by itself; see Part III E4.

## Part II Section 17 — Assist Trust

See Part II 12.2 for the current Assist Trust list.

Assist Trust means elevated trust and consideration in assists after authorization.

It does not mean automatic selection, and it does not authorize ASSISTS by itself; see Part III E4.

## Part II Section 18 — Rebound Trust

See Part II 12.3 for the current Rebound Trust list.

Rebound Trust does not mean automatic Higher and does not authorize REBOUNDS by itself; see Part III E4.

Rebounding is strongly opponent-dependent.

The system should heavily consider the opposing team's size, rebound environment, lineup, and matchup.

## Part II Section 19 — Non-Senior / Showoff Heuristic

For non-Senior scoring players, Joseph metaphorically describes them as showoffs.

Operational meaning:

Joseph's general bias on ordinary non-Senior scoring props is toward Lower, especially as the projection rises.

A rising non-Senior scoring projection can increase skepticism.

Higher can still qualify when evidence justifies it, especially when:

```text
starters are absent
Senior players are absent
usage increases
minutes increase
role materially improves
```

This is a methodology bias, not a deterministic block.

Do not apply the showoff scoring heuristic incorrectly to trusted:

```text
PRA
ASSISTS
REBOUNDS
```

markets.

Category-specific trust is a separate concept.

## Part II Section 20 — Foul-Trouble Annotation

`foul_trouble=true` does not disqualify a player.

It means Joseph has observed that the player can commit early fouls and lose meaningful playing time.

The system should therefore:

```text
apply additional skepticism
look for foul-related context and evidence
surface the risk clearly
allow the candidate to qualify if otherwise strong
return the risk to Joseph
```

Joseph decides whether to accept that risk.

Foul trouble is not a deterministic block.

## Part II Section 21 — Matchup Analysis

The agent should investigate the specific fixture.

Relevant contextual factors include:

```text
team offensive strength
opponent defensive strength
best offense vs strong defense
best offense vs weak defense
general matchup quality
player role
player availability
teammate absences
opponent absences
expected minutes
game environment
potential blowout
```

Teams can have important characteristics that change player evaluation.

Joseph previously gave examples such as:

```text
Oklahoma City
San Antonio
Houston
Los Angeles Lakers
```

These are examples, not hard-coded team rules.

The agent must retrieve current evidence rather than rely on stereotypes about a team's historical identity.

## Part II Section 22 — High-Scoring Game Environment

The agent should always investigate whether the game is projected to have a high combined score.

A high projected game total can strengthen the attractiveness of a Higher candidate.

This is not deterministic.

Example:

```text
High scoring + competitive game
→ potentially strong environment for Higher

High scoring + large mismatch
→ scoring may be strong but blowout/minutes risk may increase
```

Combine game total with the rest of Joseph's methodology.

## Part II Section 23 — Game Spread / Blowout Signal

The system is authorized to retrieve legitimate point-spread information.

The spread is supporting evidence for:

```text
potential blowout
fourth-quarter minutes risk
game competitiveness
```

It is not an automatic Higher/Lower rule.

The system must combine the spread with actual team and player context.

## Part II Section 24 — Last-8 Analysis

For serious candidates, inspect the player's last 8 games.

Look for performance relative to the relevant projection and for observable sequences and patterns.

Examples include:

```text
2 over / 2 under / 2 over / 2 under
5 over / 1 under
streaks
clusters
repeated swings
```

Do not invent a pattern when one is not present.

Do not treat a pattern as deterministic prediction.

It is supporting evidence.

Counting and numerical summaries should be performed with deterministic code rather than trusting an LLM to count manually.

## Part II Section 25 — Same-Season Head-to-Head

Head-to-head evidence should prioritize previous meetings against today's opponent during the current NBA season.

This is important because rosters and roles can change from season to season.

Do not automatically treat last season's matchup history as equivalent evidence.

If older head-to-head data is inspected, the system must first consider whether the comparison remains meaningful given:

```text
roster changes
trades
coaching changes
role changes
injuries
rotation changes
```

Current-season head-to-head remains supporting evidence, not a deterministic rule.

## Part II Section 26 — Player Trades / Roster Changes

Authorization and trust status follow the player, not the team.

A trade does not remove a player from Joseph's universe.

The system should update the current team.

However, a trade triggers additional scrutiny because it may change:

```text
role
minutes
usage
teammates
offensive environment
defensive environment
starting status
representativeness of previous same-season data
```

Same-season evidence accumulated before the trade may still be recorded but should be treated cautiously when the context changed materially.

## Part II Section 27 — Role and Minutes Security

Role and minutes security is an important ranking factor.

Joseph strongly prefers players whose opportunity survives a poor start.

A starter can miss several early shots and still have enough minutes to recover.

A fragile bench player may miss several early shots and quickly lose opportunity.

Therefore the system should ask:

> How secure is this player's opportunity to recover from a bad start?

not merely:

> Can this player theoretically beat the projection?

A fragile bench-player selection means knowingly accepting increased opportunity risk.

## Part II Section 28 — Suspiciously Attractive Projections

An obviously attractive projection is not automatically good.

Popularity does not mean quality.

Joseph's principle is:

> All that glitters is not gold.

Example:

If a player has averaged approximately 50 over a recent stretch and suddenly receives a projection of 30, the agent must investigate why rather than automatically selecting Higher.

Possible reasons might include:

```text
blowout risk
role change
injury context
teammate return
minutes concern
matchup
other material information
```

Do not invent the reason. Retrieve evidence.

## Part II Section 29 — Automatic Fantasy-Board Retrieval

**Resolved by Part III E1:** The Odds API (`us_dfs`) is the approved automated board source for PrizePicks and Underdog data. Direct platform access remains prohibited.

Joseph does not want the ordinary workflow to require manually typing or uploading the daily fantasy projections.

The governing distinction is:

> The human approves the source. The system retrieves the data.

The earlier investigation of direct Underdog Fantasy and PrizePicks access is historical. The MVP uses one approved board source, The Odds API; do not add direct platform integrations merely to make the project larger.

Do not invent an API endpoint.

Do not call an unofficial endpoint an approved API without evidence.

If the approved source is unavailable, report the limitation rather than silently bypassing access controls or substituting another source.

Fixture and mock data may still be used for deterministic testing, but it is not Joseph's desired normal runtime workflow.

## Part II Section 30 — Access Policy

Acceptable investigation includes legitimate, documented, or appropriately accessible automated data methods.

Without Joseph's explicit approval, do not:

```text
use Joseph's personal login
reuse personal session cookies
reuse authentication tokens
circumvent CAPTCHA
circumvent anti-bot protections
evade access controls
misrepresent an unofficial endpoint as official
```

If an implementation method requires one of those actions, stop and report it.

## Part II Section 31 — Supporting NBA Sources

Joseph has approved these supporting sources:

```text
NBA.com
https://nba.com

Official NBA Injury Report
https://official.nba.com/nba-injury-report-2026-27-season/

Sports Illustrated NBA
https://www.si.com/nba
```

Their role is supporting evidence.

NBA.com is limited to schedules and general player and team information. NBA.com statistical endpoints are not approved for automated fantasy analysis. The Official NBA Injury Report is the approved injury and availability source. Sports Illustrated NBA supplies contextual and editorial information only.

The architecture is:

```text
THE ODDS API (us_dfs)
→ supplies PrizePicks and Underdog fantasy projections

NBA / APPROVED SUPPORTING SOURCES
→ supply approved schedules, injury, matchup, role, and contextual evidence
```

A supporting news or statistics source must not silently replace the approved board source as the projection source.

## Part II Section 32 — Game Totals and Spread Source

Joseph authorizes the system to retrieve:

```text
projected game totals
point spreads
```

from a legitimate source.

**Resolved by Part III E1:** use The Odds API's normal NBA odds endpoint for `spreads` and `totals`. Do not request game lines separately for every event when the sport-level endpoint returns the slate.

These values are analytical evidence for:

```text
expected scoring environment
game competitiveness
blowout risk
potential minutes reduction
```

They are not automatic prediction rules.

## Part II Section 33 — Three Projection Snapshots

For each relevant game, the system should record three projection snapshots before the game begins.

```text
Snapshot 1
Snapshot 2
Snapshot 3 = T-20
```

The third and final snapshot must occur approximately:

```text
20 minutes before tipoff
```

The system should preserve:

```text
projection value
platform
source
source update time
system retrieval time
observation number
player
category
direction
```

Examples of movement:

```text
30.5 → 31.5 → 33.0 = rising
33.5 → 32.5 → 31.5 = falling
31.5 → 31.5 → 31.5 = stable
31.5 → 32.5 → 31.5 = fluctuating
```

The movement must come from recorded observations.

The agent must not remember or fabricate earlier projections.

The precise timing of Snapshot 1 and Snapshot 2 does not need to be artificially fixed if the board becomes available at different times.

The core requirements are:

```text
three timestamped observations
T-20 is observation #3
```

## Part II Section 34 — Required Candidate Evidence

For a serious candidate, the analysis should normally consider:

```text
current projection
authorized direction
projection movement across the three snapshots
last 8 games
last-8 relationship to the relevant line
same-season H2H against today's opponent
starter/bench role
minutes security
expected usage/opportunity
opponent
offense/defense matchup
injuries
important teammate absences
important opponent absences
expected game total
point spread
blowout risk
Senior status
category trust status
foul-trouble annotation where applicable
category-specific matchup evidence
material conflicting evidence
material missing evidence
```

The factors should be interpreted together.

Do not create a fake rule such as:

```text
8 of 14 boxes checked = automatic pick
```

Joseph's methodology uses contextual judgment.

Deterministic operations such as counting, filtering, category normalization, authorization, and enforcing ceilings should still use code.

## Part II Section 35 — Missing Evidence Rule

Use contextual judgment regarding missing information.

If missing evidence is critical, the agent should hold or reject the candidate rather than guess.

If missing evidence is minor and enough reliable evidence remains, the agent may continue, but it must:

```text
state exactly what is missing
disclose the uncertainty
account for the uncertainty in confidence
```

The agent must never invent missing facts.

## Part II Section 36 — Conflicting Evidence / Risk

A strong candidate with meaningful risk is not automatically rejected.

Example:

```text
Strong Senior Higher candidate
+
meaningful blowout risk
```

may remain qualified.

The agent should:

```text
keep the candidate if sufficiently strong
adjust confidence/ranking where appropriate
surface the risk prominently
return the decision to Joseph
```

The agent informs Joseph's judgment.

It does not secretly decide Joseph's personal risk tolerance.

## Part II Section 37 — Confidence System

Use three confidence levels.

### HIGH CONFIDENCE

Multiple important signals align.

No major unresolved concern materially undermines the recommendation.

This is a strong final-slate candidate.

### MEDIUM CONFIDENCE

Enough evidence exists to qualify.

However, there is meaningful risk or conflicting evidence.

It may occupy a final slot if still strong enough.

The concern must be visible.

### LOW CONFIDENCE

Worth showing in analysis.

Does not automatically occupy one of the recommended 4 or 5 final slots.

Joseph may personally promote a Low Confidence candidate.

Never fill a slot simply because one is available.

## Part II Section 38 — Rejection / Status Reasons

Keep different failure and status categories distinct.

Examples:

```text
BLOCKED
→ player/category/direction unauthorized

INSUFFICIENT EVIDENCE
→ critical evidence unavailable or unreliable

REJECTED
→ evidence materially works against recommendation

QUALIFIED BUT NOT SELECTED
→ candidate qualified but stronger candidates occupy available slots

REMOVE RECOMMENDED
→ T-20 evidence materially worsened candidate

REMOVE
→ player unavailable / not playing when applicable
```

Low Confidence candidates may remain visible in analysis without occupying the recommended slate.

Zero qualified final candidates must produce:

```text
NO ENTRY RECOMMENDED TODAY.
```

## Part II Section 39 — Ranking

Do not use a fake numerical scoring formula merely to make the system look objective.

Ranking should be based on the overall strength of evidence under Joseph's methodology.

However, Senior priority is real.

General ranking philosophy:

```text
qualifying Senior candidates receive priority treatment
↓
overall evidence orders Senior candidates
↓
remaining qualified non-Seniors are ordered by overall evidence
```

A normal non-Senior should not casually displace a strong qualifying Senior simply because one small evidence dimension looks cleaner.

For approximately equal non-Senior candidates when only one slot remains, the agent may use its judgment based on the complete evidence.

The reason must be explainable and auditable.

Joseph explicitly allows the agent discretion in that tie-breaking situation.

## Part II Section 40 — Replacement / Displacement

A new candidate may displace the weakest current finalist only when it becomes materially stronger under Joseph's methodology.

Possible reasons include:

```text
confirmed teammate absence
major role change
important lineup change
material projection movement
new evidence
```

Newness alone is not sufficient.

Record:

```text
candidate entering
candidate displaced
reason
relevant evidence
timestamp
```

Senior priority still applies.

Do not casually replace a strong qualifying Senior with an ordinary player because of one new minor signal.

## Part II Section 41 — T-20 Final Review

At approximately 20 minutes before the relevant game, automatically perform the final review.

T-20 includes Snapshot #3.

Refresh and recheck:

```text
current projection
projection movement
availability/injury information
starting lineup / role changes
important teammate absences
important opponent changes
matchup context
game environment
game total
spread
blowout concern
any new material information
```

Each finalist receives a status such as:

```text
STILL STRONG
DOWNGRADED
REMOVE RECOMMENDED
```

Joseph retains final authority.

If T-20 removes a candidate:

```text
DO NOT FORCE A REPLACEMENT.
```

A replacement is allowed only when another genuinely qualified candidate already exists.

## Part II Section 42 — Final CLI Output

The normal final output should remain concise.

Do not dump the entire investigation into the normal final screen.

Use a compact table similar to:

```text
| Player        | Pick              | Confidence | Movement               | Last 8 | Status        | Key Risk |
|---------------|-------------------|------------|------------------------|--------|---------------|----------|
| Nikola Jokic  | Higher 49.5 PRA   | HIGH       | 47.5 → 48.5 → 49.5    | 6–2    | STILL STRONG  | Low      |
| Luka Doncic   | Higher 32.5 PTS   | HIGH       | 31.0 → 31.5 → 32.5    | 5–3    | STILL STRONG  | Blowout  |
| Jayson Tatum  | Higher 28.5 PTS   | MEDIUM     | 27.5 → 28.5 → 28.5    | 5–3    | DOWNGRADED    | Matchup  |
| Deni Avdija   | Higher 36.5 PRA   | HIGH       | 35.5 → 36.0 → 36.5    | 6–2    | STILL STRONG  | Low      |
| —             | EMPTY             | —          | —                      | —      | —             | No 5th pick qualified |
```

Use the full word:

```text
Confidence
```

not `Conf.`

The detailed evidence belongs in audit output.

An empty slot is useful evidence that the system did not force a selection.

## Part II Section 43 — CLI Command Concept

The current conceptual command set is:

```text
fifth-pick analyze
fifth-pick candidates
fifth-pick final
fifth-pick t20
fifth-pick audit
fifth-pick health
```

Conceptual purposes:

```text
analyze
→ retrieve board, filter universe, gather evidence, evaluate candidates

candidates
→ display qualified/relevant candidates

final
→ produce current recommended final slate for Joseph's review

t20
→ perform the final T-20 refresh/review

audit
→ show detailed evidence, sources, receipts, exclusions, rejection reasons,
   displacement history, and decision trail

health
→ run/represent mechanical health of the project/harness
```

These names are not permission to implement yet.

Confirm them in the read-back first.

## Part II Section 44 — Finalization Requires Joseph

`fifth-pick final` may generate a recommendation.

It must not record that recommendation as Joseph's officially finalized slate until Joseph explicitly approves.

Workflow:

```text
AGENT ANALYZES
        ↓
AGENT RECOMMENDS
        ↓
JOSEPH REVIEWS
        ↓
JOSEPH APPROVES / REJECTS / MODIFIES
        ↓
FINAL DECISION RECEIPT
```

If Joseph removes a recommendation, the system must not argue or automatically fill the vacancy simply to reach 4 or 5 selections.

## Part II Section 45 — Normal Board Filter Output

Keep normal filtering output simple.

Example:

```text
20 projections retrieved → 10 eligible
```

Do not clutter the normal CLI screen by printing every excluded prop.

The audit trail should still preserve enough detail to demonstrate why excluded entries were blocked, such as:

```text
unauthorized player
unauthorized category
unauthorized direction
```

## Part II Section 46 — Universe Change Control

The approved universe must be versioned.

A Joseph-approved change should record:

```text
change
timestamp
effective date
new active version
previous version preserved
```

Default behavior:

```text
Joseph-approved change
→ effective immediately
```

unless Joseph specifies a future effective date.

The agent itself cannot add, remove, or modify:

```text
players
categories
directions
Senior status
trust status
methodology
```

without Joseph's authorization.

Historical versions must remain available so past experiment results can be evaluated using the rules that actually existed at the time.

## Part II Section 47 — Planner

Planner decides how to investigate.

Joseph decides what the rules are.

Planner may:

```text
determine what evidence is needed
identify which eligible candidates deserve deeper investigation
identify matchup questions
identify category-specific checks
prepare a bounded analysis plan
```

Planner may not:

```text
add players
authorize categories
authorize directions
change trust tiers
change Senior status
change slate ceilings
change confidence definitions
change approved sources
change methodology
change snapshot policy
```

If the methodology does not cover an important decision:

```text
HUMAN_DECISION_REQUIRED
```

Do not invent a new rule.

## Part II Section 48 — Builder

Builder executes the approved plan.

Builder may:

```text
retrieve approved evidence
apply approved methodology
analyze eligible candidates
produce confidence classifications
rank candidates
produce recommendations
produce required evidence/receipts
```

Builder may not:

```text
bypass universe enforcement
rewrite methodology
use unapproved sources silently
exceed slate ceiling
fill empty slots merely to hit 4/5
override Planner boundaries
turn its recommendation into Joseph's final decision
```

If required evidence cannot be obtained, follow the missing-evidence rule.

Do not guess.

## Part II Section 49 — Reviewer

Reviewer is independent and mechanically read-only.

Reviewer may inspect:

```text
recommendations
evidence
methodology compliance
authorization compliance
receipts
gate results
diffs
```

Reviewer may not edit the work being reviewed.

Reviewer returns a typed verdict.

Valid reviewer verdicts:

```text
PASS
FAIL
CONCERNS
```

Do not convert malformed output or unknown status into PASS.

Reviewer independence should be mechanically enforced through OpenCode permissions, not merely requested in the prompt or persona.

## Part II Section 50 — Controller

Controller controls the workflow.

Controller does not control Joseph's methodology.

Controller may:

```text
dispatch Planner
dispatch Builder
dispatch Reviewer
parse structured results
validate known statuses
enforce workflow order
enforce correction limit
route failures
record workflow state
return reviewed recommendation to Joseph
```

Controller may not:

```text
change methodology
change universe
change trust tiers
change Senior status
change confidence rules
change selection ceilings
change approved sources
approve Joseph's final slate
implement work itself merely to repair a failed agent
```

Unknown or malformed status:

```text
STOP / FAIL CLOSED
```

not:

```text
guess what the agent meant
```

## Part II Section 51 — One Correction Attempt

The Fifth Pick uses a stricter bounded-review rule:

```text
Reviewer FAIL
        ↓
Controller sends findings to Builder
        ↓
Builder gets ONE correction attempt
        ↓
Reviewer checks again
```

If second review is:

```text
PASS
→ continue toward Joseph

FAIL
→ STOP / ESCALATE TO JOSEPH
```

No endless autonomous correction loop.

This is a project-specific choice.

## Part II Section 52 — Current Typed Agent Statuses

Planner:

```text
READY
HUMAN_DECISION_REQUIRED
BLOCKED
```

Builder:

```text
DONE
BLOCKED
INSUFFICIENT_EVIDENCE
```

Reviewer:

```text
PASS
FAIL
CONCERNS
```

Controller:

```text
COMPLETE
REVISION_REQUIRED
ESCALATE_TO_JOSEPH
STOPPED
```

Responses outside the closed status contract must fail closed.

Do not silently map an unknown status to success.

If the exact routing semantics for `CONCERNS` remain unresolved, identify that explicitly during the read-back rather than guessing.

## Part II Section 53 — Permissions

Use OpenCode permissions to enforce meaningful separation.

Conceptually:

```text
Planner
→ read/planning access
→ no implementation editing

Builder
→ read required project files
→ controlled write access only where required

Reviewer
→ mechanically read-only

Controller
→ orchestration and workflow-state functions
→ does not directly rewrite Builder output to make it pass
```

Sensitive and destructive actions should be denied or require explicit human permission.

Do not protect only direct file-edit tools while leaving an equivalent shell-write bypass.

Shell and tool permissions should respect the same trust boundaries.

## Part II Section 54 — AGENTS.md

AGENTS.md should be the project's control map, not the basketball encyclopedia.

Keep it comfortably below the course's 4,000-character ceiling.

Use exactly these four sections:

```text
Run and test

Conventions that differ from defaults

Rules that must hold (enforced)

Where the truth lives
```

The first sentence should state what the system is and what it must never do.

Conceptually:

> The Fifth Pick is a human-governed NBA fantasy-selection CLI that applies Joseph's approved methodology; it must never change that methodology or finalize a slate without Joseph's authority.

AGENTS.md should include:

```text
how to run/test
four gates
Python/Astral/unittest conventions
critical governance rules
actual enforcer for each critical never
pointers to authoritative files
skills to use where appropriate
```

Do not put the entire universe or detailed basketball methodology into AGENTS.md.

Every critical never must name its real enforcer.

If an enforcer has not been built yet, say honestly:

```text
Enforced by: nothing yet.
```

Do not claim a prompt is enforcement.

## Part II Section 55 — Authoritative Config / Spec Structure

Current conceptual separation:

```text
methodology.yaml
approved-universe.yaml
trust-tiers.yaml
approved-sources.yaml
governance.yaml
category-map.yaml
```

Intended ownership:

```text
methodology.yaml
→ Joseph's selection methodology

approved-universe.yaml
→ player/category/direction authorization

trust-tiers.yaml
→ Senior, PRA Trust, Assist Trust, Rebound Trust

approved-sources.yaml
→ approved projection/supporting sources and source restrictions

governance.yaml
→ Joseph authority, ceilings, final approval, revision bound,
   version/effective-date behavior

category-map.yaml
→ platform labels mapped to internal canonical categories
```

These are authoritative inputs.

They are not agent scratchpads.

Agents must not silently rewrite them.

Dynamic runtime data does not belong in these permanent rule files.

Examples of dynamic data:

```text
daily projections
snapshot observations
candidate evidence
injury observations
game results
receipts
```

Exact file format and path may change if OpenCode identifies a better technically supported structure, but preserve the separation of concerns.

Do not implement the structure yet.

## Part II Section 56 — Skills

Use Superpowers as the general disciplined development workflow.

Use Standard Technical English principles for clear project-specific instructions.

Current project-specific skill architecture:

```text
Superpowers
Standard Technical English
Evaluate Candidate
Validate Evidence
Final Slate Review
T-20 Review
```

Purpose:

```text
Superpowers
→ disciplined software-development workflow

Standard Technical English
→ simple, precise, low-ambiguity technical language

Evaluate Candidate
→ repeatable procedure for evaluating one eligible NBA fantasy prop
   under Joseph's methodology

Validate Evidence
→ verify that candidate evidence is current, trustworthy, sufficient,
   correctly sourced, and complete enough

Final Slate Review
→ apply slate ceilings, confidence eligibility, Senior priority,
   one-player-one-slot, displacement, and no-entry discipline

T-20 Review
→ perform final approximately-20-minute refresh and assign
   STILL STRONG / DOWNGRADED / REMOVE RECOMMENDED
```

Skill descriptions must clearly state when the skill should trigger.

Do not copy the entire methodology into skill descriptions.

The description is the trigger.

The `SKILL.md` body holds the procedure.

The authoritative methodology and config remain the source of truth.

Do not create tiny independent skills for every small basketball concept such as:

```text
Senior
foul trouble
last 8
H2H
projection movement
```

Those belong inside the candidate-evaluation methodology and procedure.

## Part II Section 57 — Standard Technical English

Use simple and precise language in:

```text
AGENTS.md
skills
agent personas
technical procedures
config guidance
```

Avoid unnecessary ambiguity, flowery instructions, or complicated wording when a simple technical statement is available.

This supports repeatable agent behavior.

## Part II Section 58 — Determinism

Use deterministic Python and code where correctness should not depend on LLM interpretation.

Examples include:

```text
universe filtering
player/category/direction authorization
slate-size classification
4/5 ceiling
one-player-one-slot
category normalization
snapshot counting
projection-history storage
Last-8 counting
source validation where mechanically possible
version/effective-date handling
typed-result parsing
revision counter
final-approval gate
```

Do not ask an agent to perform arithmetic or counting when deterministic code can do it reliably.

## Part II Section 59 — Hooks and Receipts

Use hooks for important observable moments in the workflow.

Before-action hooks may stop forbidden actions where appropriate.

After-action mechanisms may validate or record.

Receipts should preserve important observable actions, not hidden reasoning.

Important Fifth Pick receipt and event examples include:

```text
BOARD_RETRIEVED
PROJECTION_SNAPSHOT
CANDIDATE_BLOCKED
CANDIDATE_QUALIFIED
CANDIDATE_REJECTED
CANDIDATE_DISPLACED
REVIEW_PASS
REVIEW_FAIL
REVISION_ATTEMPT
JOSEPH_APPROVED
JOSEPH_REJECTED
JOSEPH_MODIFIED
FINAL_SLATE_RECORDED
RESULT_RECORDED
```

A receipt should normally record applicable fields such as:

```text
timestamp
event/action
result
subject
evidence/source reference
reason/status
```

Receipts prove what the harness observed.

They are not chain-of-thought logs.

## Part II Section 60 — Assurance Table

The Final System should include an assurance table based on:

```text
ACTION / RISK
CONTROL
EVIDENCE
```

Initial Fifth Pick assurance cases should include at least these concepts:

| What could go wrong? | Mechanical control | Evidence |
|---|---|---|
| Unauthorized player reaches analysis | Allow-list validator | `CANDIDATE_BLOCKED` receipt/test |
| Unauthorized category/direction reaches analysis | Category/direction validator | Block receipt/test |
| Too many final selections | 4/5 ceiling in code | Final-slate validation receipt/test |
| Agent fills empty slots just to reach maximum | Qualification/finalization controls | Empty-slot or no-entry evidence |
| Unapproved source is silently used | Source/provenance validation | Retrieval/source receipt |
| Projection movement is guessed | Three timestamped snapshots | Snapshot receipts |
| Critical evidence is unavailable | Missing-evidence control | `INSUFFICIENT_EVIDENCE` |
| Reviewer edits Builder work | Reviewer read-only permission | Permission evidence/diff |
| Reviewer returns malformed output | Typed parser | Fail-closed receipt/test |
| Review fails after correction | One-correction counter | `ESCALATE_TO_JOSEPH` |
| Agent changes methodology | Human-controlled/versioned configuration | Change/version receipt |
| Agent finalizes its own recommendation | Joseph approval gate | `JOSEPH_APPROVED` |
| Nothing qualifies | Explicit no-entry state | `NO ENTRY RECOMMENDED TODAY.` |

Do not create assurance rows whose control is merely:

```text
the prompt says not to
```

Every important row should eventually identify a control the model cannot simply rewrite or ignore by itself.

## Part II Section 61 — Quality Gates

`fifth-pick health` should represent the mechanical health state.

The required gates are:

```text
uv run ruff check
uv run ruff format --check
uv run ty check
uv run python -m unittest discover -s tests
```

Healthy means all four exit `0`.

Also demonstrate a controlled failing case before claiming the gates detect failure.

## Part II Section 62 — Fifth Pick Governance Tests

The test suite should eventually verify important deterministic rules such as:

```text
unauthorized player is blocked
unauthorized category is blocked
unauthorized direction is blocked
half slate never exceeds 4
full slate never exceeds 5
one player never consumes multiple final slots
Low Confidence does not automatically occupy final slate
empty slots remain empty
no forced T-20 replacement
exact NO ENTRY RECOMMENDED TODAY. behavior
malformed typed result fails closed
unknown typed status fails closed
only one correction attempt is permitted
Reviewer cannot edit
Joseph approval is required before official finalization
universe versions preserve effective-date behavior
three snapshots are recorded with T-20 as #3
```

Do not treat a prompt-only rule as sufficient when a deterministic test can prove it.

## Part II Section 63 — Post-Game Result Collection

**Superseded by Part III E12:** The MVP must not automate player-result retrieval. Use a platform-settled final result, a manually recorded result with provenance and receipt, or a deterministic fixture. If no trustworthy result exists, record `RESULT UNAVAILABLE`. The Odds API scores endpoint provides team scores, not adjudicated player box scores.

Compare a trustworthy result against the exact selection state used for the final decision.

Preserve the original:

```text
player
category
direction
projection
T-20 projection
Joseph decision
```

Example:

```text
Luka Doncic
Higher 32.5 Points
Final = 36 Points
Result = HIT
```

Do not compare against a line that changed after Joseph's decision.

Handle edge cases honestly.

Potential statuses include concepts such as:

```text
HIT
MISS
VOID
DNP
RESULT UNAVAILABLE
```

Do not invent platform-specific void, push, or stat-correction rules.

The Odds API is the approved board source. Verify the actual platform settlement rules and incorporate them without inventing them.

## Part II Section 64 — Experiment Evaluation

Separate agent and process quality from basketball outcome quality.

Evaluate at least:

| Evaluation area | Meaning |
|---|---|
| Methodology Adherence | Did the agent apply Joseph's methodology correctly? |
| Decision Discipline | Did it respect authorization, slate ceilings, no forced picks, Governance Zero, etc.? |
| Evidence Quality | Was sufficient reliable evidence retrieved and disclosed? |
| Outcome Performance | Did the final Higher/Lower selections actually hit? |

Do not call an agent-methodology failure merely because a properly analyzed selection happened to lose.

Outcome is an important metric, but it is not the only definition of agent quality.

## Part II Section 65 — Track Joseph's Overrides

Preserve:

```text
Agent recommendation
Joseph final decision
Actual result
```

This includes cases such as:

```text
Agent recommended → Joseph approved → Hit/Miss

Agent recommended → Joseph rejected → Would-have-hit / Would-have-missed

Agent recommended removal at T-20 → Joseph kept → outcome recorded

Agent recommended keep at T-20 → Joseph removed → outcome recorded

Joseph changed selection/direction → compare agent decision vs Joseph decision
```

These records are for evaluation.

They do not authorize the future agent to overrule Joseph.

## Part II Section 66 — Project Success

The Fifth Pick succeeds when it demonstrates that the agentic harness can reliably operate inside Joseph's defined system.

Success is broader than raw hit rate.

The system should demonstrate:

```text
methodology adherence
discipline
deterministic universe enforcement
evidence retrieval
source provenance
risk disclosure
bounded autonomy
independent review
typed results
fail-closed behavior
receipts
mechanical gates
human final authority
experiment outcome tracking
```

A losing basketball recommendation does not by itself prove the harness failed.

A winning recommendation produced by violating Joseph's methodology also does not prove the harness succeeded.

## Part II Section 67 — Repository Philosophy

Keep the project organized but not artificially complicated.

Conceptually separate:

```text
src/
→ deterministic application logic

config/
→ authoritative Joseph-approved rules

.opencode/
→ harness-specific agents, skills, configuration

tests/
→ deterministic proof

receipts/
→ action/control evidence

evidence/
→ retrieved runtime evidence
```

Do not create dozens of tiny Python modules merely to appear sophisticated.

Let the actual implementation needs determine reasonable module boundaries.

Preserve Evolutions 00–08. Do not rewrite historical Evolution evidence.

## Part II Section 68 — Current Conceptual Project Shape

Do not create this yet.

It is a planning model only.

```text
CIDM6333-project/
│
├── AGENTS.md
├── pyproject.toml
│
├── fifth-pick/
│   ├── src/
│   │   └── fifth_pick/
│   │       ├── cli.py
│   │       ├── controller.py
│   │       ├── eligibility.py
│   │       ├── evidence.py
│   │       ├── ranking.py
│   │       ├── snapshots.py
│   │       ├── finalization.py
│   │       └── results.py
│   │
│   ├── config/
│   │   ├── approved-universe.*
│   │   ├── trust-tiers.*
│   │   ├── methodology.*
│   │   ├── governance.*
│   │   ├── category-map.*
│   │   └── approved-sources.*
│   │
│   ├── tests/
│   ├── receipts/
│   └── evidence/
│
└── .opencode/
    ├── agents/
    │   ├── planner.*
    │   ├── builder.*
    │   └── reviewer.*
    │
    └── skills/
        ├── superpowers/
        ├── standard-technical-english/
        ├── evaluate-candidate/
        ├── validate-evidence/
        ├── final-slate-review/
        └── t20-review/
```

Determine technically correct OpenCode locations, names, and formats using the installed OpenCode version before implementation.

Do not assume this draft tree is mechanically correct merely because it looks reasonable.

## Part II Section 69 — Items That May Still Require Resolution

**Status:** Historical. A items are resolved by Part III A; B items by Part III D; C items use the accepted defaults in Part III C; D and E are the design freeze. The list below is retained as historical context and may contain superseded text. Do not use it to override Part III.

Do not guess on unresolved items.

During the read-back, explicitly identify whether any of these still need Joseph's decision:

```text
Exact legitimate fantasy-source access mechanism after researching Underdog and PrizePicks.

Exact approved source for game totals and spreads.

Any original approved-universe category whose direction remains unspecified
after applying explicit directions and the approved universe; trust tiers do not add authorization (E4).

Exact routing semantics for Reviewer verdict CONCERNS.

Exact platform void/push/stat-correction rules.

Exact stable player-ID fields available from the chosen fantasy platform.

Exact timing strategy for Snapshot 1 and Snapshot 2 if automation requires
a formal schedule; T-20 must remain Snapshot 3.

Exact supported OpenCode V2 configuration syntax for the installed version.

Any technically required adjustment to file locations and formats.
```

Additional unresolved items carried forward:

```text
Model choice for runtime and development agents.

Python version.

CLI exit codes.

Receipt schema and storage format.

Course deadline, grading criteria, and final presentation requirements.

Whether to create a Fifth Pick ADR and update docs/PRD.md.

Whether Senior status is a hard ranking tier above all non-Seniors or whether
a HIGH-confidence non-Senior can outrank a MEDIUM-confidence Senior.

How foul trouble interacts with the HIGH confidence definition.

How Joseph promotes a Low Confidence candidate.

How Joseph approves, rejects, or modifies a recommendation.

How to handle no same-season H2H or insufficient last-8 data.

Whether fewer than three snapshots are allowed if the board becomes available late.

Fallback if neither fantasy platform offers legitimate automated access.

Whether project-specific skills are global or repository-local.

Exact hook and plugin implementation.

Post-game result source and timing.

Evaluation period and minimum sample size.

Whether to update AGENTS.md and docs/PRD.md now or after approval.
```

Do not turn one of these into an implementation assumption without surfacing it first.

## Part II Section 70 — Source-Retrieval Failure

If an approved source temporarily fails:

Do not silently replace it with an unapproved source.

Do not invent evidence.

Apply the missing-evidence rule.

If the missing information is critical:

```text
INSUFFICIENT EVIDENCE
```

If it is non-critical and enough reliable evidence remains:

```text
continue cautiously
disclose exactly what is missing
adjust confidence if appropriate
```

## Part II Section 71 — Design Principle

The central design principle for this project is:

> Joseph defines the rules. The harness executes and verifies them. Joseph makes the final decision.

The agent should have enough discretion to perform meaningful analysis.

It should not have enough authority to rewrite the boundaries under which that analysis occurs.

## Part II Approval

Part III A–E record Joseph's approved decisions, source research, accepted defaults, and design freeze. This consolidated specification is the approved design basis to the extent reconciled with Part III.

Implementation is still not authorized. No implementation may begin until Joseph explicitly authorizes it.

---

# Part III — Approved Resolutions and Research Authorization

**Status:** A decisions approved by Joseph. B research authorized. C defaults accepted. D source decisions recorded by Joseph after research. E design freeze decisions approved by Joseph.  
**Implementation:** Still not authorized.

Part III supersedes the corresponding unresolved items in Part II Section 69 and Part II 9.3.

## Part III A — Joseph Decisions Resolved

### A1 — Direction Shorthand

The stated direction applies to every category listed in that player's entry unless a category has its own explicit direction.

Examples:

- `higher/lower points / PRA` means Higher and Lower are authorized for POINTS and PRA.
- `higher/lower points / rebounds` means Higher and Lower are authorized for POINTS and REBOUNDS.
- `lower points / PRA` means Lower is authorized for POINTS and PRA unless another explicit direction is written.
- An explicit category-specific direction always overrides the general shorthand.

Do not interpret the direction as applying only to the first category.

### A2 — Explicitly Listed Categories With No Direction

When Joseph explicitly listed a player and category but gave no Higher or Lower restriction anywhere in that entry, authorize both Higher and Lower unless an explicit restriction exists elsewhere.

Examples:

- Andrew Nembhard: ASSISTS and PRA → Higher and Lower.
- Ivica Zubac: POINTS and REBOUNDS → Higher and Lower.
- Kel'el Ware: POINTS and REBOUNDS → Higher and Lower.
- Wendell Carter Jr.: PRA → Higher and Lower.

The same principle applies to any equivalent explicitly listed directionless category.

Explicit Higher-only or Lower-only instructions always override this default.

### A3 — Trust-Tier Category Directions (Superseded by E4)

The earlier direction default for a trust-added category is retained only as historical context. Part III E4 removes the authorization that made that default operative.

For a category explicitly included in the approved universe, use the direction produced by A1, A2, or an explicit category-specific direction. Do not infer category authorization from a trust tier.

### A4 — Derived Trust-Tier Additions (Superseded by E4)

The earlier rule treated trust-tier membership as authorization. **Part III E4 supersedes it.** Trust memberships and derived additions are evaluation context only; they do not authorize a category.

Examples of earlier derived additions that now require explicit inclusion in Joseph's approved universe:

- Paolo Banchero PRA.
- Bam Adebayo PRA.
- Assist Trust players' ASSISTS.
- Rebound Trust players' REBOUNDS.
- LeBron James ASSISTS through Assist Trust.

The trust lists remain part of the methodology as classification data, not as an authorization mechanism.

### A5 — Senior Priority Versus Confidence

Senior priority is a real ranking priority, not a small bonus.

For qualifying Senior Higher candidates:

- HIGH or MEDIUM Senior candidates receive priority over ordinary non-Senior candidates.
- A HIGH-confidence non-Senior does not automatically jump above a MEDIUM-confidence qualifying Senior merely because its evidence looks cleaner.
- Evidence still orders candidates within the Senior tier.

Exceptions:

- The Senior candidate becomes LOW Confidence.
- The Senior candidate has INSUFFICIENT EVIDENCE.
- The Senior candidate is REMOVE RECOMMENDED.
- The Senior candidate no longer qualifies.
- Joseph explicitly overrides the ranking.

Do not weaken Senior priority into a normal tie-breaker.

Senior Lower candidates are handled under A17.

### A6 — Foul Trouble Versus HIGH Confidence

Foul trouble does not cap confidence at MEDIUM.

A foul-trouble player may still receive HIGH Confidence if the overall evidence supports HIGH and the foul-related risk is appropriately investigated and disclosed.

Foul trouble remains a meaningful risk flag. It is not a deterministic blocker or an automatic confidence ceiling.

### A7 — LOW Confidence Promotion

Only Joseph may promote a LOW Confidence candidate into the final slate.

Use Joseph's final Modify or Promote interaction. Do not give the agent that authority.

Record:

- candidate;
- Joseph promotion;
- reason if supplied;
- timestamp;
- receipt.

The agent may never promote LOW to a final slot by itself.

### A8 — Joseph Approval, Rejection, and Modification

Use a simple explicit human interaction after `fifth-pick final`.

The recommendation is displayed first.

Joseph must then explicitly choose:

- APPROVE;
- REJECT;
- MODIFY.

Do not record the recommendation as the official final slate until Joseph acts.

The decision must create a receipt.

### A9 — Missing Same-Season H2H and Incomplete Last-8

Use contextual materiality.

Missing same-season H2H is normally MINOR and must be disclosed. It becomes critical only when matchup-specific history is material to the recommendation.

Incomplete Last-8 data can be MINOR early in a season when eight games do not yet exist. Disclose the limitation and use the games actually available.

If the recommendation materially depends on unavailable evidence, treat the missing evidence as CRITICAL and return `INSUFFICIENT EVIDENCE` rather than guessing.

### A10 — Fewer Than Three Projection Snapshots

Preserve Joseph's three-snapshot rule.

The normal final recommendation requires:

1. Snapshot 1.
2. Snapshot 2.
3. Snapshot 3 = T-20.

Do not silently redefine two observations as sufficient.

If the fantasy board becomes available too late to obtain three legitimate observations:

- continue any analysis that can honestly be performed;
- clearly report that projection-movement evidence is incomplete;
- do not fabricate snapshots;
- do not automatically finalize that candidate as if the three-snapshot requirement was satisfied;
- treat the missing required movement evidence as `INSUFFICIENT EVIDENCE` for automatic finalization and return the disclosed situation to Joseph.

Joseph remains Governance Zero and may make his own final decision after seeing the limitation.

### A11 — No Legitimate Automated Access

Do not bypass platform controls.

If neither platform provides an acceptable legitimate automated route:

- fixture or synthetic data may be used for the course demonstration and deterministic tests;
- clearly label it as fixture or simulation data;
- report that the desired normal live automated workflow is currently unsupported;
- do not quietly turn manual uploads into the normal product workflow;
- do not use unofficial or private endpoints, account cookies, CAPTCHA bypasses, or similar workarounds.

### A12 — Supporting-Source Precedence

Use source authority by evidence type.

For injury and availability:

1. Official NBA Injury Report.
2. NBA.com official information.
3. Sports Illustrated or contextual reporting.

For official game, player, and statistical facts:

1. NBA.com or official NBA data.
2. Other approved factual sources.
3. Sports Illustrated as supporting context.

Sports Illustrated is primarily contextual and reporting evidence. It is not the authority over official NBA injury or statistical records.

If official sources appear to conflict:

- compare timestamps;
- prefer the newer applicable official information;
- disclose the conflict when material;
- do not silently choose whichever source is more convenient.

### A13 — CLI Command Names Approved

Approved:

```text
fifth-pick analyze
fifth-pick candidates
fifth-pick final
fifth-pick t20
fifth-pick audit
fifth-pick health
```

### A14 — Fantasy Platform Choice and Access Method

This is not a methodology decision to guess.

Research both Underdog Fantasy and PrizePicks as described in B1.

After research:

- recommend the strongest legitimate automated option;
- document the exact access method;
- document stable identifiers and platform rules;
- explain limitations;
- return the recommendation to Joseph for approval before platform integration.

Joseph has already prohibited personal login or session reuse, cookie reuse, CAPTCHA bypass, anti-bot circumvention, and access-control evasion without explicit permission.

### A15 — Game-Total and Point-Spread Source

Research legitimate sources as described in B5.

Recommend a source with documented or clearly permitted access and clear provenance.

Return the recommendation to Joseph for approval before integration.

Do not invent or silently use an unofficial odds endpoint.

### A16 — VOID, PUSH, and Stat-Correction Behavior

Use the selected platform's actual documented rules.

Record the rule source and version where possible.

Do not invent platform settlement behavior.

If the platform's documented rule is genuinely ambiguous, disclose the ambiguity and bring it to Joseph.

If a result cannot be reliably classified, prefer an honest status such as `RESULT UNAVAILABLE` over a fabricated `HIT` or `MISS`.

### A17 — Senior LOWER Candidates

A Senior LOWER candidate is not forbidden, but it is intentionally difficult to justify.

It may occupy a final slot when:

- there is strong contextual evidence, especially blowout or reduced-minutes evidence;
- it reaches at least MEDIUM Confidence;
- the risk and rationale are prominently disclosed.

A Senior LOWER candidate does not receive the same priority treatment as a qualifying Senior HIGHER candidate simply because the player is Senior.

### A18 — Reviewer CONCERNS

`CONCERNS` must never become PASS automatically.

Use:

```text
Reviewer = CONCERNS
→ Controller routes the concerns to Joseph
→ Joseph sees the recommendation and concerns before finalization
```

Operationally, route to `ESCALATE_TO_JOSEPH` when the concerns require human judgment.

Joseph may still approve, reject, or modify after seeing the concerns.

The agent and controller may not silently convert CONCERNS into PASS.

## Part III B — Authorized Technical Research

Joseph authorized B1 through B13 as research only. This is not authorization to implement the Fifth Pick.

Research items:

- B1: legitimate automated access for Underdog Fantasy and PrizePicks.
- B2: legitimate NBA.com data access.
- B3: Official NBA Injury Report access.
- B4: Sports Illustrated access, excerpt, and provenance policy.
- B5: legitimate game-total and point-spread source.
- B6: stable player IDs from the candidate fantasy platform or platforms.
- B7: platform VOID, PUSH, and stat-correction rules.
- B8: exact configuration syntax supported by the installed OpenCode version.
- B9: necessary repository, file, and path layout adjustments while preserving existing Evolutions.
- B10: post-game official-result source and retrieval timing.
- B11: correct packaging and location for Superpowers, STE, and Fifth Pick-specific skills.
- B12: installed OpenCode hook and plugin mechanisms for read-only review, receipts, and fail-closed behavior.
- B13: technically reliable Snapshot 1 and Snapshot 2 scheduling.

B13 invariant:

- exactly three intended projection observations;
- Snapshot 3 = T-20;
- Snapshot 1 should occur when the usable board first becomes available;
- Snapshot 2 should occur meaningfully between Snapshot 1 and T-20;
- configurable or calculated Snapshot 2 timing is allowed;
- the three-snapshot requirement must not be weakened.

For B8 and B9, inspecting the installed OpenCode version and existing repository is permitted. Do not modify the harness.

Every researched source or access method must include evidence and provenance.

After B1 through B13, return the research findings and recommendations to Joseph. Do not begin implementation.

## Part III C — Deferred Implementation Defaults

Unless research reveals a conflict with the approved specification, use these defaults later:

- C1: CLI exit codes: `0` successful or valid result including valid no-entry; `1` blocked or operational failure; `2` usage error.
- C2: Receipts: JSON Lines preferred, with timestamp, event, result, subject, source, reason, and run ID.
- C3: Final output compact; audit contains detail. `EMPTY` is acceptable for unused slots. Last-8 shows the over or under count relative to the relevant projection.
- C4: Keep runtime and persona model choice configurable rather than hard-coding one model prematurely.
- C5: Pin a stable Python version supported by the actual Astral and OpenCode toolchain.
- C6: After this specification and the remaining research are approved, update `AGENTS.md` and authoritative project documentation before harness implementation.
- C7: Preserve earlier project material as historical context where useful; the current Fifth Pick specification is authoritative.
- C8: Create a Fifth Pick-specific ADR when implementation decisions warrant it. Do not reuse an unrelated old ADR as if it covered this architecture.
- C9: Determine the evaluation period and sample requirement from actual course constraints before locking the experiment sample size. Track every analyzed slate that belongs to the experiment.
- C10: In addition to the three projection snapshots, factual supporting sources may refresh when material news appears. Extra source refreshes do not create extra projection snapshots unless intentionally recorded as such.
- C11: Use small deterministic synthetic fixtures for governance tests. Recorded or redacted payloads may supplement them later.
- C12: `audit` contains full evidence, exclusions, receipts, provenance, and decision trail; `final` remains concise.
- C13: Use a simple explicit Approve, Reject, Modify interaction and confirmation receipt.
- C14: Confirm the actual course deadline, grading criteria, and presentation and delivery requirements from course materials early enough to prevent scope mistakes.

---

# Part III D — Source Architecture Decisions After Research

**Date:** 2026-11-14  
**Status:** Joseph reviewed the B1–B13 research and directed these source corrections. This section records source decisions only. Implementation remains unauthorized.

## D1 — Approved MVP Primary Source

Use **The Odds API** as the approved MVP primary source for the live fantasy/odds board and game-environment lines.

Joseph completed the free-plan live verification on 2026-11-14. The verification confirmed that both PrizePicks and Underdog data can be retrieved through the `us_dfs` region.

Reasons:

- Its official documentation lists both `prizepicks` and `underdog` under the `us_dfs` region.
- It provides documented API access rather than scraping either fantasy platform directly.
- Its Starter plan provides 500 free monthly credits.
- It supports NBA game totals, spreads, and the principal Fifth Pick categories:
  - POINTS via `player_points`
  - REBOUNDS via `player_rebounds`
  - ASSISTS via `player_assists`
  - PRA via `player_points_rebounds_assists`
  - REBOUNDS_ASSISTS via `player_rebounds_assists`
- One legitimate API can provide both the fantasy projection board and game-environment lines.

The verification record must preserve:

- request URL with the API key redacted;
- request timestamp;
- HTTP status;
- returned bookmakers;
- returned markets;
- returned event IDs;
- whether `prizepicks` and/or `underdog` are present;
- whether each required live category is present;
- `x-requests-remaining`, `x-requests-used`, and `x-requests-last`;
- a hash of the raw response for provenance.

Do not store the API key in the repository or in a receipt.

If a future verification fails, return to Joseph. Do not silently substitute another provider.

## D2 — Required Categories and THREE_POINT_ATTEMPTS

The live MVP categories supported through The Odds API are:

```text
POINTS
ASSISTS
REBOUNDS
PRA
REBOUNDS_ASSISTS
```

`THREE_POINT_ATTEMPTS` is not an MVP live category. It is not required for the MVP and must not be substituted or fabricated from another source.

Do not map `player_threes` to `THREE_POINT_ATTEMPTS`. `player_threes` means threes made.

Do not evaluate `THREE_POINT_ATTEMPTS` live unless Joseph later approves a legitimate source that returns the actual attempts projection. Future support requires a separate approved source decision.

The system must clearly mark `THREE_POINT_ATTEMPTS` as outside the MVP live scope. Deterministic fixtures may cover the future-only path without presenting it as live data.

## D3 — Game Totals and Spreads

Use The Odds API for NBA `h2h`, `spreads`, and `totals`.

Do not add a second provider merely to provide game totals or spreads.

## D4 — Direct Platform Access Prohibited

Prohibit direct scraping, automated browser extraction, personal-cookie reuse, login automation, and unofficial private endpoints for Underdog Fantasy or PrizePicks.

The Fifth Pick consumes PrizePicks/Underdog data through the approved data provider, not by automating either platform directly.

## D5 — NBA.com Statistics

Do not use NBA.com statistical endpoints as the Fifth Pick's automated statistical data source where doing so would conflict with NBA.com's current terms concerning fantasy-game use.

The Official NBA Injury Report may remain a contextual official source only if the approved retrieval method is compliant.

Do not treat undocumented `stats.nba.com` endpoints as approved APIs.

## D6 — Post-Game Results

Do not require an expensive licensed player-stat provider for the MVP merely to automate outcome grading.

For the course MVP, allow:

- platform-settled result data if legitimately available from the approved provider;
- otherwise, a manually recorded final result with provenance and a receipt;
- deterministic fixture results for demonstrations and tests.

Never fabricate `HIT` or `MISS`.

If an authoritative result cannot be obtained, use `RESULT UNAVAILABLE`.

Keep the architecture capable of automated results later.

The Odds API scores endpoint provides team scores, not adjudicated player box scores. Do not treat team scores as player results.

## D7 — PreciseAPI

Keep PreciseAPI in the research documentation as an optional future/full-coverage provider, especially because it supports `player_threes_attempted`.

Do not make PreciseAPI a required dependency. Do not require Joseph to purchase the paid service for the course MVP unless Joseph later explicitly approves it.

## D8 — Verification and Approval Gate

The free-plan technical verification of The Odds API is complete, and Joseph has approved The Odds API as the MVP source.

No implementation may begin until Joseph explicitly authorizes implementation.

The verification was a technical validation, not a purchase authorization.

## D9 — Free-Plan Usage Estimate

The Odds API cost model:

```text
odds request cost = number of markets x number of regions
```

- `/sports` and `/events` do not count against the quota.
- `/scores` costs 1 credit for live/upcoming games and 2 credits when `daysFrom` is specified.
- If no events are returned, the request does not count against the quota.
- Alternate player-prop markets are separate markets and therefore increase cost.

Assume a typical full slate of 10 NBA games. Assume one `us_dfs` region and one team-lines region.

Standard-board scenario, using five live categories:

```text
player props: 5 markets x 10 games x 1 region = 50 credits per snapshot
three snapshots: 50 x 3 = 150 credits
game lines: 3 markets x 1 region x 3 snapshots = 9 credits
total: 159 credits per day
free-plan duration: 500 / 159 = about 3.1 days
```

Complete-board scenario, adding the five alternate markets:

```text
player props: 10 markets x 10 games x 1 region = 100 credits per snapshot
three snapshots: 100 x 3 = 300 credits
game lines: 3 markets x 1 region x 3 snapshots = 9 credits
total: 309 credits per day
free-plan duration: 500 / 309 = about 1.6 days
```

Range for an 8-to-12-game full slate:

```text
standard board: about 129 to 189 credits per day
free-plan duration: about 2.6 to 3.9 days

complete board: about 249 to 369 credits per day
free-plan duration: about 1.4 to 2.0 days
```

These estimates exclude retries, result retrieval, and additional regions or bookmaker groups. A daily `/scores?daysFrom=1` call adds 2 credits per day.

Conclusion: 500 free credits are sufficient for a short technical verification and a small demonstration, but not for a multi-week full-slate experiment using three snapshots and alternate markets. Any paid-tier decision is separate and requires Joseph's explicit approval.

The MVP does not query alternate markets by default. The standard-board scenario is therefore the applicable MVP estimate. Alternate-market costs are retained only for future capability planning.

The 500-credit free plan is acceptable for a limited live course pilot, not a multi-week full-slate continuous experiment. The three-snapshot rule must not be weakened. Use a limited number of genuine live slate days for the live experiment and deterministic synthetic or recorded fixtures for governance tests and repeatable demonstrations. Live evidence and fixture evidence must be clearly distinguished; fixture runs must never be reported as live experiment results.

---

# Part III E — Design Freeze Decisions

**Date:** 2026-11-14  
**Status:** Approved by Joseph. Implementation remains unauthorized.  
**Effect:** This section supersedes earlier Part III text where it conflicts.

## E1 — Approved Live Projection Source

The Odds API is the approved automated projection-board source for the Fifth Pick MVP.

Joseph's live verification on 2026-11-14 confirmed that both PrizePicks and Underdog data can be retrieved through the `us_dfs` region.

The verified live MVP categories are:

```text
POINTS
ASSISTS
REBOUNDS
PRA
REBOUNDS_ASSISTS
```

Three-point attempts are not required for the MVP and must not be substituted with another category or fabricated from another source.

The system may support three-point attempts later only if an approved source becomes available and Joseph explicitly approves that source.

## E2 — Platform-Specific Projections

PrizePicks and Underdog may show different projections for the same player.

The system must not combine those projections into one artificial line.

Each observation must retain:

```text
platform
player
category
projection
direction
event
source update time
system retrieval time
```

A PrizePicks projection remains a PrizePicks observation. An Underdog projection remains an Underdog observation.

## E3 — Player Identity

The verified DFS responses do not provide a stable player ID.

The Fifth Pick will maintain its own canonical player registry.

Provider names must be mapped to the canonical registry before a candidate can enter the methodology.

The system must not silently create a new player because a similar name appears.

Unknown or ambiguous identities must fail closed and be surfaced to Joseph.

## E4 — Authorization Priority Over Trust Lists

The approved player/category/direction universe is the authorization gate.

PRA, assist, rebound, Senior, or other trust classifications do not automatically authorize a category that Joseph did not authorize for that player.

Trust classifications affect evaluation only after the candidate passes the authorization gate.

The decision order is:

```text
authorization first -> methodology second -> ranking third
```

Where earlier Part III A4 describes trust-tier category additions, this freeze requires those categories to be explicitly present in Joseph's approved universe. Trust classification alone is not authorization.

## E5 — Malik Monk

Malik Monk currently has no category or direction specified in the approved universe.

He remains in the registry but is not eligible for automated candidate selection until Joseph defines his authorized category and direction.

The agent must not guess one.

## E6 — Missing Evidence and Rejection Rule

The system may say that it does not have enough trustworthy information to recommend a candidate.

A candidate must not be promoted to the final slate when a material piece of required evidence cannot be established.

Required rejection or limitation codes include:

```text
PLAYER_IDENTITY_UNRESOLVED
CATEGORY_NOT_AUTHORIZED
PROJECTION_UNAVAILABLE
PROJECTION_OBSERVATION_MISSED
AVAILABILITY_UNRESOLVED
ROLE_OR_MINUTES_UNRESOLVED
T20_CHECK_UNAVAILABLE
SOURCE_CONFLICT_UNRESOLVED
INSUFFICIENT_SUPPORTING_EVIDENCE
```

Definitions:

- `PLAYER_IDENTITY_UNRESOLVED`: the system cannot confidently map the projection to the correct canonical player.
- `CATEGORY_NOT_AUTHORIZED`: the player is approved, but the displayed category or direction is outside Joseph's authorized universe.
- `PROJECTION_UNAVAILABLE`: the required live projection cannot be retrieved.
- `PROJECTION_OBSERVATION_MISSED`: a required legitimate observation was missed and must not be recreated or backfilled.
- `AVAILABILITY_UNRESOLVED`: important injury, availability, or participation information remains unresolved.
- `ROLE_OR_MINUTES_UNRESOLVED`: the recommendation materially depends on a role or minutes change that cannot be supported by trustworthy evidence.
- `T20_CHECK_UNAVAILABLE`: the mandatory final pregame review could not be completed.
- `SOURCE_CONFLICT_UNRESOLVED`: two relevant trustworthy sources materially conflict and the conflict cannot be resolved without guessing.
- `INSUFFICIENT_SUPPORTING_EVIDENCE`: the candidate passes authorization but the available evidence is not strong enough to justify recommending it.

These codes are not automatic predictions that a player will fail. They mean the system lacks enough justified evidence to recommend the selection.

## E7 — No Fabricated Confidence

Missing evidence must never be converted into fake certainty.

The agent may not:

- invent a projection;
- invent an injury status;
- invent a player mapping;
- invent projection movement;
- backfill a missed snapshot;
- silently substitute another player;
- silently substitute another category;
- call missing information evidence for Higher or Lower.

When evidence is incomplete, the system records the limitation.

## E8 — Confidence Rule

High confidence requires multiple important signals to align without a major unresolved concern.

Medium confidence means sufficient evidence exists but a meaningful conflict or risk remains.

Low confidence candidates may appear in analysis but do not automatically occupy one of the final recommended slots.

The system never fills the maximum number of selections simply because slots remain available.

## E9 — T-20 Requirement

The T-20 review remains a mandatory final evaluation stage.

It rechecks projection, projection movement, availability, starting role, teammate absences, game environment, blowout risk, and other methodology-relevant information.

The allowed T-20 conclusions remain:

```text
STILL STRONG
DOWNGRADED
REMOVE RECOMMENDED
```

If the T-20 check cannot be completed, the system records `T20_CHECK_UNAVAILABLE` rather than pretending the earlier evaluation is current.

Joseph remains the final authority.

## E10 — Snapshot Integrity

The experiment requires three legitimate projection observations.

Supporting-source refreshes do not count as projection observations.

Missed observations are recorded as missed and are never reconstructed after the fact.

The audit trail must distinguish:

```text
source observation time
system retrieval time
platform
event
market
player
projection
snapshot number
```

## E11 — Multiplier Data

Multiplier information is optional supporting metadata and is not part of the core Fifth Pick methodology.

The live verification showed that the field may be absent, `None`, or platform-specific.

The system must therefore never require multiplier data in order to evaluate an otherwise valid projection.

## E12 — Result Integrity

A recommendation must never later be marked `HIT` or `MISS` unless a trustworthy final result is available.

DNP, void, or equivalent platform cancellations must not be recorded as `MISS`.

If an authoritative result cannot be established, the experiment records:

```text
RESULT UNAVAILABLE
```

The system must preserve the difference between prediction quality and unavailable settlement information.

## E13 — No-Entry Discipline

The maximum number of final recommendations remains:

```text
HALF SLATE, 1-4 NBA games: maximum 4
FULL SLATE, 5+ NBA games: maximum 5
```

These are ceilings, not targets.

If only two candidates genuinely qualify, recommend two.

If none qualify, the exact output is:

```text
NO ENTRY RECOMMENDED TODAY.
```

No outside-universe player may be introduced simply to fill an empty slot.

## E14 — Final Governance Order

The Fifth Pick decision flow is:

```text
live board retrieval
-> canonical identity
-> authorization gate
-> evidence collection
-> Joseph's methodology
-> confidence/risk assessment
-> ranking
-> T-20 review
-> discipline ceiling
-> Joseph's final decision
```

The agent evaluates and enforces discipline.

Joseph owns the methodology and remains the final decision-maker.
