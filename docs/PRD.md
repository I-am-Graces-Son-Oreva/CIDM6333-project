# Product Requirements Document

## System

Graduate Application Identity-Assurance and Triage System

## User

The primary user is a graduate admissions staff member reviewing applications that may require identity or document verification.

## Problem

Graduate admissions staff may need to review many applications while deciding which records need additional human verification. The system should help organize evidence and identify items that deserve review without automatically rejecting applicants or accusing anyone of fraud.

## Product Goal

Provide bounded, evidence-based assistance for graduate application identity assurance and triage while keeping final admissions and fraud judgments with authorized humans.

## Acceptance Criteria

1. The system can answer a bounded question and stop without unnecessary additional work.
2. The primary OpenCode agent has a declared step limit.
3. When a task cannot be completed within the available steps, the agent stops tool calling and responds with text rather than continuing indefinitely.
4. The system distinguishes verified information from uncertainty.
5. The system does not automatically reject an applicant.
6. The system does not declare an applicant a fraudster.

## Boundaries

The system supports triage and verification. It does not make final admissions decisions and does not make final fraud determinations.

## Attestation

I, Joseph Edafiadhe, attest that this PRD represents the intended user, problem, boundaries, and acceptance criteria for this system.

Attested: 2026-11-09
