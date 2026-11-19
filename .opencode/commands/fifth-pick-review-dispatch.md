---
description: Confirm one M2 review correction receipt before the controller dispatches Builder
---

Arguments must be one JSON object with exactly these fields:

```json
{
  "schema_version": 1,
  "run_id": "M2-safe run identifier",
  "subject": "the same stable review subject",
  "initial_artifact_sha256": "the original review material digest",
  "current_artifact_sha256": "the artifact digest at the correction boundary",
  "revision": 1
}
```

Before dispatching the Builder, require the adapter to confirm the newly persisted receipt with `state` `REVISION_REQUIRED`, `correction_count` `1`, `correction_available` `false`, and the single exact `-02-revision_attempt` key for that cycle. The adapter derives the expected cycle from the requested run ID, subject, and initial artifact digest. If the response is missing, malformed, mismatched, or STOPPED, do not dispatch the Builder. Escalate to Joseph.

Only the response that newly persisted the receipt authorizes launch. Repeating a confirmation returns STOPPED. If interrupted and unsure whether Builder launched, stop and escalate to Joseph.

This command does not dispatch Builder or change tool permissions. The controller performs the dispatch only after confirming the receipt response.

For an `nba-proposal-vN` subject, have Builder identify the exact existing
candidate keys to remove and give a reason. The Controller applies only that
bounded correction through `fifth-pick review-correct --run-id RUN_ID --remove
CANDIDATE_KEY --reason REASON`. Submit the returned revision-1 envelope to the
Reviewer on the same cycle. An exact corrected PASS is required before Joseph
can approve. Route second FAIL, CONCERNS, an unsupported correction, or an
uncertain launch to Joseph. Never edit the proposal or review receipts directly.
