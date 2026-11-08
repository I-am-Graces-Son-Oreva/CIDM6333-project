# Design Analysis #3 — OpenCode Context System

## System

OpenCode 1.18.20 context and session system.

## 1. Context source

OpenCode builds working context from the active conversation, repository
information, tool results, and files that the agent reads.

## 2. Session boundary

A session is a boundary around a conversation history. A new session does not
automatically have the previous session's conversational context.

## 3. Measurement

OpenCode session exports contain token information on assistant/model
messages.

In Evolution 6, I observed fields for input, output, reasoning, cache read,
cache write, and total tokens.

## 4. Compaction

Long-running agent work cannot assume that every previous token will remain
available forever. Important state therefore needs a deliberate survival
strategy rather than depending only on conversation history.

For my Evolution 6 implementation, I use an explicit keep list and move
important state to files.

## 5. Persistence

Repository files provide durable context outside the model window.

For Evolution 6, important persistent artifacts include the Flight Card,
handoff, README, and runtime ledger.

## 6. Handoff

A handoff allows a new session to continue work without receiving the old
transcript.

My handoff contains seven sections:

- Current state
- Important context
- Decisions with attribution
- Next steps
- Pending work
- Verification checklist
- Evidence

The first next step is intentionally concrete so that resume behavior can be
tested.

## 7. Resume

I tested resume behavior using a fresh OpenCode Session B.

Session B received repository context rather than Session A's transcript.

Its first action matched the handoff's first next step, and it correctly
reported the latest ledger event.

## 8. Truth hierarchy

I use three layers:

- L1: canon
- L2: runtime ledger
- L3: derived views

My declared precedence is:

`L2 > L1 > L3`

This prevents an old summary or status view from defeating stronger runtime
evidence.

## 9. Failure handling

The design has explicit failure conditions.

Examples include missing provider usage without a declared fallback, a fresh
session asking already-answered questions, the wrong first resume action, or
stale L3 information overriding L2.

These conditions make failure observable instead of allowing the system to
quietly claim success.

## Why

The main reason for this design is that an agent's context window is temporary,
but project state needs to survive.

Before this exercise, it would be easy for me to think of the conversation as
the agent's memory. Evolution 6 showed me that important state should instead
be written to durable artifacts with a clear source of truth.

The handoff is especially useful because it forces me to state exactly what
another session needs instead of assuming the next model will somehow know
what happened.

## Judgment Loop

### Observe

Session A produced six user turns but twelve actual model calls. Provider token
usage showed that the working context was already larger than my deliberately
small 8,000-token design budget.

### Judge

Depending only on conversational history would make continuation difficult to
verify. I needed durable state, an explicit keep list, and a clear precedence
rule.

### Act

I implemented a budget meter, compactor, handoff writer, resume loader, and
append-only runtime ledger. I also created L1/L2/L3 rules and tested them with
a deliberately stale L3 view.

### Verify

The unit tests passed.

A fresh Session B followed the handoff's first action without Session A's
transcript and asked no already-answered questions.

When L3 contradicted the runtime ledger, Session B correctly followed L2.

### Learn

Context engineering is not just trying to fit more text into a prompt. It is
deciding what must survive, where it should live, how it should be measured,
and which source wins when information disagrees.
