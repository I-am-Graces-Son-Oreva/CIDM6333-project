---
name: validate-evidence
description: Use when evidence for an NBA fantasy candidate must be checked for currentness, source trust, provenance, identity, integrity, or completeness.
---

# Validate Evidence

Use the existing M5/M6 evidence contracts and frozen source rules. An excerpt that sounds plausible is not, by itself, verified evidence.

## Procedure

1. Bind each evidence item to the exact candidate, event, platform, category, and direction it is offered to support. Keep PrizePicks and Underdog evidence separate.
2. Inspect the declared source, access method, source reference, retrieval time, source timestamp, retained payload or excerpt, and payload digest. Identify what bytes the digest is declared to cover before comparing it. A matching digest can show retained bytes match that digest; it does not prove source authenticity.
3. Use the typed M6 validator and preserve its result. Do not claim it checks a digest-to-excerpt relationship unless that check actually occurs in the current implementation. If a declared digest target is available and does not match, report the integrity conflict; if the target or bytes are unavailable, report that verification gap.
4. Treat an absent or unusable source timestamp as unknown currentness. Do not substitute retrieval time, guess a timestamp, repair a digest, edit an excerpt, or infer that the source claim is true or false.
5. Classify evidence problems using existing M6 reason codes and named gaps. Keep missing evidence distinct from evidence that contradicts a claim. Do not count an unusable item as support or risk evidence, and do not hide the gap from the candidate judgment.
6. Use only the authorized source and access method. M6 supporting-source retrieval is unavailable; do not fetch live evidence, scrape, or substitute an unapproved source. Explicit fixture evidence remains labeled as a fixture.

Return the evidence ID, the specific validation result, and the remaining gap or conflict. Candidate qualification and confidence remain the M6 evaluator's decision.
