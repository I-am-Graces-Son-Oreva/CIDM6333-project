import sys
import unittest
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from fifth_pick.sources.availability import FixtureInjuryDocument
from fifth_pick.sources.base import SourceError

NOW = datetime(2026, 11, 18, 17, tzinfo=UTC)
BODY = b"%PDF-1.7\nsynthetic\n%%EOF"
REPORT = """NBA Injury Report: 11/18/26 12:00 PM
Game Date    Game Time    Matchup    Team    Player Name    Current Status    Reason
11/18/2026   07:00 (ET)   BOS@DAL    Dallas Mavericks    Doncic, Luka    Available    Synthetic
                                    Boston Celtics      Example, Player  Out          Synthetic
Page 1 of 1
"""


class InjuryPdfTests(unittest.TestCase):
    def test_official_archive_is_exact_and_superseded_edition_blocks(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from fifth_pick.sources.availability import (
            acquire_official_document,
            read_official_document,
        )
        from fifth_pick.sources.base import EvidenceMode
        from fifth_pick.sources.transport import HttpResponse
        from fifth_pick.storage import RunStore

        policy = SimpleNamespace(
            approved_sources=SimpleNamespace(
                sources=(
                    SimpleNamespace(
                        source_id="official-nba-injury-report",
                        access_method="official-nba-injury-report:direct-pdf",
                        terms_review_status="approved",
                    ),
                )
            )
        )
        transport = Mock(evidence_mode=EvidenceMode.LIVE)
        transport.get.return_value = HttpResponse(200, {"Content-Type": "application/pdf"}, BODY)
        prefix = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-18_"
        with (
            TemporaryDirectory() as directory,
            patch("fifth_pick.sources.availability.load_configs", return_value=policy),
        ):
            store = RunStore(directory)
            for minute in (0, 5):
                when = NOW + timedelta(minutes=minute)
                document = acquire_official_document(
                    store,
                    "injury-run",
                    transport=transport,
                    reference=f"{prefix}12_{minute:02d}PM.pdf",
                    published_at=when,
                    phase="analysis",
                    max_age=timedelta(minutes=10),
                    clock=lambda at=when: at,
                    authorized=True,
                )
            restored = read_official_document(
                store,
                "injury-run",
                phase="analysis",
                as_of=NOW + timedelta(minutes=6),
            )
            self.assertEqual(restored, document)
            for path in store.run_directory("injury-run").glob("*.pdf"):
                path.write_bytes(BODY + b" ")
            with self.assertRaisesRegex(SourceError, "digest"):
                read_official_document(
                    store,
                    "injury-run",
                    phase="analysis",
                    as_of=NOW + timedelta(minutes=6),
                )

    @unittest.skipUnless(sys.platform == "darwin", "requires macOS PDFKit")
    def test_pdfkit_extracts_actual_pdf_bytes_without_poppler(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from fifth_pick.personal_readiness import LiveEventScope
        from fifth_pick.sources.alias_crosswalk import BoardIdentity, RosterIdentity
        from fifth_pick.sources.availability import acquire_official_document
        from fifth_pick.sources.base import EvidenceMode, SourceEvent
        from fifth_pick.sources.injury_pdf import live_injury_items, record_injury_identity
        from fifth_pick.sources.transport import HttpResponse
        from fifth_pick.storage import RunStore

        lines = [line.replace("(", r"\(").replace(")", r"\)") for line in REPORT.splitlines()[:3]]
        stream = ("BT /F1 10 Tf 12 TL 30 70 Td (" + ") Tj T* (".join(lines) + ") Tj ET").encode()
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 850 100]"
            b" /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ]
        body = b"%PDF-1.4\n"
        offsets = []
        for number, obj in enumerate(objects, 1):
            offsets.append(len(body))
            body += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
        trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{len(body)}\n%%EOF"
        body += b"xref\n0 6\n0000000000 65535 f \n"
        body += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
        body += trailer.encode()
        policy = SimpleNamespace(
            approved_sources=SimpleNamespace(
                sources=(
                    SimpleNamespace(
                        source_id="official-nba-injury-report",
                        access_method="official-nba-injury-report:direct-pdf",
                        terms_review_status="approved",
                    ),
                )
            )
        )
        tipoff = NOW.replace(hour=0, day=19)
        event = SourceEvent("injury-event", "Dallas Mavericks", "Boston Celtics", tipoff, ())
        transport = Mock(evidence_mode=EvidenceMode.LIVE)
        transport.get.return_value = HttpResponse(200, {"Content-Type": "application/pdf"}, body)
        with (
            TemporaryDirectory() as directory,
            patch("fifth_pick.sources.injury_pdf.shutil.which", return_value=None),
            patch("fifth_pick.sources.availability.load_configs", return_value=policy),
        ):
            store = RunStore(directory)
            document = acquire_official_document(
                store,
                "injury-run",
                transport=transport,
                reference="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-18_12_00PM.pdf",
                published_at=NOW,
                phase="analysis",
                max_age=timedelta(minutes=10),
                authorized=True,
                clock=lambda: NOW,
            )
            scope = LiveEventScope(
                event.event_id, event.home_team, event.away_team, tipoff, ("luka-doncic",)
            )
            record_injury_identity(
                store,
                "injury-run",
                scope,
                roster=RosterIdentity("official-id", "luka-doncic", event.home_team, "roster"),
                report_identity=BoardIdentity(
                    "official-id", "Doncic, Luka", event.event_id, event.home_team, "report-binding"
                ),
                matchup="BOS@DAL",
                confirmed_at=NOW,
                authorized=True,
            )
            (item,) = live_injury_items(
                store,
                "injury-run",
                event=event,
                player_id="luka-doncic",
                candidate_key="a" * 64,
                phase="analysis",
                as_of=NOW,
            )
            self.assertEqual(item.evidence.provenance.payload_hash, document.payload_sha256)
            self.assertEqual(dict(item.facts or {})["status"], "AVAILABLE")

    def test_unapproved_official_delivery_stops_before_transport(self):
        from fifth_pick.sources.availability import acquire_official_document
        from fifth_pick.sources.base import EvidenceMode
        from fifth_pick.storage import RunStore

        transport = Mock(evidence_mode=EvidenceMode.LIVE)
        with (
            TemporaryDirectory() as directory,
            self.assertRaisesRegex(SourceError, "delivery is not approved"),
        ):
            acquire_official_document(
                RunStore(directory),
                "injury-run",
                transport=transport,
                reference="https://ak-static.cms.nba.com/referee/injury/"
                "Injury-Report_2026-11-18_12_00PM.pdf",
                published_at=NOW,
                phase="analysis",
                max_age=timedelta(minutes=10),
                clock=lambda: NOW,
                authorized=True,
            )
        transport.get.assert_not_called()

    def test_exact_scope_and_edition(self):
        from fifth_pick.sources.injury_pdf import read_injury_status

        doc = FixtureInjuryDocument(
            "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-18_12_00PM.pdf",
            NOW,
            NOW,
            sha256(BODY).hexdigest(),
            BODY,
        )

        def read(report):
            return read_injury_status(
                doc,
                tipoff=NOW.replace(hour=0, day=19),
                matchup="BOS@DAL",
                team="Dallas Mavericks",
                verified_label="Doncic, Luka",
                extract=lambda raw: report if raw == BODY else "",
            )

        self.assertEqual(read(REPORT), "AVAILABLE")
        self.assertEqual(
            read(
                REPORT.replace(
                    "Dallas Mavericks    Doncic, Luka    Available",
                    "Dallas Mavericks    Earlier, Player    Out\n"
                    "                                    Doncic, Luka    Available",
                )
            ),
            "AVAILABLE",
        )
        for report in (
            REPORT.replace("12:00 PM", "01:00 PM"),
            REPORT.replace("BOS@DAL", "NYK@DAL"),
            REPORT.replace("Doncic, Luka", "Doncic, Someone"),
            REPORT.replace("Available", "UNKNOWN"),
            REPORT.replace("07:00 (ET)", "07:30 (ET)"),
        ):
            with self.assertRaises(SourceError):
                read(report)
