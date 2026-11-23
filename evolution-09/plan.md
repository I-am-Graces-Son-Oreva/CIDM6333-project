# E9 implementation plan

1. Record the candidate falsehood, route, budget, observable test points, and prerequisites in the flight card before the graded run.
2. Use the E8 handoff contract. Store worker text as an unverified ledger claim. Derive receipts from a harness-owned test command and bind the receipt to the command, output, execution time, and Git commit.
3. Route worker and adversary calls through an explicit free-only configuration. Validate adjudications and receipt citations. Record actual usage from OpenCode events.
4. Serialize TTL expiry and reclaim with an OS lock while retaining atomic creation of the resource lock. Exercise denial, expiry, and token-checked release outside the graded run using unit tests.
5. Verify with offline tests. Publish the preflight and record any unmet prerequisites without running a graded test point.
