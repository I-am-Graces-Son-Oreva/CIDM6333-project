# AI Interaction Log

## Evolution 0

This log records the main ways I used AI while working on Evolution 0. I grouped related conversations together instead of copying the full conversation transcript.

---

### Interaction 1 — Understanding Evolution 0

**What I asked:**
I asked ChatGPT to break down the Evolution 0 assignment and explain what I was actually required to do.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT separated the assignment into the required deliverables and explained the purpose of the toolkit check, choices, skills inventory, system pitch, Design Analysis, framework board, ledger, and AI log.

**My decision:** Accepted with modifications.

**What I accepted:**
I accepted the general breakdown and decided to complete the assignment one part at a time.

**What I modified or rejected:**
When explanations used terminology I did not understand, I asked ChatGPT to explain the terms separately and in simpler language.

**Why:**
I wanted to understand what I was doing instead of only completing the required files.

---

### Interaction 2 — Learning Agentic Systems Terminology

**What I asked:**
I asked questions about terms including agent, agency, autonomy, PEAS, agent loop, halt condition, ReAct, governance, runtime, agent harness, deterministic rules, and agentic reasoning.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT explained the terms using simpler examples and connected them to the concepts being discussed in class.

**My decision:** Accepted with follow-up questions.

**What I accepted:**
I accepted explanations that helped me understand the course terminology.

**What I modified or rejected:**
I frequently asked for another explanation when an answer was too technical or when I still did not understand the difference between related terms.

**Why:**
These are terms I will need to explain and defend during the course, so knowing the definition alone is not enough.

---

### Interaction 3 — Git and GitHub Setup

**What I asked:**
I asked ChatGPT to guide me step-by-step through creating my course repository and connecting my local project to GitHub.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT guided me through creating the repository structure, initializing Git, configuring my Git name and email, connecting the GitHub remote, using the main branch, staging files, committing changes, and pushing them to GitHub.

**My decision:** Accepted with troubleshooting.

**What I accepted:**
I used the commands after asking what they meant and followed the Git workflow of edit, save, stage, commit, and push.

**What I modified or rejected:**
When normal password authentication with GitHub failed, I did not continue using that method. I followed a different approach using GitHub CLI and browser authentication. I also asked for explanations of commands such as `cd`, `git add`, `git commit`, and `git push` instead of only copying them.

**Why:**
I want to be able to use Git independently and reproduce the setup later, including on another computer.

---

### Interaction 4 — Toolkit Setup

**What I asked:**
I asked ChatGPT for help installing, checking, and understanding the tools required for the course.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT helped me work through Python, uv, gzkit, Git, Ollama, Qwen3:4b, Codex CLI, OpenCode, and the toolkit verification commands.

**My decision:** Accepted with troubleshooting.

**What I accepted:**
I accepted installation and verification guidance when I could confirm the tools were working from the terminal output.

**What I modified or rejected:**
When commands did not work as expected, I shared the terminal output and worked through the error instead of assuming the installation was successful. For example, the `code` command for Visual Studio Code was not available in my PATH, so I used another way to open files in Visual Studio Code.

**Why:**
I wanted the toolkit check to show tools that were actually installed and working on my computer.

---

### Interaction 5 — Choosing My Model Route, Harness, and Framework

**What I asked:**
I asked ChatGPT to help me understand and compare my choices for model access, an agent harness, and an orchestration framework.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT helped me compare local model access through Ollama with cloud API options. We also discussed OpenCode and Codex CLI as harnesses and compared LangGraph, CrewAI, and AutoGen as possible orchestration frameworks.

**My decision:** Accepted with modifications.

**What I accepted:**
I selected Ollama with Qwen3:4b for local model access, OpenCode as my primary harness, and LangGraph as my current candidate orchestration framework.

**What I modified or rejected:**
I did not want the choices written as if I had tested every alternative. I wanted the document to clearly separate tools I actually installed and used from alternatives I only considered. I also kept LangGraph as a provisional choice rather than treating it as a final decision.

**Why:**
I wanted the document to accurately represent what I had actually done and leave room for my design choices to change as I learn more.

---

### Interaction 6 — Skills Inventory

**What I asked:**
I asked ChatGPT to help organize my current technical skills for `skills-inventory.md`.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT helped organize my experience with SQL, Tableau, Excel, prompting, Python, Git/GitHub, APIs, and AI.

**My decision:** Modified significantly.

**What I accepted:**
I accepted the general organization of the skills into skills I already had and skills I am currently developing.

**What I modified or rejected:**
I corrected descriptions that did not accurately represent my skill level. I clarified my SQL experience, what I can do with Tableau, and that Python, APIs, Git, and AI development are still developing skills. I also asked for the document to state that I am learning Git and AI concepts with help from ChatGPT.

**Why:**
I did not want AI to exaggerate my experience or make claims that I could not personally support.

---

### Interaction 7 — Developing the Project Idea

**What I asked:**
I discussed a real problem involving suspicious or "ghost" graduate applications and asked ChatGPT to help me determine whether it could become my semester agentic systems project.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT helped me organize information from my conversations with graduate admissions staff and think about the problem as an identity-assurance and screening problem instead of simply calling it an AI fraud detector.

**My decision:** Accepted with important limits.

**What I accepted:**
I accepted the idea of developing a Graduate Application Identity-Assurance and Screening System that could help determine whether an application has enough evidence to continue normally or needs additional verification.

**What I modified or rejected:**
I rejected the idea of allowing AI to independently decide that an applicant is committing fraud. I also did not want the system to automatically reject applicants.

**Why:**
The purpose of the system is to support the admissions process and reduce unnecessary work, while important decisions should remain with appropriate people or approved verification processes.

---

### Interaction 8 — Deciding Where an Agent Is Actually Needed

**What I asked:**
I questioned whether every part of my proposed system really needed an AI agent.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
We discussed the difference between deterministic rules, workflows, and agentic reasoning.

**My decision:** Accepted.

**What I accepted:**
I decided that clear university rules should use deterministic logic when possible. Agentic reasoning should be used when the situation is uncertain and the system needs to examine evidence, choose an allowed next step or tool, observe the result, and decide whether to continue, stop, or escalate.

**What I modified or rejected:**
I rejected the idea of adding an agent simply because this is an Agentic Systems course.

**Why:**
I want the agent to have a clear reason for being part of the system. If a simple rule can perform a task more predictably, there is no reason to make that part unnecessarily agentic.

---

### Interaction 9 — Writing the System Pitch

**What I asked:**
I asked ChatGPT to help turn my project idea and the information I gathered from graduate admissions staff into the required system pitch.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT drafted the user and problem, proposed system, semester layers, biggest risk, and PEAS specification.

**My decision:** Modified.

**What I accepted:**
I accepted the overall project structure, the PEAS organization, and the focus on human oversight.

**What I modified or rejected:**
I rejected the first versions because the language was too complicated for the way I normally explain things. I asked ChatGPT to rewrite the entire pitch in simpler English while keeping important course terms such as deterministic rules, agentic reasoning, MCP, context, memory, governance, and PEAS.

I also changed the multi-agent wording so that the project does not assume more agents are automatically better. The system can test later whether having one agent check another agent's work actually improves the result.

**Why:**
I want to submit work that I understand and can explain myself during Drift.

---

### Interaction 10 — Design Analysis

**What I asked:**
I asked ChatGPT to help me compare a chat assistant with an agent harness using the nine components required by the assignment.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT organized the comparison across foundation, perception, planning and reasoning, tools and orchestration, memory and context, coordination, evaluation and feedback, governance and human interface, and runtime and operations.

**My decision:** Accepted.

**What I accepted:**
I accepted the main judgment that an agent harness needs additional controls because it can allow a model to take actions through tools instead of only producing an answer.

**What I modified or rejected:**
I kept the explanation in simple language so I could understand the reason behind the comparison and defend it.

**Why:**
The important point for me was understanding why increased agency also creates a need for permissions, evaluation, logs, halt conditions, and human oversight.

---

### Interaction 11 — Framework Board and Ledger

**What I asked:**
I asked ChatGPT to help me complete the framework board and Design Analysis ledger.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT suggested concrete systems I could already connect to parts of the framework, including Qwen3:4b, Ollama, OpenCode, Codex CLI, ChatGPT, Git, and GitHub. It also helped summarize the main judgment from Design Analysis #1 for the ledger.

**My decision:** Accepted with limits.

**What I accepted:**
I accepted examples that I had actually used or could explain.

**What I modified or rejected:**
I did not try to fill every part of the framework with an example. Areas that I cannot yet confidently explain remain learning areas.

**Why:**
I want the framework board to represent my current understanding rather than make it appear that I already know parts of the course that I have not learned yet.

---

### Interaction 12 — Evolution 5 MCP Security Sortie

**What I asked:**
I asked ChatGPT to help me plan, build, test, and document the Evolution 5 MCP security sortie.

**Model:** ChatGPT
**Interface:** ChatGPT web interface

**AI response:**
ChatGPT helped me create and revise the Flight Card, build the MCP notes-server test environment, create separate honest and adversarial clients, add a central tool-to-scope authorization table, and run the required security test points.

The tests included a pinned tool/scope check, an honest read, an out-of-scope write attempt, forged write-scope attempts, a poisoned resource test, and a wrong-audience authentication test.

ChatGPT also helped me organize the flight evidence, revise AGENTS.md, move the multi-step procedure into SKILL.md, measure the revised AGENTS.md, and write Design Analysis #2.

**My decision:** Accepted with testing and revision.

**What I accepted:**
I accepted the server-side authorization design where validated identity and scope determine whether a tool can execute. I also accepted the central scope table and the rule that client-provided scope claims and resource instructions are untrusted data.

**What I modified or rejected:**
I did not treat the first implementation as final. During testing, some early client output and middleware behavior did not meet the required evidence. I continued testing and revised the implementation until the server rejected unauthorized writes before the write handler executed.

I also kept the official Sortie 5 evidence separate from the earlier MCP poisoning lab.

**Why:**
The main thing I learned is that a client should not be able to give itself more authority by putting a stronger scope in a header, body, or tool argument. The server must validate authorization itself before allowing a protected action.

The flight results supported this design: the honest read succeeded, unauthorized and forged write attempts were denied, the poisoned resource caused no write, the write ledger stayed unchanged, and the wrong-audience request returned HTTP 401.


---

## Evolution 6 — Context Engineering

**Date:** November 8, 2026

**Model:** ChatGPT

**Interface:** ChatGPT web interface

**AI response:**
ChatGPT helped me translate the Evolution 6 Flight Card into a small context
engineering implementation. It helped me build tests for the budget meter,
compactor keep list, seven-section handoff, resume loader, and L1/L2/L3
precedence rule.

ChatGPT also helped me inspect an OpenCode Session A export without treating
the visible TUI context number as sufficient evidence. The export showed six
user turns but twelve actual model calls, so I recorded provider usage at the
model-call level.

For the resume test, ChatGPT helped me create a handoff with one concrete first
action and then start a separate OpenCode Session B without Session A's
transcript. Session B followed the handoff correctly.

A deliberately stale L3 status view was also tested against the append-only L2
ledger.

**My decision:** Accepted with testing and evidence.

**What I accepted:**
I accepted the design where important context moves to durable files, each
model call has measurable budget evidence, compaction has a declared keep
list, and a fresh session resumes from a structured handoff.

I also accepted the precedence rule:

`L2 ledger > L1 canon > L3 derived views`

**What I modified or rejected:**
I did not treat the OpenCode TUI context number as proof of my own budget
meter. I used the exported provider usage fields instead.

I also did not claim that OpenCode automatically compacted at my declared
6,400-token threshold. The controlled Sprint compaction was tested separately
in my own implementation.

The raw OpenCode session exports are not intended for the repository because
they may contain repository file contents.

**Why:**
The main thing I learned is that an agent's conversation is not a reliable
long-term source of truth. Important state needs to survive outside the
temporary context window.

The fresh-session test made this clear: Session B could continue the work
without Session A's transcript because the important state had been written to
the handoff and runtime ledger.

## 2026-11-09 — Evolution 1

**Evolution:** E1 — The Loop That Halts

**AI/model used:** `opencode/big-pickle` through OpenCode 1.18.20.

**Use:** I used the model as the `grad-triage` primary agent for the E1 sortie. TP1 tested bounded completion. TP2 tested whether the configured step limit stopped further tool use and forced a final text response.

**Model/harness claim checked against source:** I checked the OpenCode Agents documentation for the behavior of the `steps` setting. The documentation states that `steps` sets a maximum number of model steps and that on the final step OpenCode removes tools and asks the model to summarize in text. This matched the behavior observed in my sanitized TP2 export.

**Source checked:** OpenCode documentation, Agents — https://opencode.ai/docs/agents

**Evidence:** `evolution-01/evidence/tp1-sanitized.json` and `evolution-01/evidence/tp2-sanitized.json`.

**Reflection:** The preliminary flight taught me that configuring an agent is not enough; I also have to verify that the intended agent is actually running. The successful re-flight explicitly used `grad-triage` and produced evidence for both bounded completion and the halt condition.
