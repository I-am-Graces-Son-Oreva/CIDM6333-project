# Evolution 4 Flight Card — N×M Becomes N+M

## ENVELOPE

Evolution: E4 — N×M Becomes N+M  
System: Graduate Application Identity-Assurance and Triage System  
Operator: Joseph Edafiadhe  
Date: 2026-11-09

## DESIGN CLAIM

A single MCP server can expose the same graduate-triage tool contract to more than one client. OpenCode and an independent Python MCP client should both be able to discover and call the same read tool, while the write tool remains protected by OpenCode's ask permission.

## SYSTEMS UNDER TEST

- Python MCP server: `src/grad_mcp/server.py`
- OpenCode MCP client
- Independent Python MCP client: `evolution-04/python_client.py`
- OpenCode permission gate for the MCP write tool
- MCP call log: `evolution-04/server.log`

## SUBSTRATE

Repository: CIDM6333-project  
Commit: f9d519d  
OpenCode: 1.18.20  
MCP Python SDK: 1.30.0 (`mcp<2`)  
Model: opencode/big-pickle  
Transport: stdio

## TEST POINTS / EXPECTED OBSERVATIONS

### TP1 — Independent client discovery and read

Run the Python MCP client.

Expected:
- Client lists `read_triage_note` and `write_triage_note`.
- Client calls `read_triage_note`.
- Server log records `client=python-client`.
- Read result returns the demo triage note.

### TP2 — OpenCode discovery and read

Ask OpenCode to use the E4 MCP read tool on the demo note with client `opencode`.

Expected:
- OpenCode calls the same `read_triage_note` tool.
- Tool returns the demo note.
- Server log records `client=opencode`.
- Sanitized OpenCode export contains evidence of the MCP tool call.

### TP3 — OpenCode write permission gate

Ask OpenCode to call `write_triage_note` with client `opencode`.

Expected:
- OpenCode encounters the configured `ask` permission for the write tool.
- A noninteractive run must not silently perform the write.
- Evidence shows the permission request/rejection or equivalent gate behavior.
- No successful unauthorized note write occurs.

## INSTRUMENTATION

- `evolution-04/server.log`
- Python client terminal output
- Sanitized OpenCode session exports
- Git status/diff checks
- MCP tool listing
- OpenCode permission configuration

## FALSIFIERS

1. The sortie passes only because a permission was loosened, a tool was removed, or an export was edited.
2. OpenCode and the independent Python client do not discover/call the same MCP read tool.
3. The server does not log the client/tool call.
4. The OpenCode write call succeeds without encountering the configured `ask` permission.

## ABORT

ABORT if the MCP server cannot start, OpenCode cannot connect to it, the selected model cannot make the required MCP tool call, or the independent client cannot initialize an MCP session. Record the error and model/client identity rather than claiming PASS.

## CHASE GO / NO-GO

GO — Chase — 2026-11-09
