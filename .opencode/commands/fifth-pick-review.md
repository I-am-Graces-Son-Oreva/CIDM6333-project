---
description: Fifth Pick independent read-only reviewer run
agent: fifth-pick-reviewer
subagent: true
---

Independently review the Fifth Pick milestone evidence:

$ARGUMENTS

Return ONLY valid JSON matching this contract:
{
  "status": "PASS" or "FAIL" or "CONCERNS",
  "summary": "non-empty string",
  "findings": ["finding strings"]
}

PASS may use an empty findings list.
FAIL and CONCERNS must contain at least one finding.

Do not return prose outside the JSON object.
Do not modify any files.
