"""One-game evidence packages built entirely from synthetic bytes."""

import json
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from fifth_pick.evidence import history_line_outcome
from fifth_pick.models import Category
from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.dunkapi_evidence_package import replay_evidence_package
from tests.test_dunkapi_replay import REGISTRY, ROW, SCOPE, archives, digest, encoded

SINGLE_GAME_SCOPE = replace(SCOPE, first_date=date(2026, 12, 30), last_date=date(2026, 12, 30))
AS_OF = datetime(2027, 1, 2, 3, tzinfo=UTC)
EVENT_TEAMS = ("Golden State Warriors", "Los Angeles Lakers")


def package(row=ROW, *, previous=None):
    identity, pages, timing = archives(row)
    timing["request"] |= {"first_date": "2026-12-30", "last_date": "2026-12-30"}
    if previous is not None:
        timing["retrieved_at"] = "2027-01-02T02:18:00Z"
    timing_bytes = encoded(timing)
    subject = {
        "event_id": "synthetic-event",
        "event_teams": list(EVENT_TEAMS),
        "canonical_player_id": "stephen-curry",
        "game_id": "901",
        "request": timing["request"],
    }
    coverage = {
        "kind": "history-coverage",
        "subject": subject,
        "game_ids": ["901"],
        "complete": True,
        "observed_at": "2027-01-02T02:19:00Z" if previous else "2027-01-02T00:10:00Z",
        "reference": "synthetic:separate-game-inventory",
    }
    correction = {
        "kind": "history-correction-check",
        "subject": subject,
        "observed_at": "2027-01-02T02:25:00Z" if previous else "2027-01-02T02:00:00Z",
        "reference": "synthetic:separate-stat-check",
        "stats": {"points": row["pts"], "rebounds": 6, "assists": 7, "minutes": 31.5},
    }
    manifest = {
        "subject": subject,
        "provenance": "synthetic",
        "version": 1,
        "previous_sha256": None,
        "sealed_at": "2027-01-02T02:15:00Z",
        "corroboration_sha256": digest(timing_bytes),
        "pages": [{**timing["pages"][0], "retrieved_at": timing["retrieved_at"]}],
    }
    if previous is not None:
        manifest.update(
            version=2, previous_sha256=digest(previous), sealed_at="2027-01-02T02:30:00Z"
        )
    return identity, pages, timing_bytes, coverage, correction, manifest


def seal(coverage, correction, manifest):
    return encoded(
        manifest
        | {
            "coverage": {"reference": coverage["reference"], "sha256": digest(encoded(coverage))},
            "correction": {
                "reference": correction["reference"],
                "sha256": digest(encoded(correction)),
            },
        }
    )


class DunkApiEvidencePackageTests(unittest.TestCase):
    def test_replayed_stat_categories_support_exact_higher_lower_and_push_comparisons(self):
        game = self.replay(*package()).game
        for category, expected in (
            (Category.POINTS, 21),
            (Category.REBOUNDS, 6),
            (Category.ASSISTS, 7),
            (Category.PRA, 34),
            (Category.REBOUNDS_ASSISTS, 13),
        ):
            with self.subTest(category=category):
                value = game.sample(category).value
                self.assertEqual(value, expected)
                self.assertEqual(history_line_outcome(value, expected - 0.5), "HIGHER")
                self.assertEqual(history_line_outcome(value, expected + 0.5), "LOWER")
                self.assertEqual(history_line_outcome(value, expected), "PUSH")

    def replay(
        self,
        identity,
        pages,
        timing,
        coverage,
        correction,
        manifest,
        *,
        sealed=None,
        anchor=None,
        previous=None,
        scope=SINGLE_GAME_SCOPE,
    ):
        sealed = seal(coverage, correction, manifest) if sealed is None else sealed
        return replay_evidence_package(
            sealed,
            identity_body=identity,
            pages=pages,
            corroboration_body=timing,
            coverage_body=encoded(coverage),
            correction_body=encoded(correction),
            expected_manifest_sha256=digest(sealed) if anchor is None else anchor,
            previous_manifest_body=previous,
            scope=scope,
            registry=REGISTRY,
            canonical_player_id="stephen-curry",
            event_id="synthetic-event",
            event_teams=EVENT_TEAMS,
            game_id="901",
            as_of=AS_OF,
            coverage_max_age=timedelta(hours=3),
            correction_max_age=timedelta(hours=2),
        )

    def test_deterministic_synthetic_game(self):
        inputs = package()
        result = self.replay(*inputs)
        self.assertEqual(result, self.replay(*inputs))
        self.assertEqual(result.provenance, "synthetic")
        self.assertEqual(result.game.game_id, "901")
        self.assertEqual(result.game.completed_at.isoformat(), "2026-12-31T03:31:00+00:00")
        self.assertEqual(result.manifest_sha256, digest(seal(*inputs[-3:])))

    def test_timing_and_page_chronology_fail_closed(self):
        identity, pages, timing, coverage, correction, manifest = package()
        for stamp in ("2027-01-02T00:00:00", "2027-01-01T23:59:00Z", "2027-01-02T04:00:00Z"):
            changed = [{**manifest["pages"][0], "retrieved_at": stamp}]
            with self.subTest(stamp=stamp), self.assertRaises(MalformedPayloadError):
                self.replay(
                    identity, pages, timing, coverage, correction, manifest | {"pages": changed}
                )
        proof = json.loads(timing)
        for value in (None, "2026-12-31T01:00:00Z"):
            proof["games"][0]["actual_completed_at"] = value
            body = encoded(proof)
            with self.subTest(value=value), self.assertRaises(MalformedPayloadError):
                self.replay(
                    identity,
                    pages,
                    body,
                    coverage,
                    correction,
                    manifest
                    | {
                        "corroboration_sha256": digest(body),
                    },
                )
        with self.assertRaises(MalformedPayloadError):
            self.replay(identity, (), timing, coverage, correction, manifest)

    def test_coverage_and_correction_are_separate_and_fresh(self):
        identity, pages, timing, coverage, correction, manifest = package()
        cases = (
            (coverage | {"complete": False}, correction),
            (coverage | {"game_ids": []}, correction),
            (coverage | {"observed_at": "2027-01-01T23:59:59Z"}, correction),
            (coverage, correction | {"observed_at": "2027-01-02T00:30:00Z"}),
            (coverage, correction | {"stats": {**correction["stats"], "points": 22}}),
            (coverage, correction | {"reference": coverage["reference"]}),
            (coverage, coverage),
        )
        for cov, corr in cases:
            with self.subTest(cov=cov, corr=corr), self.assertRaises(MalformedPayloadError):
                self.replay(identity, pages, timing, cov, corr, manifest)

    def test_each_page_requires_its_own_ordered_retrieval(self):
        identity, pages, timing, coverage, correction, manifest = package()
        first = json.loads(pages[0][1])
        first["data"]["next_offset"] = 1
        terminal = {"data": {"player_id": "101", "count": 0, "games": [], "next_offset": None}}
        pages = ((0, encoded(first)), (1, encoded(terminal)))
        bindings = [{"offset": offset, "sha256": digest(body)} for offset, body in pages]
        proof = json.loads(timing)
        proof["request"]["max_pages"] = 2
        proof["pages"] = bindings
        timing = encoded(proof)
        subject = {**manifest["subject"], "request": proof["request"]}
        coverage = coverage | {"subject": subject}
        correction = correction | {"subject": subject}
        scope = replace(SINGLE_GAME_SCOPE, max_pages=2)
        manifest |= {"subject": subject, "corroboration_sha256": digest(timing)}
        first_page = bindings[0] | {"retrieved_at": proof["retrieved_at"]}
        for second_at, valid in (
            ("2027-01-02T00:05:00Z", True),
            (proof["retrieved_at"], False),
            ("2027-01-02T00:11:00Z", False),
        ):
            records = [first_page, bindings[1] | {"retrieved_at": second_at}]
            with self.subTest(second_at=second_at):
                updated = manifest | {"pages": records}
                if valid:
                    self.assertEqual(
                        self.replay(
                            identity, pages, timing, coverage, correction, updated, scope=scope
                        ).game.game_id,
                        "901",
                    )
                else:
                    with self.assertRaises(MalformedPayloadError):
                        self.replay(
                            identity, pages, timing, coverage, correction, updated, scope=scope
                        )

    def test_digest_reference_and_provenance_binding(self):
        identity, pages, timing, coverage, correction, manifest = package()
        sealed = seal(coverage, correction, manifest)
        for cov, corr in ((None, correction), (coverage, None)):
            with self.assertRaises(MalformedPayloadError):
                self.replay(identity, pages, timing, cov, corr, manifest, sealed=sealed)
        with self.assertRaises(MalformedPayloadError):
            self.replay(
                identity,
                pages,
                timing,
                coverage,
                correction,
                manifest,
                sealed=sealed + b" ",
                anchor=digest(sealed),
            )
        with self.assertRaises(MalformedPayloadError):
            self.replay(
                identity, ((0, pages[0][1] + b" "),), timing, coverage, correction, manifest
            )
        with self.assertRaises(MalformedPayloadError):
            self.replay(
                identity,
                pages,
                timing,
                coverage | {"complete": False},
                correction,
                manifest,
                sealed=sealed,
            )
        changed_ref = encoded(
            manifest
            | {
                "coverage": {"reference": "synthetic:other", "sha256": digest(encoded(coverage))},
                "correction": {
                    "reference": correction["reference"],
                    "sha256": digest(encoded(correction)),
                },
            }
        )
        with self.assertRaises(MalformedPayloadError):
            self.replay(identity, pages, timing, coverage, correction, manifest, sealed=changed_ref)
        with self.assertRaises(MalformedPayloadError):
            self.replay(
                identity,
                pages,
                timing,
                coverage,
                correction,
                manifest | {"provenance": "external-unverified"},
            )

    def test_correction_creates_a_version_and_prior_bytes_remain_replayable(self):
        first = package()
        previous = seal(*first[-3:])
        second = package(ROW | {"pts": 22}, previous=previous)
        updated = self.replay(*second, previous=previous)
        self.assertEqual((updated.version, updated.game.points), (2, 22))
        self.assertEqual(updated.previous_sha256, digest(previous))
        self.assertEqual(self.replay(*first, sealed=previous).game.points, 21)
        for prior in (None, previous + b" "):
            with self.subTest(prior=prior is not None), self.assertRaises(MalformedPayloadError):
                self.replay(*second, previous=prior)
        identity, pages, timing, coverage, correction, manifest = first
        with self.assertRaises(MalformedPayloadError):
            self.replay(
                identity,
                pages,
                timing,
                coverage,
                correction,
                manifest
                | {
                    "version": 2,
                    "previous_sha256": digest(previous),
                    "sealed_at": "2027-01-02T02:30:00Z",
                },
                previous=previous,
            )
