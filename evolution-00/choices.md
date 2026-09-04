# Evolution 0 — Route, Harness, and Candidate Framework

## Model-Access Route — Ollama with Qwen3:4b

I chose **Ollama with the Qwen3:4b open-weight model running locally** as my primary model-access route. I considered cloud-hosted alternatives such as the **OpenAI API with GPT models, Anthropic API with Claude models, and Google Gemini API**. These cloud options could provide access to more capable models and reduce some of the performance limitations caused by my local hardware. However, they can also introduce usage-based costs. Since I am still learning how agentic systems work, I expect to experiment, make mistakes, repeat tests, and gradually increase the complexity of my system. I prefer to do that without having to worry about API charges while I am learning.

Ollama gives me a cost-controlled environment where I can run Qwen3:4b locally, and I have already confirmed that the model runs successfully on my computer. The main trade-off is that my current computer has hardware limitations that may affect the speed of the system and the size or capability of the models I can run. Rather than assuming that this limitation will become a problem, I want to observe how Qwen3:4b performs as my system develops during the semester. If the system eventually becomes too demanding for my local setup, I can use that evidence to reconsider the model-access decision.

## Primary Harness — OpenCode

I chose **OpenCode** as my primary harness. I also installed and considered **Codex CLI** as an alternative. Both provide an environment around a language model that can help with software-development tasks, but I selected OpenCode because it gives me an opportunity to learn how a harness structures and directs the behavior of a model through instructions, tools, context, permissions, and other control mechanisms. OpenCode is also the harness being emphasized in this course, so using it will allow me to become familiar with the concepts and structure that I will eventually need to understand well enough to design my own agentic system.

The trade-off is that OpenCode is a new development environment for me. I will need to learn how it works instead of relying only on a familiar chat interface. I consider that learning curve useful because one of my goals in this course is to understand the difference between simply interacting with an AI model and designing a governed system around one.

## Candidate Orchestration Framework — LangGraph

I selected **LangGraph** as my provisional orchestration-framework candidate. I also considered **CrewAI** and **AutoGen**. CrewAI places more emphasis on organizing agents into roles that collaborate on tasks, while AutoGen has also been used for coordinating interactions among multiple agents. Those approaches may become useful later when the course reaches multi-agent systems, but I do not want to introduce multiple agents simply because a framework makes it possible.

My semester project currently appears to need a controlled process in which a graduate application can move through evidence gathering, assessment, additional verification, normal processing, or human escalation depending on the state of the case. LangGraph's state-and-transition approach appears suitable for representing this type of governed workflow. It also leaves room for tools, memory, conditional routing, human involvement, and eventually multi-agent behavior if those capabilities earn a place in the design.

The trade-off is that LangGraph is new to me, and I do not yet have enough evidence to claim that it is the best framework for my system. I am therefore treating LangGraph as a candidate rather than a final decision. I will compare it more formally with alternatives before making the framework decision in ADR-1 during Evolution 2.