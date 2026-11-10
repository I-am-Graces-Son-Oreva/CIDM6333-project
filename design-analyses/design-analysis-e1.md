# Evolution 1 Design Analysis

## ReAct Loop vs. OpenCode Agent Loop

### Context

Evolution 1 examines how an agent repeatedly reasons, acts, observes results, and decides whether to continue or stop. I compared the general ReAct loop with the OpenCode agent loop used in my Graduate Application Identity-Assurance and Triage System.

## Nine-Component Comparison

| Component | ReAct | OpenCode Loop | Judgment |
|---|---|---|---|
| 1. Goal | A task or question begins the loop. | The user prompt begins the OpenCode session. | Both require a clear task. |
| 2. Reasoning | The model reasons about the next action. | The configured model decides how to respond or which tool to use. | OpenCode provides the reasoning model inside a working harness. |
| 3. Action | The agent selects an action. | The agent can make an allowed tool call. | OpenCode makes actions operational through tools. |
| 4. Observation | The result of the action returns to the agent. | Tool output returns to the OpenCode agent. | Both use observations to determine the next step. |
| 5. Tools | ReAct may be connected to external tools. | OpenCode exposes configured tools such as read. | OpenCode provides concrete tool integration. |
| 6. State / Context | Previous thoughts, actions, and observations influence later decisions. | The OpenCode session preserves messages and tool results as context. | Both depend on accumulated context. |
| 7. Control | The loop continues until the agent decides to answer or another limit is imposed. | OpenCode supports an explicit `steps` limit. | OpenCode gives me a direct harness-level halt control. |
| 8. Evidence | A ReAct implementation must provide its own trace or logging mechanism. | OpenCode sessions can be exported and used as evidence. | OpenCode gives the course a reproducible flight record. |
| 9. Halt | The agent eventually produces a final answer or is stopped externally. | On the configured final step, OpenCode removes tools and requires a text response. | OpenCode provides a testable stopping boundary. |

## Judgment Loop

**Decision:** Use the OpenCode agent loop for this system rather than implementing a separate ReAct loop myself.

**Characteristics privileged:** Explicit halt control, tool integration, session evidence, bounded agency, and a configuration that can be inspected and tested.

**Cost:** The system depends on OpenCode's harness behavior and configuration. I must verify that the configured agent and model are actually the ones used during a sortie.

**Failure mode:** The wrong primary agent can be used, or a task can be structured in a way that does not actually exercise the step boundary. This occurred during my preliminary E1 attempt when the Build agent was used instead of `grad-triage`.

**Preservation mechanism:** Explicitly launch the required agent, keep `steps: 5` in the agent definition, use dependent test actions that require multiple iterations, export sessions with `--sanitize`, and have Chase judge the committed evidence.

## Evidence from E1

TP1 showed that `grad-triage` could answer a bounded question and stop before the limit.

TP2 used a dependent file chain. The sanitized export showed four sequential read-tool steps followed by a fifth text-only response with `finish = stop`. The chain remained incomplete.

## Conclusion

The OpenCode loop fits this project because it turns the general agent loop into something I can configure, limit, observe, and test. The most important E1 result is that the halt condition is not only an instruction in a prompt. It is enforced by the harness through the configured step limit.
