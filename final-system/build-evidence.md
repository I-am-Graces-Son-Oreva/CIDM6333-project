# MVP build evidence

Inventory taken from the class submission checkpoint `1b8b549`. The
path query includes source and scripts as well as the pre-relocation
package path. A listed commit establishes repository history. It needs
an independently matching session, ledger event, review, and eval
result to establish a governed build.

## Traceable checkpoint and limits

- `f39cf82` records the offline workflow implementation checkpoint.
  The [committed demo evidence](../final-project/docs/fifth-pick/evidence/course-demo-f39cf82.jsonl)
  provides CLI verification. The [gate record](../final-project/docs/fifth-pick/gates.md)
  records milestone verification. A sanitized build session and corresponding
  per-commit ledger and review chain have not been verified for this commit.
- The [M10 correction witness](../final-project/docs/fifth-pick/gates.md#m10-end-to-end-correction-path)
  records a Controller session, a Reviewer FAIL, one authorized Builder
  dispatch, and a Reviewer PASS with a new artifact hash. It corrected
  a scratch fixture inline. That evidence establishes the bounded
  review loop and does not establish authorship of an MVP source commit.
- A historical milestone PASS can support the specific claim the gate
  tested. A later rerun can verify current behavior. Neither establishes
  that an earlier commit passed every required gate before it landed.

## M1 historical commit receipt

A read-only scan matched completed OpenCode shell events containing
`git commit` against the hashes in the inventory below. One matched:
`8c7d01e`, the M1 control-plane commit. The Git output's abbreviated
hash and subject match the Git object. The
[session projection](evidence/m1-commit-projection.json) preserves the
session ID, tool part ID and source digest. This proves where that
commit command ran. It leaves separate questions about who generated
each change and whether the committed tree had matching review, eval,
and ledger records. The scan did not establish those links.

## M9 historical trace

Commit `60fd576` contains the result-settlement implementation. The
[recovered OpenCode projection](evidence/m9-session-projection.json)
links the original controller and reviewer sessions to selected source
records with part IDs, timestamps, and hashes. No conversation content
was exported. The controller's later record names the commit and the
reviewer record contains the recorded PASS. A completed tool event
independently records the unittest output for 424 tests.

The tool event and Reviewer record precede the commit. The surviving
records do not bind both to the exact committed tree. No matching
per-commit ledger event or separate eval receipt was recovered. This is
a partial trace. The M9 reference in the [gate log](../final-project/docs/fifth-pick/gates.md#m10-phase-2-bounded-correction-pass)
also identifies the original records.

## Source and script commits

Every row below lacks a verified complete per-commit chain. M9 is
the recovered partial trace above. The offline checkpoint and M10
witness have the narrower evidence described above.

| Commit | Recorded summary |
| --- | --- |
| `caa353b` | Show course demo results in bordered CLI tables |
| `ee542f2` | Preregister E12 wheel deployment and hash-checked rollback |
| `eafa3f2` | Polish Fifth Pick review and decision tables |
| `84e260e` | Show four classroom picks with minutes and matchup evidence |
| `3c7a6e9` | Expand the Fifth Pick classroom demo to twelve players |
| `c5999dc` | Align Fifth Pick submission guides and verify date-scoped preflight |
| `be0cda9` | Anchor live snapshots and review to the first official slate tipoff |
| `30b3449` | Require independently verified tipoff for live snapshot series |
| `093f020` | Report exact live lines and phase-bound historical comparisons |
| `5f60189` | Guide operators through the Fifth Pick LIVE workflow |
| `8cb5179` | Archive provider boards and add offline preliminary inspection |
| `74e6a42` | Complete Fifth Pick live workflow safeguards and interrupted-run audit |
| `7f5ed3f` | feat(fifth-pick): refine CLI navigation and review layouts |
| `88dff4a` | Organize CIDM 6333 final project and coursework navigation |
| `eb6615d` | Verify native skill routing and recover Fifth Pick review context |
| `e2d2671` | checkpoint: preserve complete Fifth Pick M1-M10 and LIVE integration progress |
| `d88ccfe` | Verify supporting-source scope and offline proposal replay |
| `3c45276` | Prepare bounded BALLDONTLIE history replay adapter |
| `ebbe484` | Reconcile NBA provider discovery with the official slate |
| `98d4956` | Keep future snapshot windows closed until slate day |
| `da6f059` | Prepare dated NBA discovery and bind verified LIVE aliases |
| `f39cf82` | Finalize Fifth Pick offline workflow and LIVE readiness safeguards |
| `60fd576` | M9: implement result settlement and grading |
| `e3e9b8d` | M8: implement Governance Zero and approval workflow |
| `986ac81` | M7: add T-20 candidate review workflow |
| `35f0243` | M6: add evidence methodology confidence and ranking |
| `429a0db` | M5: add Fifth Pick three-snapshot workflow |
| `796e7d2` | M4: add Odds API source adapter quota and verification |
| `71723ec` | M3: add Fifth Pick identity registry and authorization |
| `ff8b6a4` | M2: add Fifth Pick domain models receipts and storage |
| `8c7d01e` | M1: establish Fifth Pick health-only control plane |
