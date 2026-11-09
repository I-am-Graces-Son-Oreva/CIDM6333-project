# Evolution 7 — Chase Independent Preflight Handoff

## Status
CHASE NO-GO CORRECTIONS IN PROGRESS — PREVIOUS NO-GO REMAINS VALID.

The implementation now fails closed on existing sandbox, private, sidecar,
and OpenCode data paths; preserves existing ledgers; and includes a synthetic-
validated capture command. These changes are uncommitted and require a
separate independent Chase re-review. No GO or PASS is claimed.

## Code and evidence
- Implementation commit: 6755cce
- Isolation summary commit: 3122f35
- Automated tests: 32 passed
- OFF isolation probes: 65 total; 61 denied; 3 allowed absent; 1 expected allowed read
- ON isolation probes: 64 total; 61 denied; 2 allowed absent; 1 expected allowed read
- Reported leaks: 0

## Review materials
- evolution-07/flight-card.md
- evolution-07/ADR-2.md
- evolution-07/evidence/preflight-isolation.json
- evolution-07/evidence/preflight-tp5-isolation.json
- evolution-07/evidence/isolation-summary.md
- src/e7_memory/
- tests/test_e7_isolation.py

## Required independent checks
1. Confirm sandbox enforcement against actual private memory artifacts.
2. Confirm OFF cannot retrieve hidden memory from any excluded source.
3. Confirm ON can access memory only through the retrieval service.
4. Confirm fresh OpenCode data directories and valid V1 permission configuration.
5. Confirm the fixture hash and retrieval score threshold.
6. Confirm TP5 eviction is isolated and ledger events are append-only.
7. Confirm live tool traces and verbatim answers can be captured.
8. Check all 25 falsifiers and 7 ABORT conditions in the Flight Card.

## Decision
Chase verdict: PENDING
Official sortie: NOT RUN

Do not launch the official sortie before independent Chase GO.
