# Design Analysis — Evolution 4

## Model Context Protocol vs. Direct Client Plugins

Evolution 4 asks how one capability can be made available to multiple AI clients without building a separate integration for every client-system pair. For the Graduate Application Identity-Assurance and Triage System, I used a Python MCP server that exposes graduate-triage tools through a shared protocol.

I compared MCP with direct client-specific plugins. A direct plugin can connect one client to one service, but adding more clients and services can require separate integrations. MCP moves the tool contract behind a protocol boundary so different MCP-capable clients can use the same server implementation.

## Nine Components

| Component | Direct Client Plugins | MCP | Judgment |
|---|---|---|---|
| 1. Goal | A plugin connects a particular client to an external capability. | MCP exposes capabilities through a shared client-server protocol. | MCP better supports the E4 goal of demonstrating one server contract across different clients. |
| 2. Reasoning | The client model decides when to invoke its plugin. | The client model decides when to invoke an MCP tool exposed by the server. | Model reasoning still belongs to the client; MCP standardizes the capability boundary rather than the reasoning itself. |
| 3. Action | Actions are implemented through the plugin's client-specific interface. | Actions are exposed as MCP tools such as `read_triage_note` and `write_triage_note`. | The MCP tool contract can remain the same when the client changes. |
| 4. Observation | Plugin results return through the plugin integration. | MCP tool results return through the protocol to the requesting client. | Both approaches return observations, but MCP gives multiple compatible clients a common interaction model. |
| 5. Tools | Each plugin integration defines how its tools are exposed to its client. | The MCP server defines tools once and clients discover them through MCP. | E4 demonstrated the same `read_triage_note` tool being discovered through an independent Python client and used through OpenCode. |
| 6. State / Context | Integration state may be coupled to the plugin or host application. | Server-side data and logs can remain behind the MCP boundary while clients receive tool results. | Keeping the graduate-triage capability behind the server gives the system a clearer boundary. |
| 7. Control | Control depends on the plugin and host application's permission system. | MCP provides the tool interface while the client harness can apply its own permission boundary. | In E4, OpenCode configured the MCP write tool as `ask`, so the write attempt was blocked before reaching the server. |
| 8. Evidence | Evidence depends on what the individual plugin or host records. | MCP server logs can be combined with client-side session evidence. | E4 used the server log plus sanitized OpenCode exports to observe both sides of the boundary. |
| 9. Halt / Failure | Failure behavior depends on each plugin integration. | Tool calls can fail at the client permission boundary or server/tool boundary. | TP3 showed that an MCP write request can be stopped by the client harness before server execution. |

## Judgment Loop

**Decision:** Use MCP for the E4 shared tool boundary rather than creating separate direct plugins for each client.

**Characteristics privileged:** A shared tool contract, client/server separation, tool discovery, reuse across different clients, server-side call logging, and compatibility with client-side permission gates.

**Cost:** MCP adds another protocol and server boundary that must be configured, tested, and maintained. Client behavior can also differ, so using a common protocol does not eliminate the need to test each client.

**Failure mode:** A client could call the wrong tool, supply incorrect arguments, receive broader tools than intended, or attempt a protected write. A server could also expose unsafe behavior if its tools are poorly designed.

**Preservation mechanism:** Keep the MCP server small, expose only required tools, distinguish read and write effects, log calls at the server, apply client-side permissions to protected tools, retain sanitized client evidence, test the same tool from multiple clients, and have Chase review committed evidence.

## Evidence from E4

TP1 used the independent Python MCP client. The client discovered both `read_triage_note` and `write_triage_note`, called `read_triage_note`, and received the demo graduate-triage note. The server log recorded the call with `client=python-client`.

TP2 used OpenCode as the other MCP client. OpenCode called `grad-triage-e4_read_triage_note` and received the same demo note. The sanitized OpenCode export preserved the MCP tool-call structure, while the server log recorded `client=opencode`.

Together, TP1 and TP2 support the E4 design claim: two different clients used the same MCP read-tool contract instead of requiring two separate implementations of the graduate-triage capability.

TP3 tested the protected write path. OpenCode attempted `grad-triage-e4_write_triage_note`, but the configured `ask` permission was auto-rejected during the non-interactive run. The sanitized export recorded the tool call with an error, `tp3-blocked.txt` was not created, and the server log contained no `write_triage_note` call.

Chase reviewed the committed evidence and recorded:

`CHASE — Chase — 2026-11-09 — PASS`

## Conclusion

For this project, MCP provides a useful boundary between AI clients and graduate-triage capabilities. E4 demonstrated that an independent Python client and OpenCode could use the same MCP read-tool contract while OpenCode could independently enforce a permission rule on the write path.

The main lesson is that MCP standardizes how a client reaches a capability, but it does not replace authorization, permission gates, logging, or testing. Those controls still need to exist around the protocol.
