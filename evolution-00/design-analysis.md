# Evolution 0 — Design Analysis #1

## Chat Assistant vs. Agent Harness

### Sources Read

For this analysis, I used the Evolution 0 course materials, the class discussion on agent harnesses, and the assigned readings on agentic systems.

### Nine Components

| Component | Chat Assistant | Agent Harness |
|---|---|---|
| **Foundation** | Uses an LLM to understand a prompt and generate a response. | Also uses an LLM, but places a system around the model so it can perform more than just generate responses. |
| **Perception** | Receives information mainly through the user's messages and available context. | Can receive information from the user, files, tools, command results, and other parts of its environment. |
| **Planning and Reasoning** | Reasons about the user's question and produces a response. | Can reason about a goal, decide what step to take next, observe the result, and continue through a loop. |
| **Tools and Orchestration** | May have tools available, but the conversation is usually centered on answering the user. | Uses tools to perform actions such as reading files, editing files, running commands, or testing results. |
| **Memory and Context** | Uses the conversation and available context to understand the current request. | The harness can manage context and keep useful information available while completing a task. |
| **Coordination** | Usually involves the user and one assistant. | Can coordinate tools, workflows, and possibly other agents. |
| **Evaluation and Feedback** | The user usually reviews the answer and decides whether it is useful or correct. | Results can be checked through tests, tool output, logs, or another review step before the system continues. |
| **Governance and Human Interface** | The human controls the conversation by deciding what to ask and what to do with the answer. | Permissions and rules can control what the system is allowed to do, while important decisions can remain with the human. |
| **Runtime and Operations** | Runs inside the chat environment provided to the user. | The harness manages how the model, tools, commands, and agent loop operate together. |

### Why the Harness Is Built This Way

An agent harness is built around the LLM because the model alone does not have everything needed to safely complete multi-step tasks. The harness gives the model access to tools, controls its actions, manages context, and helps determine when the system should continue or stop. This gives the system more **agency**, but it also creates more risk. If the model makes a bad decision, the mistake could become an action instead of only a bad answer. Because of this, permissions, evaluation, logs, halt conditions, and human oversight become important.

### Judgment Loop

**Decision:** Use an agent harness when a task needs the system to take actions and work through multiple steps instead of only answering a question.

**Characteristics privileged:** Tool use, controlled agency, evidence, human oversight, and the ability to complete multi-step tasks.

**Cost:** The system becomes more complex and requires more testing, permissions, monitoring, and governance.

**Failure mode:** The model may reason incorrectly and use a tool or take an action that it should not take.

**Preservation mechanism:** Use clear permissions, logs, evaluation, halt conditions, and human authority over important decisions.