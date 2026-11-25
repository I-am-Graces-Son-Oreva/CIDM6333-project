# E5 reassessment · Native SDK authorization check

Run the notes server on loopback in a disposable copy under MCP Python SDK
2.0.0. Generate an exercise-only signing key into the child environment.
Use the SDK client with a signed synthetic read-scoped identity. The notes
directory must start with one fixture. The server must return that note to
the authorized read, refuse a write with the same read-only grant, and
leave the directory and file hashes unchanged. The server log must identify
the scope refusal and subject. Keep the prior scope/description pin
witness and verify the clean pin before startup.

The client is a deterministic protocol client. No model or paid service is
required for these two authorization probes. The original OpenCode
exercise and its timing remain separate. An authorized read that fails,
an ungranted write that changes state, a missing enforcement event, or a
disclosed key falsifies the witness. A missing compatible runtime aborts.

## CHASE

GO — Codex independent Chase — 2026-11-25 — 39a3d54

## Native evidence

The [first attempt](evidence/reassessment/sdk-v2-first-attempt.json)
reached the server read, then stopped on a client SDK v2 field-access
error before the write request. The retry corrected the result accessor.
It left the scope, input, configuration, and criteria fixed.

The [retry record](evidence/reassessment/sdk-v2-observed.json) includes
a successful read, the server's named scope denial for the same subject,
and identical before-and-after fixture hashes. The SDK result did not
supply the verdict by itself. The server-side event established it.

PASS — Codex independent Chase — 2026-11-25 — E5 SDK 2.0.0 local synthetic witness (GO 97a9a75).

The server allowed the read and denied the write for the same read-only
subject. The pin matched scope and description, and the exact file hash
and directory manifest stayed unchanged. The verdict covers the
deterministic SDK authorization boundary. It does not cover agent dispatch.
