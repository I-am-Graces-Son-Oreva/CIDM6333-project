# Reproduce the course demonstration

From the project directory with the existing environment available:

```zsh
uv run --offline --no-sync fifth-pick menu
```

In **Demo Mode**, select **Analyze NBA Slate** twice to collect the first two
fictional observations. Inspect **View Candidates and Rankings** and confirm
the watchlist is provisional. Select **Run T-20 Review** and inspect **View
Final Recommendations**. An attempt to record results before explicit approval
stops. Open **Approve / Reject / Modify**, review the exact line, and explicitly
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
