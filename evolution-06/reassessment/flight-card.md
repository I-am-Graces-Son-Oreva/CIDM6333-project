# Follow-up card · E6 and E7

This is a separate local-model witness for two missing observables. It
preserves the original OpenCode E6 evidence and E7 aborts.

- **Route** · Ollama on loopback, Llama 3.2 3B, no tools exposed to the model,
  no remote services, six model calls at $0.00. Synthetic fixtures only.
- **E6** · A single project session calls the model with disposable history,
  compacts the history using the E6 keep-list helper, then calls the model
  again with the compacted state. The next action must match the retained
  synthetic instruction, and provider input usage must decrease. This
  exercises project-managed compaction. Native OpenCode auto-compaction and
  its provider threshold are outside this witness.
- **E7** · Four independent requests use the same model and contract.
  OFF gets no retrieval. ON gets a result from the existing E7 retriever.
  ABSENT has a populated store but an unrelated query. EVICT repeats the
  ON query after expiry and is checked against the eviction event.
  The model must give the unique synthetic value only in ON and answer
  UNKNOWN in all other conditions. The model can see only the request body.
  This is a bounded alternate harness, separate from the original native
  OpenCode route and its OS isolation requirement.
- **Falsifiers** · Wrong session or action, failed reduction, incorrect
  before/after ordering, unexpected disclosure in a negative condition,
  absent retrieval receipt in ON, or absent eviction event.
- **Abort** · Local model failure or missing provider usage.

## CHASE

GO — Codex independent Chase — 2026-11-24 — e6147aa

Scope: alternate local E6/E7 controls.
