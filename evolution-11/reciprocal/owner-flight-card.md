# Reciprocal validation flight card

**Target owner** · Codex agent e6_native_postflight, acting as a separate
exercise partner. This is a synthetic coursework target.

**Scope** · Run `python3 -B review_record.py RECORD.json` in this scratch
directory. Supply synthetic fixtures only. The validator reads one JSON
record and returns one JSON status line. No network or file writes are
needed. Compare fixture and target hashes after execution.

| Requirement | Observable |
| --- | --- |
| P1 · Complete evidence | A missing or blank source, evidence text, or digest returns `BLOCKED` with `INCOMPLETE_EVIDENCE`, exit 1. |
| P2 · Consistent evidence | For a complete record, the reported SHA-256 must equal the SHA-256 of the UTF-8 evidence text. A contradiction returns `BLOCKED` with `CONTRADICTORY_EVIDENCE`, exit 1. A matching complete control returns `ACCEPTED`, exit 0. |

**Falsifiers** · Any blocked case accepted, an inconsistent status and exit
code, a missing receipt, or a change to a reviewed file.

**Chase** · The reviewer supplies two probes and records GO before running
them. Retain command output and exit status, then give a verdict against
these observables.
