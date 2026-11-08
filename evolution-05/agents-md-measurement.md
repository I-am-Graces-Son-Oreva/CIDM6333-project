# AGENTS.md Loaded-Context Measurement

## Earlier Measurement

Source: `evolution-03/agents-md-measurement.md`

The earlier course measurement used `wc -c AGENTS.md`.

- Earlier AGENTS.md size: 852 bytes
- Baseline without AGENTS.md: 8.5K displayed input tokens
- With AGENTS.md: 8.7K displayed input tokens
- Observed loaded-context increase: approximately 0.2K displayed input tokens
- Earlier /init-generated AGENTS.md comparison: 1,923 bytes

## Evolution 5 Re-measurement

The Evolution 5 revision keeps persistent rules in AGENTS.md and moves the multi-step Sortie procedure to:

`.opencode/skills/sortie-security/SKILL.md`

Measured with the same `wc -c` method used previously:

- Earlier AGENTS.md: 852 bytes
- Evolution 5 AGENTS.md: 1483 bytes
- Evolution 5 character count: 1481 characters
- Required maximum: 4,000 characters
- Character-limit result: PASS

## Comparison

AGENTS.md is larger than the earlier 852-byte version because Evolution 5 adds persistent MCP security rules.

However, the detailed TP0-TP4 procedure is not kept in the always-loaded AGENTS.md. It is stored in the OpenCode skill so the longer procedure can be loaded only when that workflow is needed.

The earlier displayed loaded-context measurement was 8.5K tokens without AGENTS.md and 8.7K with it. I am preserving those observed values rather than inventing a new token count from a different measurement method.
