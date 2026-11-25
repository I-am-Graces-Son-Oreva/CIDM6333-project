# Instructor validation task card

## Hand this section to the instructor

**Role.** An NBA fantasy participant who wants to apply a consistent
screen before deciding whether to enter a slate.

**Goal.** Inspect a synthetic slate, explain one proposed selection
from its evidence, and confirm what happens when the provider has no
lines at the final checkpoint.

**Starting state.** The class repository is checked out and its Python
dependencies are installed. Open a terminal at the repository root and run:

```sh
sh final-project/scripts/course-demo.sh
```

All projections and observation times in this exercise are simulated.
The exercise requires no provider key, OpenCode session, or payment.

| Task | Observable success |
| --- | --- |
| Inspect the first slate’s snapshots | The first table has three numbered stages and observation counts of 15, 15, and 14. |
| Inspect the proposed slate | Four selections appear with platform, market, direction, line, and T−20 status. The proposal awaits Joseph’s decision. |
| Explain a selection using the supporting table | Cite the three snapshot lines and one stated reason for a Higher or Lower selection. |
| Inspect the second slate and locate its audit | Snapshot 3 shows zero observations. The outcome reads `NO ENTRY RECOMMENDED TODAY.` and an audit replay command appears below it. |

## Observer record

The instructor trial is pending. The existing offline rehearsal is
verification evidence. Record the trial here only after it occurs.

| Field | Record at the trial |
| --- | --- |
| Date and exact tested commit | Pending |
| Instructor’s actions and observed output | Pending |
| Result for each task and any unexpected behavior | Pending |
| Whether assistance was needed | Pending |
