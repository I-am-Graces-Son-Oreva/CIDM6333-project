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

## Re-flight Attempt — 2026-11-12

Evolution 7 was re-flown after the OpenCode Big Pickle model became available again in ordinary OpenCode execution.

Before the re-flight:

- `tests/test_e7_memory.py`, `tests/test_e7_isolation.py`, and `tests/test_e6_context.py` passed: 37 tests total.
- `opencode/big-pickle` responded successfully to the ordinary readiness check with `E7 MODEL READY`.
- The previously approved Evolution 7 flight configuration was not weakened or redesigned.
- The existing independent Chase GO remained the governing preflight approval.

A fresh isolated sortie root was created and the Memory-OFF and Memory-ON environments were rebuilt using the approved procedure.

The first official capture attempt entered the isolated Memory-OFF OpenCode process but produced no evidence files and did not return. The process was terminated after confirming that the capture directory remained empty.

A second fresh isolated environment was then created for a bounded diagnostic re-flight. The approved Memory-OFF launcher was invoked with the control question `What is 2 + 2?` and a 60-second timeout.

Result:

`TIMEOUT AFTER 60 SECONDS`

The isolated launcher produced no standard output and no standard error before the timeout.

This establishes that ordinary OpenCode Big Pickle was available while the approved isolated Evolution 7 execution path still could not produce a model response.

The sandbox and isolation controls were not weakened to obtain a successful response.

### Re-flight Verdict

**ABORTED — infrastructure/execution-path blocker remains under the approved isolation configuration.**

This re-flight is recorded without claiming TP1–TP5 PASS. The original Evolution 7 ABORT remains accurate, and this section records the required re-fly attempt.
