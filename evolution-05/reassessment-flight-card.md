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
