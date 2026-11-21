"""Offline validation of attributed availability and role archives.

This interface validates an independently captured observation and its receipt.
It neither acquires source material nor issues evidence for LIVE admission.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from fifth_pick.config import load_configs
from fifth_pick.evidence import EvidenceKind
from fifth_pick.models import Provenance
from fifth_pick.receipts import Receipt
from fifth_pick.snapshots import T20_OFFSET
from fifth_pick.sources.availability import _STATUSES
from fifth_pick.sources.base import LiveAuthorizationError, MalformedPayloadError, SourceEvent
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    payload_hash,
    require_fresh,
)
from fifth_pick.t20_review import review_window_allows

_DATA_SCOPES = {
    EvidenceKind.AVAILABILITY: "injury and availability status",
    EvidenceKind.TEAMMATE_ABSENCE: "teammate absence",
    EvidenceKind.ROLE_MINUTES: "role and minutes",
}


@dataclass(frozen=True, slots=True)
class ContextObservation:
    kind: EvidenceKind
    candidate_player_id: str
    subject_player_id: str
    team: str
    event_id: str
    phase: str
    excerpt: str
    facts: tuple[tuple[str, str | int | float], ...]
    provenance: Provenance
    capture_receipt: Receipt


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise MalformedPayloadError("context archive requires nonempty printable text")
    return value


def _facts(
    kind: EvidenceKind, value: object, player: str, team: str, roster: Mapping[str, str]
) -> tuple[str, dict[str, str | int | float]]:
    if not isinstance(value, dict):
        raise MalformedPayloadError("context archive requires attributed facts")
    if kind is EvidenceKind.AVAILABILITY:
        if value.keys() == {"status"} and _text(value.get("status")) in _STATUSES:
            return player, {"status": value["status"]}
    elif kind is EvidenceKind.TEAMMATE_ABSENCE:
        teammate = _text(value.get("teammate_id"))
        if (
            value.keys() == {"status", "teammate_id"}
            and value["status"] == "OUT"
            and teammate != player
            and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", teammate)
            and roster.get(teammate) == team
        ):
            return teammate, {"status": "OUT", "teammate_id": teammate}
    elif value.keys() == {"role", "minutes_low", "minutes_high"}:
        role = _text(value["role"])
        low, high = value["minutes_low"], value["minutes_high"]
        if (
            all(type(n) in (int, float) and math.isfinite(n) for n in (low, high))
            and 0 <= low <= high
        ):
            return player, {"role": role, "minutes_low": low, "minutes_high": high}
    raise MalformedPayloadError("context fact is ambiguous, contradictory, or outside scope")


def validate_context_observation(
    body: bytes,
    source_body: bytes,
    capture_receipt: Receipt,
    *,
    run_id: str,
    event: SourceEvent,
    candidate_player_id: str,
    event_roster: Mapping[str, str],
    phase: str,
    as_of: datetime,
    max_age: timedelta,
) -> ContextObservation:
    """Check supplied bytes and receipt against the current source registry.

    The caller supplies an independently trusted event roster, capture receipt,
    and freshness bound. The archived excerpt must appear verbatim in the source
    bytes. This verifies scope and integrity, but cannot authenticate a publisher
    or establish that a human's interpretation of an excerpt is correct.
    """
    if len(body) > 65_536 or not source_body or len(source_body) > 1_048_576:
        raise MalformedPayloadError("context archive is missing or exceeds its byte limits")
    try:
        raw = decode_payload(body)
        if not isinstance(raw, dict) or raw.keys() != {
            "event_id",
            "player_id",
            "team",
            "phase",
            "kind",
            "source_id",
            "access_method",
            "reference",
            "source_timestamp",
            "source_sha256",
            "excerpt",
            "fact",
        }:
            raise MalformedPayloadError("invalid context observation envelope")
        kind = EvidenceKind(raw["kind"])
        if kind not in _DATA_SCOPES:
            raise MalformedPayloadError("context evidence kind is outside the ingestion scope")

        source_id, method = _text(raw["source_id"]), _text(raw["access_method"])
        if not any(
            source.source_id == source_id
            and source.access_method == method
            and source.terms_review_status == "approved"
            and _DATA_SCOPES[kind] in source.approved_data
            for source in load_configs().approved_sources.sources
        ):
            raise LiveAuthorizationError("context source, data scope, or delivery is not approved")
        reference = _text(raw["reference"])
        url = urlsplit(reference)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.query
            or url.fragment
            or url.path.lower().startswith("/stats/")
            or url.hostname.lower() == "stats.nba.com"
        ):
            raise MalformedPayloadError("invalid or prohibited context reference")
        team = _text(raw["team"])
        excerpt = _text(raw["excerpt"])
        source_digest, archive_digest = payload_hash(source_body), payload_hash(body)
        captured = aware_timestamp(capture_receipt.timestamp)
        observed = aware_timestamp(raw["source_timestamp"])
        target = event.commence_time - T20_OFFSET
        require_fresh(observed, as_of, max_age)
        if (
            event.commence_time.utcoffset() is None
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", candidate_player_id)
            or raw["event_id"] != event.event_id
            or raw["player_id"] != candidate_player_id
            or raw["phase"] != phase
            or len({event.home_team, event.away_team}) != 2
            or team not in (event.home_team, event.away_team)
            or event_roster.get(candidate_player_id) != team
            or raw["source_sha256"] != source_digest
            or excerpt.encode() not in source_body
            or not observed <= captured <= as_of
            or not (
                phase == "analysis"
                and as_of < target
                or phase == "t20"
                and target <= captured
                and review_window_allows(target, as_of, live=True)
            )
        ):
            raise MalformedPayloadError("context scope, archive bytes, or phase chronology differs")
        if capture_receipt != Receipt(
            captured.isoformat(),
            "CONTEXT_OBSERVATION_ARCHIVED",
            "CAPTURED",
            f"{event.event_id}:{candidate_player_id}:{phase}",
            source_id,
            archive_digest,
            run_id,
            f"context-observation-{archive_digest}",
        ):
            raise MalformedPayloadError("context capture receipt does not bind these exact bytes")
        subject, facts = _facts(kind, raw["fact"], candidate_player_id, team, event_roster)
    except (ValueError, OverflowError, RecursionError) as exc:
        raise MalformedPayloadError("invalid offline context observation") from exc
    return ContextObservation(
        kind,
        candidate_player_id,
        subject,
        team,
        event.event_id,
        phase,
        excerpt,
        tuple(sorted(facts.items())),
        Provenance(source_id, captured, observed, method, reference, source_digest),
        capture_receipt,
    )
