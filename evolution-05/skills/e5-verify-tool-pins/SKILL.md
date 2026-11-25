---
name: e5-verify-tool-pins
description: Verify the declared MCP tool descriptions and scopes before the E5 local notes exercise.
---

Run `python3 evolution-05/sortie-05/pin.py` from the repository root.
Stop on a nonzero exit. Compare the changed declaration with the reviewed
manifest before changing the pin. Do not refresh a pin merely to get a
passing result.

Use the same locally supplied `E5_TEST_SIGNING_KEY` for the issuer and
the notes server. Keep it in the process environment and out of outputs.
