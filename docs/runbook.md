# Fifth Pick deployment runbook

## What runs where

The wheel runs the Python CLI in an isolated local uv virtual environment.
Examples use a POSIX shell from the repository root and require Python, uv,
and local cached dependencies. `DEPLOY_ROOT` is an absolute path outside
the source checkout. The installed executable is
`"$DEPLOY_ROOT/current/bin/fifth-pick"`.

## Release

In a clean checkout, build with `uv build --offline --wheel`. Release the
candidate with the following command, setting `WHEEL`, `VERSION` and
`BUILD_COMMIT` to the artifact, version and source commit.

```sh
python3 deploy.py --root "$DEPLOY_ROOT" release "$WHEEL" --version "$VERSION" --commit "$BUILD_COMMIT"
```

The command prints and appends a JSON event. A candidate that fails health
or cannot load its packaged configuration leaves the current pointer intact.

## Health

```sh
"$DEPLOY_ROOT/current/bin/fifth-pick" health
```

Expect JSON with package `fifth_pick`, status `ok` and the installed version.

## Rollback

```sh
python3 deploy.py --root "$DEPLOY_ROOT" rollback --version 0.1.0
```

The command verifies archived bytes before reinstalling. Check the returned
hash against the successful release event and rerun health. The measured
rollback took 1.866413 seconds in the isolated E12 trial. See the
[release ledger](../evolution-12/evidence/release-ledger.jsonl).

## Limits and budgets

Deployment uses offline package installation. Health and configuration
smoke checks call no model or sports data provider. The installed Demo
Mode runs with bundled synthetic fixtures.

## Secrets

The release exercise uses a fake marker injected only into the runtime
environment. Real provider credentials belong in the operator's local
environment. Rotate a compromised key through the provider and replace
the local value. Search emitted evidence and artifacts for the exact
marker before publishing.

## Known gaps

This runbook covers the isolated wheel path. LIVE evidence and provider
prerequisites remain documented in the
[Fifth Pick operator runbook](../final-project/docs/fifth-pick/runbook.md).
An accountable human must separately attest to the final release.
