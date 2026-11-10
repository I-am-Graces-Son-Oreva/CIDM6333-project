# GitHub MCP Server Design Analysis

## Ways to run (remote/local)
- Remote: https://api.githubcopilot.com/mcp/
- Local: Docker image ghcr.io/github/github-mcp-server

## Ways to authenticate; which precedence
- Authentication method 1: OAuth
- Authentication method 2: GitHub Personal Access Token (PAT)
- Which precedence: Personal Access Token (PAT) takes precedence over OAuth.

## Default toolsets (count) / all toolsets (count)
- Default toolsets (count): 5
- All toolsets (count): 22

## Tools with effect class (at least eight): read/write/irreversible
1. `get_file_contents` — read
2. `create_or_update_file` — write
3. `delete_repository` — irreversible
4. `issue_read` — read
5. `issue_write` — write
6. `add_issue_comment` — write
7. `create_pull_request` — write
8. `merge_pull_request` — irreversible

## Tools that return other people's text
1. `issue_read` — can return issue bodies and comments written by other people.
2. `get_file_contents` — can return file content from a repository not owned by you.
3. `pull_request_read` — can return PR descriptions, comments, and review comments written by other people.

## Attack trace
1. Agent reads an open issue in a public repository using `issue_read`; the issue contains text written by a stranger.
2. Agent reads data from a private repository and brings that private data into its context.
3. Agent writes the private data into a pull request in the public repository, where the stranger can read it.

## Setting that stops each step
1. `--lockdown-mode` / `X-MCP-Lockdown` — stops the malicious public issue from being surfaced when its author does not have push access to the repository.
   > "Lockdown mode limits the content that the server will surface from public repositories."
2. Fine-grained PAT restricted to selected repositories — stops the agent from accessing the private repository if that repository is not included in the  token's allowed repositories.
   > "Each token can be further limited to only access specific repositories for that user or organization."
3. `--read-only` / `X-MCP-Readonly` — stops the agent from writing the private data into a public pull request because only read-only tools are offered.
> "This will only offer read-only tools, preventing any modifications to repositories, issues, pull requests, etc."

## Step that no setting stops
- None in this three-step attack trace; each step has a configuration control that can stop it. 

## Model id used in step 4
- `opencode/big-pickle`

## Model's other path (Q1): tool named · confirmed/refuted/cannot tell · evidence
- Tool named: `merge_pull_request`
- Confirmed/refuted/cannot tell: Cannot tell
- Evidence: The README confirms that `merge_pull_request` exists and merges a pull request, but this tool entry does not show whether it remains available when `--read-only` is enabled.

## Trade-off (Q2)
- A developer could no longer merge a pull request because `--read-only` prevents write operations.

## Judgment loop
- Decision: I would use lockdown mode, a fine-grained PAT restricted to only the repositories the agent needs, and read-only mode.
- Characteristics: The agent's ability to read repository data and write or modify GitHub content is privileged.
- Cost: The agent loses useful write capabilities and cannot access repositories outside those allowed by the fine-grained PAT.
- Failure mode: Untrusted content could still reach the agent through another path that is not blocked by the chosen settings.
- Preservation: The restricted fine-grained PAT limits what repository data the agent can access, and read-only mode limits its ability to write data out through GitHub.

## Nine-Component Design Analysis

| Component | GitHub MCP Server Analysis |
|---|---|
| Foundation | The system uses an AI model connected to GitHub through the GitHub MCP server, with GitHub authentication controlling repository access. |
| Perception | The agent can receive repository content through tools such as `issue_read`, `get_file_contents`, and `pull_request_read`. This can include text written by strangers, so untrusted public content can enter the model's context. Lockdown mode reduces this exposure by limiting content surfaced from public repositories. |
| Planning & reasoning | The model can combine multiple tool calls into a sequence, including reading an issue, accessing repository data, and deciding what action to take next. |
| Tools & orchestration | GitHub MCP provides both read and write tools. A dangerous combination is a private read path together with a public write path. A restricted fine-grained PAT limits which repositories can be accessed, while `--read-only` removes write capabilities. |
| Memory & context | Private repository data returned by a tool can enter the model's working context and may remain available while later actions are planned. |
| Coordination | The workflow coordinates the model, GitHub MCP server, GitHub permissions, and the human operator. Security should not depend only on the model following instructions; the MCP configuration and GitHub permissions should constrain what the agent can actually do. |
| Evaluation & feedback | I would check whether untrusted public content can reach the agent, whether repositories outside the PAT scope can be read, and whether a GitHub write path remains available. |
| Governance & human | I would use lockdown mode, a fine-grained PAT restricted to only necessary repositories, and read-only mode. These controls preserve human authority by limiting what the agent can access and change instead of relying only on instructions given to the model. |
| Runtime & operations | The server configuration and token permissions should remain restricted while the agent is running, and the settings should be checked before granting broader access. |

## Connection Decision

I would connect the GitHub MCP server only with restricted settings. I would use lockdown mode, a fine-grained PAT limited to only the repositories the agent needs, and read-only mode when write access is not necessary. These settings reduce the attack path examined in this lab by limiting untrusted public content, restricting access to private repository data, and removing GitHub write paths. The cost is that the agent loses useful capabilities such as creating, modifying, or merging GitHub content. I would not rely only on an instruction telling the model not to reveal private data because the configuration outside the model should enforce the boundary.