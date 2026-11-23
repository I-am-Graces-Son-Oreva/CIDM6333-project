# E11 guardrails

| ID | Mechanism and locus | Rule | Probe |
| --- | --- | --- | --- |
| G1 | Proposal shape, application receipt and approval checks in `fifth_pick.approval.load_approved_final` | A missing run record cannot yield a Joseph-approved selection. | A1, [receipt](receipts/A1.json) |
| G2 | Strict schema and duplicate-key rejection in `fifth_pick.review.parse_review_verdict` | Untrusted verdict bytes must decode to one unambiguous typed record. | A2 and A4, [A2 receipt](receipts/A2.json), [A4 receipt](receipts/A4.json) |
| G3 | Exact secret redaction in `fifth_pick.receipts.redact_text` | Caller-supplied secrets are scrubbed before evidence is emitted. | A3, [receipt](receipts/A3.json) |
| G4 | Exact canonical grant in `fifth_pick.authorization.AuthorizationGate.authorize` | A different direction is a different grant. | A5, [receipt](receipts/A5.json) |

The runner logs a digest at delivery, a distinct enforcement span and a
receipt with a safe reason. For A3 the redactor returns sanitized text
and the wrapper records that the original text was withheld. Only the
offline runner writes observability artifacts. The production checks
run against synthetic inputs or an empty temporary store.
