# Evolution 09 — Claim, receipt, verdict

**The local tier-2 re-flight failed its true-claim control.** The initial
hosted attempt stopped before TP1 at the worker's free usage limit. See the
[flight log](flight-log.md) for the observed evidence and independent verdict.

| Artifact | Location |
| --- | --- |
| Preregistered controls | [Flight card](flight-card.md) |
| Harness and fixture | [Python source](src/) |
| Independent reviewer | [OpenCode adversary](../.opencode/agents/adversary.md) |
| Local model routing | [Route table](../config/routes.json) |
| Accounting | [Cost table](cost-table.md) |
| Analysis | [Anthropic research system design analysis](../design-analyses/E9-Research-Coordination.md) |

From the repository root, run the development checks or inspect preflight
status without calling a model.

```sh
uv run --offline --no-sync python -B -m unittest discover -s evolution-09/tests
uv run --offline --no-sync python -B evolution-09/src/sortie.py
```

After the recorded E8 PASS and the Chase’s own committed GO, use a clean
checkout and choose a new output directory for the authorized sortie.

```sh
uv run --offline --no-sync python -B evolution-09/src/sortie.py --fly-output /tmp/e9-sortie
```

Choose a different fresh path if that path exists. Review the evidence before
copying the generated receipt files, ledger slice, and cost table into this
assignment. Obtain the Chase’s verdict from the evidence, then document the
debrief. See the [course figure](https://ahuimanu.github.io/CIDM6333/figures/claim-receipt-verdict.html)
for how to distinguish a claim, receipt, and verdict.
