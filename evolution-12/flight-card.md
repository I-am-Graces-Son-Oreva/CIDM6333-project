# Sortie 12 flight card

- **Envelope** · Expansion.
- **Claim** · One command restores the exact wheel recorded for a prior release and logs its hash. A mismatching wheel must be refused. The runtime-only fake secret must stay out of published artifacts.
- **System** · Fifth Pick CLI health, uv wheel build, deployment script, local virtual environment, hash-indexed artifact store, release ledger, runbook and human attestation.
- **Substrate** · Clean Git checkout, Python 3.14, uv, no container engine in this flight, no model in release smoke. One scratch deploy root.
- **Dependency** · E11 independent PASS at `833ea8f`.
- **Entry** · Clean checkout, approved flight card, serving ADR, draft runbook, runtime-only synthetic secret and independent GO before release.

| Test point | Observable |
| --- | --- |
| TP1 | Build and release good version 0.1.0. Health reports 0.1.0. Ledger stores wheel SHA-256. |
| TP2 | Build 0.1.1 with a synthetic unhealthy response in a separate clone. Smoke fails and the active version stays 0.1.0. |
| TP3 | Run one timed rollback. Returned SHA-256 equals TP1 and health reports 0.1.0. |
| TP4 | In the scratch deploy root only, overlay different bytes at the recorded artifact path and try rollback. Refuse before install and log failure. Restore scratch bytes from the independently retained original. |
| TP5 | Search wheel bytes and decompressed members, release logs and Git patches for the exact runtime-only marker. Expect zero hits. |
| TP6 | Joseph personally attests to the good release. Record the actual decision after it is made. |

Keep commands, health output, hashes, exit codes and ledger lines. A manual
rollback step, restored hash mismatch, secret leak, missing attestation at
closeout, modified evidence or skipped smoke check falsifies the claim.
Abort on unavailable build or install dependencies. Wheel-only flight,
with no container or model-dependent smoke.

## CHASE

Pending. The independent Chase reviews evidence and exercises the
runbook's rollback in a scratch environment before issuing a verdict.
