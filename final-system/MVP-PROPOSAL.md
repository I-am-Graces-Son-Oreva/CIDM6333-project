# The Fifth Pick classroom MVP

This scope was reconstructed during closeout. Joseph recalls receiving
verbal permission to start. The date and any written pre-build approval
remain unverified.

**User.** An NBA fantasy participant applying Joseph’s evening-slate
screening methodology.

**Workflow.** The participant opens the bundled classroom slate,
compares the three timed observations and the selection rationale, and
gets a proposal for Joseph’s review or a NO ENTRY outcome.

The original graduate-triage E0 pitch and the later Fifth Pick PRD are
separate historical records. The [PRD](../final-project/docs/PRD.md)
documents the project change. Instructor confirmation of the substituted
MVP scope is pending.

| Observable criterion | Verification |
| --- | --- |
| The course demo opens without a provider credential and identifies the data as simulated. | Run `sh final-project/scripts/course-demo.sh`. |
| Fixture A displays three snapshot stages and four proposed selections awaiting Joseph. | Script assertions and fixture workflow regression. |
| Fixture B displays zero Snapshot 3 observations and the exact NO ENTRY outcome. | Script assertions and fixture workflow regression. |
| An invalid Snapshot 4 analysis request exits 2. | Input guard in the course demo. |

The closeout rehearsal requires all script assertions and all four bundled
regression checks to pass. This records the present threshold. The
pre-build eval threshold for this scope remains unverified.

[Assurance controls](../final-project/docs/fifth-pick/assurance.md) ·
[Instructor task card](validation.md) · [Build evidence](build-evidence.md)

**Risk and cut line.** Provider coverage and timing can prevent a LIVE
rehearsal. The classroom scope uses bundled fixtures and excludes LIVE
collection, payment, and external account access.
