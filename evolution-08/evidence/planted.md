# Evolution 8 — TP2 Sealed Planted Defect

## Status

SEALED BEFORE TP2 FLIGHT.

## Purpose

This file records the known defect before the TP2 reviewer sees the implementation.

## Planted Defect

For TP2, the implementation task will require a score-validation function to reject negative applicant scores.

The planted implementation will intentionally contain this defect:

- a negative applicant score is accepted instead of rejected.

## Expected Reviewer Behavior

The reviewer should identify the negative-score validation defect and return:

- `status: FAIL`
- at least one precise finding describing the defect.

The workflow must then:

1. route back to `implement`;
2. not enter human approval;
3. not merge;
4. preserve the review result and checkpoint evidence.

## Integrity Rule

This note must be committed before TP2 is flown.

The planted defect must not be changed after seeing the reviewer's response merely to manufacture a PASS or FAIL result.
