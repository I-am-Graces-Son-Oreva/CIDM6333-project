# Evolution 6 — OpenCode Session A Budget Measurement

Declared turn budget: **8,000 tokens**

Declared 80% threshold: **6,400 tokens**

Harness: **OpenCode 1.18.20**

Provider/model: **opencode / big-pickle**

This table is derived from OpenCode's exported provider usage fields.
The raw export is intentionally not committed because it may contain repository contents.

| Call | User turn | Input | Output | Reasoning | Cache read | Cache write | Provider total | Budget % | Result |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---|
| 1 | 1 | 8196 | 58 | 0 | 1792 | 0 | 10046 | 126% | OVER |
| 2 | 1 | 2070 | 34 | 0 | 9984 | 0 | 12088 | 151% | OVER |
| 3 | 2 | 85 | 59 | 0 | 12032 | 0 | 12176 | 152% | OVER |
| 4 | 2 | 1421 | 39 | 0 | 12160 | 0 | 13620 | 170% | OVER |
| 5 | 3 | 82 | 57 | 0 | 13568 | 0 | 13707 | 171% | OVER |
| 6 | 3 | 1676 | 28 | 0 | 13696 | 0 | 15400 | 192% | OVER |
| 7 | 4 | 88 | 51 | 37 | 15360 | 0 | 15536 | 194% | OVER |
| 8 | 5 | 81 | 24 | 0 | 15488 | 0 | 15593 | 195% | OVER |
| 9 | 6 | 146 | 44 | 26 | 15488 | 0 | 15704 | 196% | OVER |
| 10 | 6 | 178 | 95 | 32 | 15616 | 0 | 15921 | 199% | OVER |
| 11 | 6 | 565 | 55 | 83 | 15872 | 0 | 16575 | 207% | OVER |
| 12 | 6 | 308 | 91 | 117 | 16512 | 0 | 17028 | 213% | OVER |

## Observation

Session A contained **6 user turns** and **12 actual model calls**.

Every assistant/model call in the export contained provider token usage.

The first model call already exceeded the declared 8,000-token budget. Therefore this measurement does not claim that OpenCode compacted at our declared threshold. The declared budget is our design budget, not evidence of the harness's internal compaction limit.

The Sprint compaction mechanism is tested separately in our own E6 context-engineering implementation.
