# Sortie 12 flight log

The independent Chase gave GO before the trial at `d07383d`. The trial
used two scratch checkouts and a disposable uv deployment. It built
the release wheel without networking. The deliberately broken wheel
was built from the same base commit with the recorded fixture patch.

| Point | Observed evidence |
| --- | --- |
| TP1 | Wheel release exit 0. Health reported `{"package":"fifth_pick","status":"ok","version":"0.1.0"}`. |
| TP2 | Candidate 0.1.1 exited 1 with `health smoke check failed`. Health still reported 0.1.0. |
| TP3 | One rollback command exited 0 in **1.866413 s**. Its SHA-256 equals the TP1 release. Health reported 0.1.0. |
| TP4 | Rollback exited 1 with `stored release hash mismatch` before installation. The active environment remained healthy. |
| TP5 | Exact runtime marker search returned 0 matches. |
| TP6 | Pending Joseph's personal attestation. |

Verified original and restored wheel SHA-256:
`015d9b3f3522e1e8e87978c5f4fec6c325d4752893c2b13d05a4b2bc0ff14c34`.

[Commands and captured outputs](evidence/commands.json) ·
[Actual ledger lines](evidence/release-ledger.jsonl) ·
[Planted defect](evidence/planted-defect.txt) ·
[Marker check](evidence/marker-check.json)

The installed wheel also displayed the offline Demo Mode menu in a
pseudo-terminal outside the source tree and exited 0 on Q. No paid
provider calls were required.

## Chase and closeout

The full sortie verdict and final release remain pending TP6.
