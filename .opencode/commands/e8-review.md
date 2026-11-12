---
description: Evolution 8 independent reviewer child run
agent: e8-reviewer
subagent: true
---

Independently review this Evolution 8 handoff and the repository evidence:

$ARGUMENTS

Return ONLY valid JSON matching this contract:
{
  "status": "PASS" or "FAIL",
  "summary": "non-empty string",
  "findings": ["finding strings"]
}

PASS may use an empty findings list.
FAIL must contain at least one finding.

Do not return prose outside the JSON object.
Do not modify any files.
