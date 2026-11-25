# Reciprocal probes and GO

Reviewer: Codex acting as reciprocal Chase with Joseph’s authorization.
Target owner: independent Codex agent. Separate role and frozen target at d7c5678.

- [A4-incomplete](A4-incomplete.json) · P1 · missing evidence text must return INCOMPLETE_EVIDENCE, exit 1. SHA-256 `d1d9fff759cc06c8d4c2edb3e8178ec27f82a68a3cf3b5dda0bc45a70edc2a5b`.
- [A5-contradiction](A5-contradiction.json) · P2 · digest of a different synthetic input must return CONTRADICTORY_EVIDENCE, exit 1. SHA-256 `6a9a2447df8d3d73879684020bc3d32c02f46ebec0308bf7352c7bc8bcba1f4a`.
- [control](control.json) · Positive control · the matching digest must return ACCEPTED, exit 0. SHA-256 `26e194b6a755dc3626194057c9b65f1f085df5cc0601388c1dcc7fda669417de`.

GO — Codex reciprocal Chase — 2026-11-25 — d7c5678.
The inputs exercise the exact required validation paths, with a positive
control to distinguish legitimate refusal from an always-block result.
Preserve output, exit codes and hashes before and after.
