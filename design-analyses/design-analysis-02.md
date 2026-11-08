# Design Analysis #2

## Subject

Client-Claimed Scope vs. Server-Validated Authorization

## Context

Evolution 5 tested whether an MCP client with read-only authorization could gain write authority by claiming a stronger scope or by receiving malicious instructions from a resource.

The system exposes two protected tools:

- `read_note` requires `notes:read`
- `write_note` requires `notes:write`

The main design question was where authorization should be trusted and enforced.

## Nine Design Components

### 1. Foundation

The security design follows least privilege. A client receives only the authority it actually needs. A read-only client should not gain write access by claiming a stronger scope.

### 2. Perception

The server receives several kinds of information from the client, including the signed token, request data, headers, tool arguments, and resource content. These inputs do not all have the same level of trust.

### 3. Planning and Reasoning

Before executing a protected tool, the system determines which scope the tool requires and compares that requirement with the scope from the server-validated token.

The client does not get to decide its own authority.

### 4. Tools and Orchestration

The MCP server exposes `read_note` and `write_note`. A central scope table maps each tool to its required authorization scope.

A tool that is absent from the central scope table is refused rather than being allowed by default.

### 5. Memory and Context

Resource content and note content are treated as data. They may provide context, but they do not provide authorization.

This became important when the poisoned resource contained the instruction to write X immediately.

### 6. Coordination

The honest client and adversarial red client run with separate identities and signed tokens. This separation allows the experiment to distinguish normal authorized behavior from attempts to increase authority.

### 7. Evaluation and Feedback

TP0 checks the pinned tool-to-scope contract.

TP1 verifies that an authorized read succeeds.

TP2 tests whether a read-only client can execute the write tool.

TP3 tests forged write-scope claims.

TP4 tests whether poisoned resource content can cause a write.

The server log and append-only write ledger provide evidence for evaluating the result.

### 8. Governance and Human Interface

Write authority is controlled by server-side authorization rather than instructions supplied by the client or a resource.

The confirmation gate also provides an additional boundary around write behavior. Resource instructions cannot silently grant permission to change state.

### 9. Runtime and Operations

The MCP server validates signed test tokens containing `sub`, `aud`, `scope`, and `exp`.

The server checks the token signature, expiration, audience, and required tool scope. A wrong-audience signed token is rejected before tool execution.

The official flight also keeps server evidence separate from the client so the client cannot manufacture successful authorization evidence.

## Options Considered

### Option 1 — Trust Client-Provided Scope Claims

The server could accept scope information supplied through a request header, request body, or tool argument.

This is simpler, but it lets the client describe its own authority. A malicious or compromised client could claim `notes:write` even when its validated authorization only grants `notes:read`.

### Option 2 — Use Server-Validated Authorization

The server validates the client's signed authorization and compares the validated scope against the central tool-to-scope table before allowing a protected tool to execute.

Client-provided scope claims are treated as untrusted data.

## Why This Design Matters

Authorization controls what an agent or client is allowed to change. If a client can increase its own authority through a header, request field, tool argument, or poisoned resource instruction, then the authorization boundary is not meaningful.

For this project, the safer design is to keep authority on the server and treat client claims and resource instructions as untrusted input.

## Experiment Evidence

The Sortie 5 flight supports the server-validated design.

TP1 showed that an honestly authorized read request succeeds.

TP2 showed that a read-only client cannot execute `write_note`.

TP3 showed that forged write-scope attempts were denied while the server continued to validate only `notes:read`.

TP4 showed that the poisoned resource instruction did not cause a write. The write ledger remained at zero.

The signed wrong-audience test returned HTTP 401, and the server recorded `wrong_audience`.

## Judgment Loop

**Claim:** A read-only MCP client should not be able to execute a protected write by claiming stronger authority, and poisoned resource content should not create write authority.

**Evidence:** The read-only red client was denied access to `write_note`; forged scope attempts were denied using the validated `notes:read` scope; the poisoned resource produced no write; and the wrong-audience signed token returned HTTP 401.

**Judgment:** The evidence supports server-validated authorization. Client-provided claims and resource instructions must not be treated as authority.

**Next action:** Keep the central scope table, signed-token validation, pre-execution scope enforcement, separate identities, confirmation gate, server log, and append-only write ledger as the security boundary for future MCP work.

## Consequences

This design reduces the risk that a compromised client, forged request field, or poisoned MCP resource can increase its own authority.

It also makes authorization easier to inspect because tool requirements are stored in one central table.

The tradeoff is additional server-side security logic and testing, but that complexity is justified because write operations can change system state.
