---
description: Evolution 8 implementer child run
agent: e8-implementer
subagent: true
---

Perform this Evolution 8 implementation task:

$ARGUMENTS

Return ONLY valid JSON matching this contract:
{
  "status": "DONE" or "BLOCKED",
  "summary": "non-empty string",
  "evidence": ["one or more evidence strings"]
}

Do not return prose outside the JSON object.
