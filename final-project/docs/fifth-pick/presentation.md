# The Fifth Pick course walkthrough

Tuesday, November 24, 2026

## Opening

“The Fifth Pick is a Python command-line assistant for evaluating NBA fantasy lines. It checks who the player is, whether I authorized that exact category and direction, and whether recent evidence supports the line. I make the final decision. Sometimes the right output is `NO ENTRY RECOMMENDED TODAY.`”

## Run the offline demonstration

From the repository root, in the prepared project environment:

```sh
sh final-project/scripts/course-demo.sh
```

Use the following sequence as a roughly five-minute speaking guide. Every line, judgment, approval, and result shown in the demonstration belongs to a synthetic fixture run.

| Time | What to show | What to say |
| --- | --- | --- |
| 0:00–0:45 | The problem and the Demo Mode label | An assistant should explain the basis for a selection and stop when evidence or authorization is missing. PrizePicks and Underdog are separate boards. |
| 0:45–1:45 | Invalid fourth snapshot and candidate refusals | Each game has three observation slots. The fixture audit also shows an unresolved identity and an unauthorized category or direction. |
| 1:45–2:45 | Third observation, proposal, and review state | The synthetic fixture uses its recorded game clock. A new LIVE series counts back 20 minutes from the first official NBA tipoff on the slate. Show fixture Luka Doncic, PrizePicks assists HIGHER, and movement from 8.5 to 9.0 to 9.5. Point to the `HIGH` judgment and `STILL STRONG` T-20 result. The fixture proposal reports `AWAITING_JOSEPH` and the separate native review status reports `AWAITING_REVIEW`. Demo decisions can be recorded without a native dispatch. A separate CLI process reloads the checkpoint from the run ID and reports that dispatch is unauthorized. |
| 2:45–3:45 | Receipts and the missing-third-observation scenario | The receipts show what happened. When the third observation is missing, the fixture produces zero picks and `NO ENTRY RECOMMENDED TODAY.` |
| 3:45–5:00 | Automated regression replay | The replay checks a synthetic review verdict, refusal to settle before approval, explicit fixture approval, and a synthetic result. It also checks the four- and five-pick caps and that removals leave slots empty. One synthetic HIT exercises settlement. It cannot establish a hit rate. |

For a manual rehearsal, use `uv run --offline --no-sync fifth-pick menu` and the [menu walkthrough](demo.md). The menu shows the provisional watchlist after the first two observations. The [archived fixture trail](evidence/course-demo-f39cf82.jsonl) documents a prior clean-checkout demonstration at commit `f39cf82`.

## Optional native harness evidence

On a host configured for OpenCode 1.18.20, run:

```sh
opencode debug skill
opencode debug agent fifth-pick-reviewer
```

Look for the review adapter activation marker, the four Fifth Pick skills, and
`read` and `skill` exposed while `bash`, `edit`, `write`, and `task` are
withheld. The recorded Planner exercise completed two native skill calls with
a scripted loopback model response. For actual Reviewer and Builder model
execution, use the historical M10 receipts and their qualification.
[Native checks](harness.md#professor-alignment-native-checks-and-fresh-session-recovery)

## Questions to be ready for

- **Can it evaluate an actual NBA slate?** The approved fantasy-board route is The Odds API `us_dfs`. LIVE selection still needs verified event and player identities and authorized supporting evidence. A reported BALLDONTLIE trial accepted Teams and Players requests, while the Stats request returned HTTP 401. Documented endpoints alone cannot establish access or coverage. Official injury-document acquisition and the evidence needed to reach a positive LIVE T-20 proposal also remain unverified. Paid board actions require Joseph's explicit scoped budget. [Source verification](source-verification.md) · [Product completion](product-completion.md)
- **Who makes the decision?** Governance Zero routes work from Joseph through the Controller, Planner, Builder, independent Reviewer, and Controller back to Joseph. Joseph alone makes the explicit decision. The application performs no entry submission or wagers. [Agent guidance](agent-guidance.md)
- **What did the native Reviewer check establish?** M10 was accepted with qualification for OpenCode 1.18.20. Both native write routes were withheld and read-oriented tools were exposed. Request-to-denial behavior is unverified for both routes, so correlated Route A denial evidence remains blocked. Live second-FAIL/CONCERNS escalation is unverified and has offline regression coverage. [Assurance](assurance.md) · [Gate record](gates.md)
