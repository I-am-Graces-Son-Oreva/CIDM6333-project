"""Validate one exact row from the NBA's layout-preserving injury-report text."""

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from fifth_pick.evidence import EvidenceEffect, EvidenceItem, EvidenceKind, EvidenceSignificance
from fifth_pick.models import Evidence, Provenance
from fifth_pick.personal_readiness import LiveEventScope
from fifth_pick.receipts import Receipt
from fifth_pick.sources.alias_crosswalk import BoardIdentity, RosterIdentity, join_event_aliases
from fifth_pick.sources.availability import InjuryDocument, read_official_document
from fifth_pick.sources.base import (
    EvidenceMode,
    LiveAuthorizationError,
    MalformedPayloadError,
    SourceError,
    SourceEvent,
)
from fifth_pick.sources.supporting_fixture import payload_hash
from fifth_pick.storage import RunStore, collection_lock

_EDITION = re.compile(r"^(?:NBA )?Injury Report:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_EVENT = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2})\s+\(ET\)\s+([A-Z]+@[A-Z]+)$")
_STATUSES = {"AVAILABLE", "PROBABLE", "QUESTIONABLE", "DOUBTFUL", "OUT"}
_MAX_PDF_BYTES = 8 * 1024 * 1024
_PDFKIT_SCRIPT = """
ObjC.import("PDFKit");
function run(args) {
    const doc = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(args[0]));
    const count = doc.pageCount;
    if (doc.isLocked || !count || count > 128) throw Error("Unsupported PDF");
    const pages = [];
    for (let index = 0; index < count; index++) {
        const text = ObjC.unwrap(doc.pageAtIndex(index).string);
        if (typeof text !== "string" || !text.trim()) throw Error("Unreadable page");
        pages.push(text);
    }
    return pages.join("\\f");
}
"""


def extract_injury_pdf_text(body: bytes) -> str:
    """Run a local layout extractor without passing credentials or permitting shell expansion."""
    executable = shutil.which("pdftotext")
    if not body or len(body) > _MAX_PDF_BYTES:
        raise MalformedPayloadError("official injury PDF exceeds the extraction bound")
    clean_environment = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}
    try:
        if executable:
            result = subprocess.run(
                [executable, "-layout", "-enc", "UTF-8", "-", "-"],
                input=body,
                env=clean_environment,
                capture_output=True,
                check=True,
                timeout=10,
            )
        elif sys.platform == "darwin":
            with TemporaryDirectory(prefix="fifth-pick-pdf-") as directory:
                path = Path(directory) / "report.pdf"
                path.write_bytes(body)
                result = subprocess.run(
                    ["/usr/bin/osascript", "-l", "JavaScript", "-e", _PDFKIT_SCRIPT, str(path)],
                    env=clean_environment,
                    capture_output=True,
                    check=True,
                    timeout=10,
                )
        else:
            raise SourceError("official injury PDF extraction requires pdftotext or macOS PDFKit")
        if len(result.stdout) > _MAX_PDF_BYTES:
            raise MalformedPayloadError("official injury PDF text exceeds the extraction bound")
        return result.stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise MalformedPayloadError("official injury PDF could not be extracted") from exc


def read_injury_status(
    document: InjuryDocument,
    *,
    tipoff: datetime,
    matchup: str,
    team: str,
    verified_label: str,
    extract: Callable[[bytes], str] = extract_injury_pdf_text,
) -> str:
    """Return a status only when document edition, tipoff and exact identity agree."""
    if (
        tipoff.utcoffset() is None
        or document.published_at.utcoffset() is None
        or document.retrieved_at.utcoffset() is None
        or not document.published_at <= document.retrieved_at < tipoff
        or not matchup
        or not team
        or not verified_label
        or len(document.body) > _MAX_PDF_BYTES
        or not document.body.startswith(b"%PDF-")
        or not document.body.rstrip().endswith(b"%%EOF")
        or payload_hash(document.body) != document.payload_sha256
    ):
        raise MalformedPayloadError("official injury PDF or game scope is invalid")
    text = extract(document.body)
    eastern = ZoneInfo("America/New_York")
    editions = _EDITION.findall(text)
    if not editions:
        raise MalformedPayloadError("official injury PDF lacks its publication header")
    for edition in editions:
        try:
            observed = datetime.strptime(edition.strip(), "%m/%d/%y %I:%M %p")
        except ValueError as exc:
            raise MalformedPayloadError(
                "official injury PDF has an invalid edition header"
            ) from exc
        if observed != document.published_at.astimezone(eastern).replace(tzinfo=None):
            raise MalformedPayloadError("official injury PDF publication differs from its edition")

    expected = tipoff.astimezone(eastern)
    expected_scope = (expected.strftime("%m/%d/%Y"), expected.strftime("%I:%M"), matchup)
    collapsed_row = re.compile(
        rf"^{re.escape(expected_scope[0])} +{re.escape(expected_scope[1])}"
        rf" +\(ET\) +{re.escape(matchup)} +{re.escape(team)} +{re.escape(verified_label)}"
        r" +([A-Za-z]+)(?: +.*)?$"
    )
    event_scope = None
    current_team = None
    statuses = []
    for line in text.splitlines():
        flat = collapsed_row.fullmatch(line.strip())
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) == 1 and flat:
            status = flat[1].upper()
            if status not in _STATUSES:
                raise MalformedPayloadError("official injury PDF row status is unknown")
            statuses.append(status)
            event_scope = current_team = None
            continue
        if parts[0].startswith(("Game Date", "Page ", "NBA Injury Report", "Injury Report:")):
            event_scope = None
            current_team = None
            continue
        event = _EVENT.fullmatch(" ".join(parts[:3]))
        if event:
            event_scope = event.groups()
            current_team = None
            parts = parts[3:]
        elif re.match(r"\d{2}/\d{2}/\d{4}|\d{1,2}:\d{2}\s+\(ET\)", line.strip()):
            event_scope = None
            current_team = None
        if len(parts) >= 2 and "," in parts[1] and "," not in parts[0]:
            current_team = parts[0]
            parts = parts[1:]
        elif not parts or "," not in parts[0]:
            current_team = None
        if event_scope != expected_scope or current_team != team or parts[:1] != [verified_label]:
            continue
        if len(parts) < 2 or parts[1].upper() not in _STATUSES:
            raise MalformedPayloadError("official injury PDF row status is unknown")
        statuses.append(parts[1].upper())
    if len(statuses) != 1:
        raise MalformedPayloadError("official injury PDF row is absent or ambiguous")
    return statuses[0]


def record_injury_identity(
    store: RunStore,
    run_id: str,
    scope: LiveEventScope,
    *,
    roster: RosterIdentity,
    report_identity: BoardIdentity,
    matchup: str,
    confirmed_at: datetime,
    authorized: bool = False,
) -> None:
    """Bind a report label to a corroborated event roster identity after owner review."""
    if not authorized or confirmed_at.utcoffset() is None or confirmed_at >= scope.tipoff:
        raise LiveAuthorizationError("injury identity requires explicit pre-tipoff approval")
    if not re.fullmatch(r"[A-Z]+@[A-Z]+", matchup):
        raise MalformedPayloadError("invalid official injury report matchup")
    aliases, references = join_event_aliases(scope, (roster,), (report_identity,))
    if aliases != {report_identity.provider_label: roster.canonical_id}:
        raise MalformedPayloadError("injury report identity is not independently corroborated")
    key = f"official-injury-identity-{scope.event_id}-{roster.canonical_id}"
    reason = json.dumps(
        {
            "label": report_identity.provider_label,
            "team": roster.team,
            "matchup": matchup,
            "references": references[report_identity.provider_label],
            "tipoff": scope.tipoff.isoformat(),
        },
        sort_keys=True,
    )
    with collection_lock(store, run_id):
        store.append_receipt(
            Receipt(
                confirmed_at.isoformat(),
                "OFFICIAL_INJURY_IDENTITY",
                "AUTHORIZED",
                roster.canonical_id,
                "fifth-pick",
                reason,
                run_id,
                key,
            )
        )


def live_injury_items(
    store: RunStore,
    run_id: str,
    *,
    event: SourceEvent,
    player_id: str,
    candidate_key: str,
    phase: str,
    as_of: datetime,
) -> tuple[EvidenceItem, ...]:
    key = f"official-injury-identity-{event.event_id}-{player_id}"
    bindings = [row for row in store.read_receipts(run_id) if row["event_key"] == key]
    if not bindings:
        return ()
    if len(bindings) != 1:
        raise MalformedPayloadError("official injury identity is ambiguous")
    row = bindings[0]
    try:
        scope = json.loads(row["reason"] or "")
        from fifth_pick.sources.supporting_fixture import aware_timestamp

        confirmed = aware_timestamp(row["timestamp"])
        if (
            row
            != Receipt(
                confirmed.isoformat(),
                "OFFICIAL_INJURY_IDENTITY",
                "AUTHORIZED",
                player_id,
                "fifth-pick",
                json.dumps(scope, sort_keys=True),
                run_id,
                key,
            ).to_dict()
            or scope["team"] not in (event.home_team, event.away_team)
            or aware_timestamp(scope["tipoff"]) != event.commence_time
            or not scope["references"].strip()
            or confirmed > as_of
        ):
            raise ValueError
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise MalformedPayloadError("official injury identity receipt is invalid") from exc
    document = read_official_document(store, run_id, phase=phase, as_of=as_of)
    if document is None:
        return ()
    status = read_injury_status(
        document,
        tipoff=event.commence_time,
        matchup=scope["matchup"],
        team=scope["team"],
        verified_label=scope["label"],
    )
    excerpt = f"Official report lists {player_id} as {status} for event {event.event_id}"
    return (
        EvidenceItem(
            f"official-injury-{phase}-availability",
            candidate_key,
            EvidenceKind.AVAILABILITY,
            Evidence(
                excerpt,
                Provenance(
                    "official-nba-injury-report",
                    document.retrieved_at,
                    document.published_at,
                    "official-nba-injury-report:direct-pdf",
                    document.reference,
                    document.payload_sha256,
                ),
                excerpt,
            ),
            EvidenceMode.LIVE,
            EvidenceEffect.NEUTRAL,
            EvidenceSignificance.IMPORTANT,
            facts={"canonical_player_id": player_id, "event_id": event.event_id, "status": status},
        ),
    )
