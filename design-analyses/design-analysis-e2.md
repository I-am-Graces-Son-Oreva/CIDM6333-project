# Design Analysis — Evolution 2

## OpenCode Orchestrator-Workers vs. LangGraph Orchestration

Evolution 2 asks who owns the loop when one agent delegates work to other agents. For the Graduate Application Identity-Assurance and Triage System, I used OpenCode's orchestrator-workers pattern. The `grad-triage` primary agent owns the workflow and delegates narrow responsibilities to `evidence-reviewer` and `triage-summarizer`.

I compared this design with LangGraph because LangGraph can also represent multi-agent and multi-step workflows, but it places more emphasis on an explicit graph of nodes, state, and transitions.

## Nine Components

| Component | LangGraph Orchestration | OpenCode Orchestrator-Workers | Judgment |
|---|---|---|---|
| 1. Goal | A graph can represent a workflow toward a defined result. | The primary agent receives the goal and coordinates workers toward the bounded triage result. | OpenCode is sufficient for this project's small workflow. |
| 2. Reasoning | Reasoning can be distributed across graph nodes or agents. | The primary decides when to delegate, while workers reason about narrow assigned tasks. | Narrow worker roles reduce responsibility overlap. |
| 3. Action | Nodes and tools perform actions according to graph transitions. | The primary uses the `task` tool to delegate work to subagents. | Delegation is visible as a tool action that can be tested. |
| 4. Observation | State and node outputs can be observed and passed through the graph. | The primary receives a worker result before making the next delegation. | The workflow can depend on the previous worker completing. |
| 5. Tools | Tools can be attached to graph nodes or agents. | OpenCode supplies the `task` tool for subagent delegation. | The existing harness already provides the tool needed for this pattern. |
| 6. State / Context | LangGraph supports explicit shared or persistent graph state. | Each delegated worker operates in its assigned context and returns a result to the primary. | OpenCode is simpler for this bounded two-worker workflow. |
| 7. Control | Graph edges and routing logic control execution order. | The primary-agent instructions define worker order, while `permission.task` restricts which subagents may be called. | OpenCode combines prompt-level workflow order with a harness-level delegation gate. |
| 8. Evidence | Graph execution can be instrumented through application-level tracing and logs. | OpenCode sessions can be exported with `--sanitize`, preserving tool-call structure and status. | The course requires sanitized OpenCode evidence, so the harness directly supports the sortie. |
| 9. Halt | The graph stops when its terminal condition is reached. | The primary stops after the required workers return and the bounded final response is produced. | The workflow has a clear completion point without adding another orchestration framework. |

## Judgment Loop

**Decision:** Use OpenCode orchestrator-workers for the E2 workflow instead of adding LangGraph.

**Characteristics privileged:** Simple delegation, narrow worker responsibilities, visible task calls, explicit worker order, permission-controlled delegation, and evidence that can be exported from the same harness used for the sortie.

**Cost:** The orchestration depends partly on primary-agent instructions rather than a separately encoded graph. Sanitized exports also redact task inputs, outputs, titles, and metadata, which can limit what a single export independently proves about worker identity.

**Failure mode:** The primary could skip a worker, call workers in the wrong order, perform the workers' responsibilities itself, or attempt to delegate to an unauthorized subagent.

**Preservation mechanism:** Define narrow subagents, state the required order in `grad-triage`, deny task delegation by default, explicitly allow only `evidence-reviewer` and `triage-summarizer`, use sanitized session exports, and have Chase judge the committed evidence.

## Evidence from E2

TP1 showed the primary completing two sequential `task` calls followed by a final response. The live run showed Evidence-Reviewer first and Triage-Summarizer second. The sanitized export preserved the two sequential completed task calls but redacted their worker identities, and this limitation is recorded in the flight log.

TP2 attempted delegation outside the allowlist. The sanitized export preserved a failed `task` call and the permission error showing a default deny for `task` plus explicit allows for `evidence-reviewer` and `triage-summarizer`.

Chase reviewed the committed evidence and recorded:

`CHASE — Chase — 2026-11-09 — PASS`

## Conclusion

For this project, OpenCode orchestrator-workers gives me enough structure without adding another orchestration framework. E2 also showed that orchestration is not only about telling agents what order to follow. The harness can restrict which workers the primary is allowed to call, giving the workflow a permission boundary that can be tested.
