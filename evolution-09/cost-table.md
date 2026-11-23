# Sortie 9 cost table

Attempt 1 has one started free worker invocation. It returned no verified
token counts or cost. See the [abort record](evidence/attempt-1/abort.md).
No paid fallback was configured.

The re-flight has a maximum external provider cost of **$0.00**. Both models
are installed locally. The router records the Ollama input and output token
counts for every completed call, and the harness writes the measured cost
table alongside the re-flight ledger.
