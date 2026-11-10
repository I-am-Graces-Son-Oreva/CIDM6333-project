# Design Analysis Ledger

| Evolution | Design Analysis | Subject | Main Judgment |
|---|---|---|---|
| E0 | Design Analysis #1 | Chat Assistant vs. Agent Harness | Use an agent harness when a task needs tools, actions, and multiple steps. Keep human control, permissions, evaluation, and halt conditions because the system can act, not just answer. |
| E5 | Design Analysis #2 | Client-Claimed Scope vs. Server-Validated Authorization | Enforce authorization from server-validated identity and scope using a central tool-to-scope table. Treat client scope claims and resource instructions as untrusted data, and reject insufficient scope before the protected tool executes. |
| E1 | Design Analysis — ReAct Loop vs. OpenCode Agent Loop | ReAct vs. OpenCode Loop | Use the OpenCode loop because it provides explicit step limits, integrated tools, exportable evidence, and a testable halt boundary while preserving human control over important admissions decisions. |
| E2 | Design Analysis — OpenCode Orchestrator-Workers vs. LangGraph Orchestration | LangGraph vs. OpenCode Orchestration | Use OpenCode orchestrator-workers for this bounded two-worker workflow because it provides visible task delegation, explicit worker roles, permission-controlled subagent access, and sanitized session evidence without adding another orchestration framework. |
| E3 | Design Analysis — OpenCode Permissions vs. Claude Code Hooks | Harness Permission Gates | Use OpenCode permissions as the harness gate because allow/ask/deny rules can stop protected tool actions independently of model reasoning and produce testable sanitized evidence. E3 showed this matters when the local model followed a planted instruction but the write gate prevented repository changes. |
