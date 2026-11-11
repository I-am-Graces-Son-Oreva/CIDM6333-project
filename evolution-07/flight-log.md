# Evolution 7 Flight Log — Memory With a Receipt

## Sortie Status

**Status: ABORTED**

The official Evolution 7 sortie received independent Chase GO before flight. The approved flight configuration required fresh isolated OpenCode sessions using `opencode/big-pickle`, with separate Memory-OFF and Memory-ON sandboxes.

## Official Sortie Attempt

The sortie was started using the approved Memory-OFF configuration.

OpenCode initialized the fresh session and selected:

- Provider: `opencode`
- Model: `big-pickle`
- Agent: `build`

Before TP1 could produce an answer, the model call returned:

`AI_APICallError: Free usage limit reached. Free models work in OpenCode; subscribe to OpenCode Go to keep going.`

The process did not produce a valid TP1 answer or official TP1 evidence.

A later fresh attempt under the approved isolation configuration reproduced the same model-availability error.

## ABORT Decision

The sortie was aborted rather than weakening the approved isolation boundary or substituting fabricated evidence.

This is recorded as an infrastructure/model-availability ABORT, not a TP1 FAIL. The answering model was unavailable under the approved sortie configuration.

No TP1–TP5 PASS claims are made from this aborted sortie.

Preflight and automated test results remain supporting engineering evidence only and are not represented as official sortie results.

## Diagnostic Evidence

The OpenCode usage-limit failure was preserved in:

`evolution-07/evidence/aborted-sortie-opencode-limit.log`

Additional diagnostic work established that Big Pickle remained available in ordinary OpenCode execution, but the official sortie could not complete successfully under the approved E7 execution configuration.

The approved sandbox and flight-card conditions were not weakened merely to obtain a successful model response.

## Existing Verification

Before the official sortie:

- `tests/test_e7_memory.py`: 8 tests passed.
- `tests/test_e7_isolation.py`: 24 tests passed.
- E6 context tests: 5 tests passed.
- Full relevant suite: 37 tests passed.

These results verify implementation and isolation behavior but do not replace the required official sortie.

## TP Status

| Test Point | Result | Reason |
|---|---|---|
| TP1 — Memory OFF | ABORT | Answering model unavailable before a valid answer was produced |
| TP2 — Memory ON | NOT FLOWN | Sortie aborted at TP1 |
| TP3 — Control | NOT FLOWN | Sortie aborted at TP1 |
| TP4 — Absent Question | NOT FLOWN | Sortie aborted at TP1 |
| TP5 — Expiration/Eviction | NOT FLOWN | Sortie aborted at TP1 |

## Final Sortie Claim

Evolution 7 implementation and preflight verification were completed, but the official memory OFF/ON sortie did not complete because the required answering model became unavailable during the approved flight.

No unsupported PASS result is claimed.
