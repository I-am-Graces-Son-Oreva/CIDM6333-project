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