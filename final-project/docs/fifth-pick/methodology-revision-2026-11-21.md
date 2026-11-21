# Methodology revision approved by Joseph on November 21, 2026

This decision supersedes mandatory player availability, injury-report,
teammate-absence, and role/minutes evidence requirements in the current
recommendation workflow. Existing design and acceptance records describe
the earlier policy and remain historical evidence.

- M6 can qualify a candidate without those categories. M7 and the Controller
  submission enforce current game context and the existing freshness rules
  for facts actually cited. Uncited optional context does not satisfy a
  required category. Missing context may be reported as a limitation.
  Supplied contradictions, critical evidence gaps, and prohibited sources
  still fail their existing checks.
- HIGH still requires distinct important, aligned evidence, sufficient
  support, and no disqualifying conflict or gap. MEDIUM still requires
  sufficient evidence and a disclosed meaningful risk or gap. Counts from
  a historical sample supply no confidence or probability by themselves.
  The separate Senior LOWER safeguard still requires cited blowout or
  reduced-minutes support and disclosure. A role report is one possible
  way to supply that support.
- The revision leaves the frozen player grants, Senior tier, genuine
  three-snapshot workflow, T−25 through T−20 Snapshot 3 window, T−20 through
  T−15 LIVE review, independent Reviewer and Controller, Joseph's final
  authority, caps, no-refill, and zero-pick rules in force. No source or
  spending permission follows from this decision.

## Replay against a captured platform line

The read-only `history-compare` command reopens the exact candidate and
snapshot from the receipt-bound ledger. It applies the existing category
calculation to each structurally verified DunkAPI package and compares the
result to the unmodified recorded projection. It counts Higher, Lower and
Push, and counts matches to the candidate's authorized direction. There is
no recommendation, promotion, confidence, or LIVE evidence receipt.

```sh
.venv/bin/fifth-pick history-compare --run-id "$RUN" --candidate-key "$KEY" --snapshot 2 \
  --archive "$ARCHIVE_DIRECTORY" "$PINNED_MANIFEST_SHA256"
```

Repeat `--archive DIRECTORY SHA256` for additional games. Each directory
holds the existing Stage 3 `manifest.json`, `identity.json`,
`corroboration.json`, `coverage.json`, `correction.json`, and the
`page-<offset>.json` files. A successor version includes
`previous-manifest.json`. Supply the manifest digest from a trusted channel.
The comparison uses the recorded snapshot's retrieval time as the as-of
cutoff and a conservative 30-minute limit for both coverage and correction
checks in this read-only command. Synthetic archives require a fixture
board. External archives require a LIVE board, stay external-unverified,
and have no path into LIVE scoring. Separate one-game packages do not
establish season or last-eight completeness.

## Executable synthetic demonstration

```sh
.venv/bin/python -B -m unittest -v \
  tests.test_fixture_cli.FixtureCliTests.test_revised_history_pipeline_offline
```

This uses isolated fixture transport, eight separately replayed synthetic
games, supplied fixture Controller assessments at slots 2 and 3, the T−20
review, a synthetic independent Reviewer PASS through the review bridge,
and an explicit test APPROVE through the decision CLI. It uses no injury,
availability, teammate-absence, or role/minutes input. It exercises
production interfaces without claiming a real assessment or native LIVE run.

## Remaining LIVE work

Obtain one exact historical game with lawfully retained provider bytes and an
independent record of actual start and completion. Verify the identity,
coverage and dated correction evidence before seeking approval for the
production source and access method. Before making a qualifying history
claim, establish complete coverage for its sample scope. Connect the
authorized replay and supported directional facts to the existing M6
evidence admission rules. Keep contextual game evidence current and retain
all review and decision receipts. The standalone comparison grants no
production authority.
