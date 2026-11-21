# Reproduce the course demonstration

From the repository root with the existing environment available:

```zsh
uv run --offline --no-sync fifth-pick menu
```

In **Demo Mode**, select **Analyze NBA Slate** twice to collect the first two
fictional observations. Inspect **View Candidates and Rankings** and confirm
the watchlist is provisional. Select **Run T-20 Review** and inspect **View
Final Recommendations**. An attempt to record results before explicit approval
stops. Open **Approve / Reject / Modify**, review the exact lines, and explicitly
choose the synthetic demo decision. Then **Record Results** and inspect
**View Audit and Receipts**. No provider key or network access is needed.

The deterministic CLI test demonstrates the whole path, including an unresolved
identity, an unauthorized grant, a reviewed projection of 9.5, HIGH confidence,
STILL STRONG, and a fixture result bound to the approved candidate key:

```zsh
uv run --offline --no-sync python -m unittest -v tests.test_fixture_cli.FixtureCliTests.test_complete_workflow
```

The product matrix and gate record explain the separate LIVE and M10
qualification boundaries. The release candidate excludes local credentials,
tool caches, installed environments and operational runtime artifacts.

## Clean-checkout demonstration — commit f39cf82

The `course-closeout-f39cf82` fixture run loaded the bundled producer
responses, showed a provisional watchlist after slots 1 and 2, then reviewed
the actual fixture movement through slot 3. The proposed projection was
`9.5`, confidence `HIGH`, and status `STILL STRONG`. An initial settlement
attempt exited 1. Explicit fixture approval, synthetic settlement, audit
and evaluation each exited 0. The [30-receipt fixture trail](evidence/course-demo-f39cf82.jsonl)
has SHA-256 `7627c5e3375a14775aa980217082f23f945781f3a48af72bb23d56e3285b5182`.
The approval and outcome are demonstration records only.

## One-command professor rehearsal

From a fresh clone, run `uv sync --locked` once. Initial installation may
need the internet to obtain dependencies. A warm uv cache and an installed
compatible Python allow offline setup with `uv sync --locked --offline`.
After setup the demonstration uses local files and needs no credentials,
provider calls, or OpenCode runtime.

```sh
sh final-project/scripts/course-demo.sh
```

The script runs the standalone CLI against the bundled synthetic inputs.
Fixture A shows that snapshot 4 is invalid, ambiguous identity and a
missing grant block lines, and the three timestamped snapshots narrow a 12-player, four-game slate to three proposals.
Luka Doncic’s PrizePicks assists, Jayson Tatum’s Underdog PRA, and Joel Embiid’s
PrizePicks points await Joseph. Kevin Durant’s line disappears at T-20 and the fourth
slot stays open. Fixture B removes all provider lines from a temporary copy of
the third input. The T-20 check then produces `NO ENTRY RECOMMENDED TODAY.`
The command prints both run IDs and audit commands. A separate CLI process
reconstructs the bounded review checkpoint from the first run ID. Each run is retained
under ignored `var/fifth-pick/runs/`.

The final regression replay exercises the Python review bridge with a test
verdict, settlement gating, four- and five-slot ceilings, and no refill.
The direct CLI fixture reports `AWAITING_JOSEPH`. The separate native
review reports `AWAITING_REVIEW`. Neither a native verdict nor an owner
decision is recorded in those direct CLI runs. For the independent native Reviewer route and its
qualifications, consult the [harness](harness.md) and [gate record](gates.md).

Open the [user guide](user-guide.html) or follow the
[November 24 presentation walkthrough](presentation.md).
