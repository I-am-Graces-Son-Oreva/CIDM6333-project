# Product Requirements Document

## System

The Fifth Pick — An NBA Fantasy Selection & Discipline Experiment

## User

The primary user is me. I use NBA fantasy projections to make Higher and Lower selections and want a more disciplined and consistent process for applying my strategy.

## Problem

I normally rank fantasy selections from the ones I trust the most to the ones I trust less. When I make larger entries, I sometimes continue adding selections after I already have my strongest choices.

The system should test whether an agent can consistently apply my documented NBA fantasy-selection strategy while helping me know when to stop.

## Product Goal

Build an auditable NBA fantasy-selection agent that gathers available current projections, applies my documented strategy, ranks qualified candidates, and enforces a Stop Gate without taking the final decision away from me.

The goal is not to produce the maximum number of selections. The goal is to protect decision quality.

## Acceptance Criteria

1. The system evaluates candidates using my documented fantasy-selection rules rather than inventing its own strategy.
2. The system distinguishes verified current information from uncertainty and does not invent projections, injuries, lineups, or other evidence.
3. The system ranks qualified candidates from strongest to weakest and records reasons for important recommendations and rejections.
4. For a small slate, the system recommends no more than four final selections.
5. For a large slate, the system recommends no more than five final selections.
6. The maximum is a ceiling, not a target. The system does not add weaker selections simply to reach the limit.
7. If no candidates meet the required standard, the system returns **NO ENTRY RECOMMENDED TODAY.**
8. Final candidates normally receive a T-20 review approximately 20 minutes before the relevant game begins using the latest information available to the system.
9. If a late change removes a candidate, the system does not automatically replace that candidate simply to maintain the previous number of selections.
10. I remain Governance 0. I can accept fewer selections, reject recommendations, or choose no entry.
11. The system does not automatically submit fantasy entries or make the final decision for me.
12. The system keeps system-performance evaluation separate from outcome evaluation: following my documented strategy is evaluated separately from whether an individual selection eventually hits or misses.
13. The agent has a bounded execution process and stops rather than continuing unnecessary tool calls when it has reached a final recommendation, a no-entry decision, or cannot obtain required information.

## Boundaries

The initial experiment is limited to NBA fantasy selections during the 2026–27 NBA season.

The system may gather and analyze available information, evaluate Higher and Lower candidates, rank candidates, apply my strategy, and recommend when to stop.

The system does not guarantee that a selection will succeed, does not lower its standards just to produce more selections, does not automatically submit an entry, and does not override my final decision.

## Attestation

I, Joseph Edafiadhe, attest that this PRD represents the intended user, problem, boundaries, and acceptance criteria for The Fifth Pick.

Attested: 2026-11-11
