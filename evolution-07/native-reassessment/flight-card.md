# E7 native reassessment · Local route

Keep the earlier hosted ABORT and alternate-harness PASS. Reuse the native
E7 Seatbelt profiles, thin retrieval client and read-denial probes. Replace
only the provider in disposable launch configurations with local Ollama
Llama 3.2 3B. Use fresh OpenCode 1.18.20 sessions and an isolated scratch
retrieval store. Never send the fixture beyond loopback or publish its text.

OFF must receive no retrieval and say the requested synthetic fact is
unavailable. ON must invoke the thin client and report the exact stored
fact with its ID and source. The matching recall ledger must report a hit
at or above 0.30. The condition profiles must pass the existing denial
probes, and the ON service must be down during OFF. Record actual proof
flags and tool status without publishing raw tool content.

The isolated arithmetic, absent and eviction controls remain separately
identified in the earlier coursework evidence. This witness covers
native OFF and ON. Missing isolation, missing authorized retrieval, a
fact in OFF, or an unsupported model answer fails. Missing route or
timeout aborts.

## CHASE

Pending.

## Egress amendment

NO-GO — Codex independent Chase — 2026-11-25 — 4bb87b7.
The historical filesystem profile alone does not restrict outbound traffic.

Retain its filesystem denials and append a scratch-only outbound network
deny. Allow only loopback TCP to the local model port and, in ON only,
the thin-client service port. Restrict the ON shell tool to the exact
fixture query. Use isolated XDG configuration, cache and state directories,
disable sharing and external plugins, and pass no provider credentials.
Recheck isolation after adding the rules. No run before fresh GO.

GO — Codex independent Chase — egress — 2026-11-25 — 22e5f44

## Attempt record and preflight repair

The first launch aborted at profile compilation. Seatbelt requires
`localhost` in its port-specific rule. With that spelling corrected,
the [first model attempt](attempt-1.json) completed neither condition's
acceptance checks. File probes reported accessible artifacts from the
same scratch prefix, and Llama's ON Bash call was rejected by the tool
schema before dispatch. No matching retrieval receipt was recorded.

The retry uses a scratch parent outside the historical `e7-*` artifact
discovery pattern, preserves explicit denied sibling paths, and fails
closed before launching either condition if its filesystem probe fails.
The prompt tells the model to omit optional Bash arguments, including
null values. This does not change the expected OFF/ON outcomes or the
file and network policy. No retry before fresh GO.

GO — Codex independent Chase — retry — 2026-11-25 — 3b34028

## ON-only schema repair

The [second attempt](attempt-2.json) verified isolation in both conditions.
OFF reported the fact unavailable and made no tool call. ON attempted
two native Bash calls but both were rejected because Llama emitted null
for the numeric timeout. No retrieval reached the service.

Keep the passing OFF evidence. Re-run ON alone using the same model,
fixed command and policies. The prompt supplies a numeric timeout of
30,000 ms and the exact scratch working directory, leaving the requested
command and success criteria fixed. No further run before a fresh GO.

GO — Codex independent Chase — on-only — 2026-11-25 — 9b320d8

## Native outcome

The [OFF control](attempt-2.json) passed 75 isolation probes, made no
tool call and reported the fact unavailable. The [ON retry](attempt-3.json)
passed 78 isolation probes. Three completed Bash calls used the fixed
client and the [sanitized projection](on-retry-projection.json) records
three returns of `m-9001`, each with score 0.6717. The model's final
answer omitted the exact fact, record ID and source. ON therefore failed
the answer criterion despite the successful process exit and verified
retrieval. The [runner](run.py.txt) preserves the executed source for review.

**FAIL — independent Codex Chase — 2026-11-25 — ON-only retry (GO `e0e3a9c`).**
The receipt IDs and scores establish retrieval above the 0.30 threshold.
The answer omitted all three required fields. The earlier OFF PASS stands.

### Native ON rerun with Qwen

Keep the prior OFF control and rerun ON with local Qwen3 4B in OpenCode
1.18.20. Preserve the fixed retriever command, sandbox profile, preflight
probes and exact fact, ID and source criteria. Disable thinking to keep
the answer within the output budget. The fact and source must come from
the retrieved record. Publish a sanitized projection only.

GO — Codex independent Chase — 2026-11-25 — Qwen rerun at `458ceac`.
