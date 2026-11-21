# Learning notes for The Fifth Pick

The Fifth Pick takes platform lines and supporting evidence, applies Joseph's rules, and records a reviewable decision trail. Follow one fixture from the menu to the audit with the [course walkthrough](presentation.md).

## Python and the terminal

| Term | Meaning in this project |
| --- | --- |
| Python | The language that reads the provider data, applies rules, and writes audit records. |
| CLI | A command-line interface. `fifth-pick menu` opens the choices in the terminal. `uv run --offline --no-sync` runs with the prepared project environment. |
| Module and function | A module is a Python file. A function is a named operation. `identity.py` contains code for matching provider names to canonical players. |
| Dataclass and enum | A dataclass groups named fields into a record. An enum gives a field a fixed set of options. `models.py` defines records such as an observation and options such as `HIGHER` and `LOWER`. |
| Automated test | A repeatable check of a specific behavior. `unittest` exercises behavior, Ruff checks lint and formatting, and ty checks types. |

Think of a basketball practice plan. Each drill has a name and a specific job. Modules organize related jobs, functions carry them out, and tests check whether the drills produce the expected behavior, including when something goes wrong. [Architecture](architecture.md) · [Fixture workflow test](../../tests/test_fixture_cli.py)

## APIs, identity, and data

An **API** defines how programs request information. An **endpoint** is a particular address for a request, like the scorer's desk where you go for the game list or the board for a particular game. The Odds API event list supplies event IDs. A per-event request asks for the approved fantasy markets from PrizePicks and Underdog. The provider responds with an HTTP status and data. The API key authorizes the request through a header and stays in the process environment. A **quota** limits usage, and approved discovery and paid board requests have different credit rules. [Board source verification](source-verification.md)

A **fixture** is a prepared example. Demo Mode feeds synthetic JSON through the offline adapter so the same input can be replayed during practice. **Normalization** converts provider fields to project fields. **Canonical identity** is the project's stable identity for a player. An exact authorization ties that identity to a category and direction. An ambiguous label or missing grant stops the candidate. Think of matching a jersey to the official roster before recording a stat. [Identity and source modules](architecture.md)

**Provenance** records where the data came from, when the source published or updated it, when it was retrieved, and how to identify the payload. A SHA-256 **digest** is a fingerprint of the bytes inside that record's stated scope. In painting, think of labeling a color swatch with the paint and date so you can trace where it came from. The digest helps check that the recorded bytes stayed the same. A **receipt** records a particular workflow event. The audit groups those records so you can see how a run reached its decision. [Receipt schema](architecture.md#receipt-schema)

## Basketball lines and descriptive statistics

- **Line and direction.** A line is the threshold for a selection. If a fictional assists line is 9.5, a result of 10 is higher and a result of 9 is lower. An exact tie is a push. A result graded on the wrong player, platform, direction, or line answers a different question.
- **Sample and last eight.** A sample is the group of recorded games used for a comparison. The last-eight view takes up to eight recent usable games and reports an incomplete sample when appropriate. Think of an athlete's last eight timed drills. You can count results faster, slower, or equal to today's target.
- **Head-to-head (H2H).** This view uses games in the same season against the same opponent. It can give matchup context, and the sample can be small. Here H2H means player history against an opponent.
- **Counts and confidence.** For three practice games with 8, 10, and 11 assists, at a 9.5 line there are two above, one below, and zero equal. The counts describe those three games. The application's HIGH confidence is a qualitative evidence judgment based on cited support and meaningful risks. Three practice games give little basis for estimating the chance of a future result.
- **Context.** Minutes, role, availability, opponent, game total, point spread, and potential blowout can change how past performance applies. A runner's practice times have different implications when the next race is on a different surface or the runner is injured. In LIVE, missing required historical or game-environment evidence can prevent qualification. Availability, role, and minutes are optional context. Missing optional context supplies no support for a direction or confidence.

[Evidence summaries](../../src/fifth_pick/evidence.py) · [Frozen methodology](../superpowers/specs/2026-11-13-fifth-pick-design.md)

## Trace a decision

Follow the first two snapshots into the provisional watchlist, then the third into T−20 review. The demo uses its recorded fixture clock. A new LIVE series uses the first official tipoff across the entire slate. A late reading cannot replace a missed snapshot. Review and explicit approval precede grading of the exact approved selection. DNP means did not play, VOID means the result is void, and `RESULT UNAVAILABLE` records missing trustworthy result evidence. As in reviewing a race, judge whether you followed the process separately from where you finished. [Runbook](runbook.md) · [Assurance](assurance.md)

## Explain it back

- Trace one projection from input JSON to the CLI screen. Point to the exact player, market, direction, and timestamp that Python validates.
- Explain why two results above a line in three past games do not establish a calibrated win probability. Then show what the CLI reports when evidence is incomplete.
- Open one receipt and explain what its digest can establish. Describe how the Controller, independent Reviewer, and Joseph each contribute to the final decision.
