# Design Analysis · GitHub Actions-based Copilot cloud agent

| Component | Observation |
| --- | --- |
| Foundation | The coding model is mediated by GitHub's agent service. |
| Perception | Repository state and the assigned task provide context. |
| Memory | The repository and PR retain artifacts outside the model context. |
| Reasoning | The agent proposes edits to satisfy the issue. |
| Planning | A session can inspect the task and break it into changes. |
| Tools and orchestration | The Actions-based environment works in one repository context and can use setup and compute configuration. That bounds where it works while leaving a separate review surface. |
| Runtime and operations | The service executes in GitHub's environment. Availability, execution, and quota depend on the account and organization settings. Local release timing is measured separately. |
| Evaluation and feedback | A proposed diff and test output are review evidence. A deployment claim still needs an actual health result and a release receipt naming the deployed artifact. |
| Governance and human interface | A user delegates a task and reviews the result. In The Fifth Pick the release and human attestation are separate ledger events. |

The separation between a proposed change and an accepted change makes
the PR an auditable boundary. It costs an extra review step and protects
against a session reporting completion without evidence of what shipped.
[GitHub Copilot documentation, reviewed November 24, 2026](https://docs.github.com/en/copilot/concepts/copilot-surfaces/copilot-on-github)

**Judgment loop** · Require release acceptance separately, prioritize
artifact identity and human control, budget an extra check, address
Appendix C mode 4 (skipped verification), and copy the review boundary
into the local release attestation step and hash-bound ledger.
