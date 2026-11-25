# Class submission cold rehearsal

Codex rehearsed the task card from a clean, detached checkout of
`b12189aa44ae5e1a5f01361d31141d69ec71ef49` with a new Python 3.14.7
environment. The instructor trial and grading freeze are pending.

## Setup and eval

The first full offline sync missed a locked Ruff wheel. The rehearsal
used the locked runtime dependencies in a separate fresh checkout with
a preseeded cache:

```sh
uv sync --locked --offline --no-default-groups
uv run --offline --no-sync python evals/gate.py --output /tmp/fifth-class-eval
sh final-project/scripts/course-demo.sh
```

The offline eval passed all 12 cases with zero regressions.
[Eval delta](evidence/class-cold-eval.json)

The [demo output](evidence/class-cold-demo.txt) shows four selections
awaiting Joseph in Fixture A, and `NO ENTRY RECOMMENDED TODAY.` in
Fixture B after zero observations at Snapshot 3. All four bundled
regression checks passed. The full `uv sync --locked` also installed
the development and legacy dependencies with network access.

## Release candidate and rollback

`uv build --offline --wheel` built version 0.1.0 from the pinned commit.
Its SHA-256 is
`015d9b3f3522e1e8e87978c5f4fec6c325d4752893c2b13d05a4b2bc0ff14c34`.
The bytes match the previously attested E12 wheel. The changed
classroom script runs from the checkout and is outside the wheel.

The first deployment cache could not complete the offline install.
Using the preseeded E12 cache in the disposable deployment, release
and rollback both exited 0 with the same commit and SHA-256. The
installed CLI reported healthy version 0.1.0 before and after rollback.
The [deployment ledger](evidence/class-candidate-deployment.jsonl)
retains the failed attempt and both successful events. The local
rehearsal did not publish a GitHub release.
