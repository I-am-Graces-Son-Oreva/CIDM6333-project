# Approved LIVE operational amendment — November 18, 2026

Joseph approved these implementation decisions on November 18, 2026. The
[November 13 frozen design](../superpowers/specs/2026-11-13-fifth-pick-design.md)
and earlier milestone evidence remain intact. This record states the approved
operational timing and release interpretation. It does not authorize a source
subscription, paid request, new player grant, or LIVE acceptance.

## Observation and release

- Accept on-time Snapshot 3 from T−25 through T−20, inclusive, with actual
  provider and application timestamps. Keep existing Snapshot 1 and 2 rules.
- In LIVE, moving evidence must be retrieved from T−20 through the actual
  review completion time. The review completion window is T−20 through T−15,
  inclusive. Record the application clock. An out-of-window review cannot
  retain the candidate, and missing required facts remain an evidence gap.
- Use one receipt-bound official slate, one frozen capped candidate pool, and
  each event's own timing. Wait for outstanding in-window reviews. Omit a
  candidate once its decision window is lost. Do not refill. A proposal and
  any approval must be pre-tipoff for all included events.
- Demo timing remains deterministic and the accepted historical milestone
  examples keep their exact recorded time semantics.

## Review and decision

Use the existing native review and dispatch commands with the exact
`review-material` envelope. The Controller may dispatch Builder only when
this response created the one persisted M2 revision attempt. A product
correction is subset-only. Use `review-correct` to remove exact cited keys
after the confirmed Builder attempt. A second review must use the returned
revision-1 envelope on the original cycle. The original artifact and revised
proposal digest are retained. A mismatched artifact or incomplete persistence
stops. No review or correction approves a selection.

CONCERNS and second FAIL stop automated correction. `review-status` and
`decide` display the verified original findings. Part III A18 permits Joseph
to reject or modify after seeing them, or to acknowledge CONCERNS for an
uncorrected exact proposal and explicitly approve with a reason. A corrected
proposal requires exact-version PASS. Second FAIL cannot be converted to PASS
by the controller. Native Reviewer permissions and the OpenCode 1.18.20
acceptance qualifications remain unchanged.

## Source and spending boundary

BALLDONTLIE is approved for evaluation only. The prepared parser and complete
pagination checks cannot create LIVE M6 evidence. Actual coverage, reliable
game timestamps and correction freshness remain unverified. An external
board-to-roster identity crosswalk needs corroborated stable IDs and source
references. A provider label alone is insufficient.

Proposed pilot ceiling remains 19 Odds API credits, with 15 for one event's
three boards and four for two approved one-group totals/spreads observations.
Zero retries. Access to supporting providers and any purchase are separate
explicit decisions. No spending was approved in the amendment.
