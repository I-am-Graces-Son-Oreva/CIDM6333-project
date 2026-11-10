# Evolution 4 Flight Log — N×M Becomes N+M

Date: 2026-11-09  
Operator: Joseph Edafiadhe  
Preflight: GO — Chase — 2026-11-09  
Preflight commit: 79adfdb  
MCP SDK: 1.30.0  
OpenCode: 1.18.20  
Model: opencode/big-pickle

## Design Claim

A single MCP server implementation can expose the same tool contract to multiple clients. OpenCode and an independent Python MCP client should both discover and call the same read tool, while OpenCode's permission gate protects the write tool.

## TP1 — Independent Python Client

Verdict: PASS

Evidence:
- `evolution-04/evidence/tp1-python-client.txt`
- `evolution-04/server.log`

Observed:
- Python client discovered both `read_triage_note` and `write_triage_note`.
- Python client called `read_triage_note`.
- The demo note returned successfully.
- Server log recorded `client=python-client`, `tool=read_triage_note`, `name=demo`.

## TP2 — OpenCode MCP Read

Verdict: PASS

Session:
`ses_e3cb461a8ffezemx61YA76m4MQ`

Evidence:
- `evolution-04/evidence/tp2-sanitized.json`
- `evolution-04/server.log`

Observed:
- OpenCode called `grad-triage-e4_read_triage_note`.
- The demo note returned successfully.
- Sanitized export preserves the MCP tool-call structure.
- Server log recorded `client=opencode`, `tool=read_triage_note`, `name=demo`.
- TP1 and TP2 therefore show two different clients using the same MCP read-tool contract.

## TP3 — OpenCode Write Permission Gate

Verdict: PASS

Session:
`ses_e3cb17ea5ffeR7DDmssaqDSwz1`

Evidence:
- `evolution-04/evidence/tp3-sanitized.json`
- `evolution-04/server.log`
- absence of `evolution-04/data/tp3-blocked.txt`

Observed:
- OpenCode attempted `grad-triage-e4_write_triage_note`.
- The configured `ask` permission was encountered.
- Noninteractive OpenCode auto-rejected the permission request.
- Sanitized export records the tool with status `error` and states that the user rejected permission.
- `tp3-blocked.txt` was not created.
- No `write_triage_note` call reached the MCP server.

## Falsifier Review

1. Permission loosened, tool removed, or export edited:
   NOT OBSERVED. The write permission remained `ask`, both tools remained available, and evidence uses sanitized OpenCode exports.

2. Two clients fail to use the same MCP read tool:
   NOT OBSERVED. Python client and OpenCode both called `read_triage_note`.

3. Server fails to log client/tool calls:
   NOT OBSERVED. Server log contains both successful read calls with distinct client identifiers.

4. OpenCode write succeeds without encountering `ask`:
   NOT OBSERVED. The write was rejected and no output file was created.

## Flight Verdict

PASS

The sortie supports the design claim. The independent Python client and OpenCode used the same MCP read-tool contract, while OpenCode's permission boundary prevented the attempted write from reaching the server.

## CHASE POST-FLIGHT

Pending.
