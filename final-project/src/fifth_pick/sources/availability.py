"""Offline source-precedence boundary for normalized NBA availability fixtures."""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fifth_pick.config import load_configs
from fifth_pick.evidence import EvidenceItem, EvidenceKind
from fifth_pick.receipts import Receipt
from fifth_pick.sources.base import EvidenceMode, LiveAuthorizationError, MalformedPayloadError
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    fixture_evidence,
    fixture_provenance,
    payload_hash,
    require_fresh,
)
from fifth_pick.sources.transport import Transport
from fifth_pick.storage import RunStore, _atomic_write, collection_lock

_OFFICIAL = ("official-nba-injury-report", "nba-com")
_EDITORIAL = "sports-illustrated-nba"
_STATUSES = {"AVAILABLE", "PROBABLE", "QUESTIONABLE", "DOUBTFUL", "OUT"}
_MAX_PDF_BYTES = 8 * 1024 * 1024


def check_official_edition(
    reference: str, published_at: datetime, retrieved_at: datetime, max_age: timedelta
) -> None:
    """Verify the exact publisher and edition timestamp of a normalized report."""
    if published_at.utcoffset() is None:
        raise MalformedPayloadError("official injury edition requires a timezone-aware publication")
    require_fresh(published_at, retrieved_at, max_age)
    edition = published_at.astimezone(ZoneInfo("America/New_York"))
    suffix = edition.strftime("%Y-%m-%d_%I_%M%p")
    expected = f"https://ak-static.cms.nba.com/referee/injury/Injury-Report_{suffix}.pdf"
    if reference != expected or edition.second or edition.microsecond:
        raise MalformedPayloadError("official injury report edition and publication time disagree")


@dataclass(frozen=True, slots=True)
class InjuryDocument:
    reference: str
    published_at: datetime
    retrieved_at: datetime
    payload_sha256: str
    body: bytes


FixtureInjuryDocument = InjuryDocument


def _require_official_delivery() -> None:
    if not any(
        source.source_id == _OFFICIAL[0]
        and source.access_method == "official-nba-injury-report:direct-pdf"
        and source.terms_review_status == "approved"
        for source in load_configs().approved_sources.sources
    ):
        raise LiveAuthorizationError("official injury report delivery is not approved")


def acquire_official_document(
    store: RunStore,
    run_id: str,
    *,
    transport: Transport,
    reference: str,
    published_at: datetime,
    phase: str,
    max_age: timedelta,
    authorized: bool = False,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> InjuryDocument:
    """Fetch one known edition only after policy and explicit authorization agree."""
    _require_official_delivery()
    if (
        authorized is not True
        or getattr(transport, "evidence_mode", None) is not EvidenceMode.LIVE
        or phase not in ("analysis", "t20")
    ):
        raise LiveAuthorizationError("official injury report requires an authorized LIVE phase")
    with collection_lock(store, run_id):
        requested_at = clock()
        check_official_edition(reference, published_at, requested_at, max_age)
        key = f"official-injury-{phase}-{payload_hash(reference.encode())}"
        if any(row["event_key"] == key for row in store.read_receipts(run_id)):
            raise LiveAuthorizationError("this official injury edition was already attempted")
        store.append_receipt(
            Receipt(
                requested_at.isoformat(),
                "OFFICIAL_INJURY_REQUEST",
                "ATTEMPTED",
                phase,
                _OFFICIAL[0],
                json.dumps(
                    {
                        "reference": reference,
                        "published_at": published_at.isoformat(),
                        "max_age_seconds": max_age.total_seconds(),
                    },
                    sort_keys=True,
                ),
                run_id,
                key,
            )
        )
        body = _download_pdf(transport, reference)
        retrieved_at = clock()
        check_official_edition(reference, published_at, retrieved_at, max_age)
        if retrieved_at < requested_at:
            raise MalformedPayloadError("official injury retrieval predates its request")
        digest = payload_hash(body)
        path = store.run_directory(run_id) / f"{key}.pdf"
        if path.exists() or path.is_symlink():
            raise MalformedPayloadError("official injury archive path is already occupied")
        _atomic_write(path, body)
        store.append_receipt(
            Receipt(
                retrieved_at.isoformat(),
                "OFFICIAL_INJURY_RESPONSE",
                "DOCUMENT_CAPTURED",
                phase,
                _OFFICIAL[0],
                digest,
                run_id,
                f"{key}-response",
            )
        )
    return InjuryDocument(reference, published_at, retrieved_at, digest, body)


def read_official_document(
    store: RunStore, run_id: str, *, phase: str, as_of: datetime
) -> InjuryDocument | None:
    """Reopen the newest known edition for this phase, with no fallback after failure."""
    if phase not in ("analysis", "t20") or as_of.utcoffset() is None:
        raise MalformedPayloadError("official injury report requires an aware stage scope")
    rows = store.read_receipts(run_id)
    requests = [
        receipt
        for receipt in rows
        if receipt["event"] == "OFFICIAL_INJURY_REQUEST" and receipt["subject"] == phase
    ]
    if not requests:
        return None
    _require_official_delivery()
    prior = []
    for request in requests:
        requested_at = aware_timestamp(request["timestamp"])
        if requested_at > as_of:
            continue
        try:
            reason = json.loads(request["reason"] or "")
            published_at = aware_timestamp(reason["published_at"])
            reference = reason["reference"]
            seconds = reason["max_age_seconds"]
            if type(seconds) not in (int, float) or not math.isfinite(seconds):
                raise ValueError
            max_age = timedelta(seconds=seconds)
            key = f"official-injury-{phase}-{payload_hash(reference.encode())}"
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as exc:
            raise MalformedPayloadError("official injury request metadata is invalid") from exc
        check_official_edition(reference, published_at, requested_at, max_age)
        if (
            request
            != Receipt(
                requested_at.isoformat(),
                "OFFICIAL_INJURY_REQUEST",
                "ATTEMPTED",
                phase,
                _OFFICIAL[0],
                json.dumps(reason, sort_keys=True),
                run_id,
                key,
            ).to_dict()
        ):
            raise MalformedPayloadError("official injury receipt does not match the edition")
        prior.append((published_at, requested_at, reference, key, max_age))
    if not prior:
        return None
    published_at, requested_at, reference, key, max_age = max(prior)
    if sum(item[0] == published_at for item in prior) != 1:
        raise MalformedPayloadError("official injury edition is ambiguous")
    responses = [row for row in rows if row["event_key"] == f"{key}-response"]
    if len(responses) != 1:
        raise MalformedPayloadError("latest official injury edition has no exact response")
    response = responses[0]
    retrieved_at = aware_timestamp(response["timestamp"])
    check_official_edition(reference, published_at, as_of, max_age)
    path = store.run_directory(run_id) / f"{key}.pdf"
    if path.is_symlink():
        raise MalformedPayloadError("official injury archive path is invalid")
    try:
        body = path.read_bytes()
    except OSError as exc:
        raise MalformedPayloadError("official injury PDF archive is missing") from exc
    digest = payload_hash(body)
    if (
        not requested_at <= retrieved_at <= as_of
        or response
        != Receipt(
            retrieved_at.isoformat(),
            "OFFICIAL_INJURY_RESPONSE",
            "DOCUMENT_CAPTURED",
            phase,
            _OFFICIAL[0],
            digest,
            run_id,
            f"{key}-response",
        ).to_dict()
    ):
        raise MalformedPayloadError("official injury archive digest or retrieval does not match")
    return InjuryDocument(reference, published_at, retrieved_at, digest, body)


def replay_official_document(
    transport: Transport,
    *,
    reference: str,
    published_at: datetime,
    retrieved_at: datetime,
    max_age: timedelta,
) -> FixtureInjuryDocument:
    """Acquire document bytes in replay without asserting PDF contents or LIVE authority."""
    if getattr(transport, "evidence_mode", None) is not EvidenceMode.FIXTURE:
        raise LiveAuthorizationError("injury document replay requires a fixture transport")
    check_official_edition(reference, published_at, retrieved_at, max_age)
    body = _download_pdf(transport, reference)
    return InjuryDocument(reference, published_at, retrieved_at, payload_hash(body), body)


def _download_pdf(transport: Transport, reference: str) -> bytes:
    response = transport.get(reference, {"Accept": "application/pdf"})
    if response.status != 200:
        raise MalformedPayloadError(f"injury document returned HTTP {response.status}")
    content_types = [
        value.partition(";")[0].strip().lower()
        for name, value in response.headers.items()
        if name.lower() == "content-type"
    ]
    if (
        len(response.body) > _MAX_PDF_BYTES
        or content_types != ["application/pdf"]
        or not (response.body.startswith(b"%PDF-") and response.body.rstrip().endswith(b"%%EOF"))
    ):
        raise MalformedPayloadError("injury document did not return bounded PDF bytes")
    return response.body


@dataclass(frozen=True, slots=True)
class FixtureAvailabilityObservation:
    """Normalized attributed availability, without claim of live source access."""

    role: str
    status: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class FixtureAvailability:
    player_id: str
    event_id: str
    retrieved_at: datetime
    payload_sha256: str
    observations: tuple[FixtureAvailabilityObservation, ...]
    selected: FixtureAvailabilityObservation | None

    @property
    def conflict(self) -> bool:
        return len({observation.status for observation in self.observations}) > 1

    def evidence(self, *, candidate_key: str, kind: EvidenceKind) -> tuple[EvidenceItem, ...]:
        if kind not in (
            EvidenceKind.AVAILABILITY,
            EvidenceKind.TEAMMATE_ABSENCE,
            EvidenceKind.OPPONENT_ABSENCE,
        ):
            raise MalformedPayloadError("invalid availability evidence kind")
        if self.selected is None:
            return ()
        selected = self.selected
        return (
            fixture_evidence(
                candidate_key,
                kind=kind,
                provenance=fixture_provenance(
                    f"nba-availability/{self.event_id}/{self.player_id}",
                    self.retrieved_at,
                    selected.updated_at,
                    self.payload_sha256,
                ),
                excerpt=f"{self.player_id} was listed {selected.status} for {self.event_id}",
                facts={
                    "canonical_player_id": self.player_id,
                    "event_id": self.event_id,
                    "status": selected.status,
                    "simulated_source_role": selected.role,
                    "reported_conflict": self.conflict,
                },
            ),
        )


def resolve_fixture_availability(
    body: bytes,
    *,
    player_id: str,
    event_id: str,
    retrieved_at: datetime,
    max_age: timedelta,
) -> FixtureAvailability:
    """Apply A12 to one pre-resolved player/event and keep all conflicting records."""
    raw = decode_payload(body)
    if not isinstance(raw, list) or not player_id.strip() or not event_id.strip():
        raise MalformedPayloadError("availability requires a scoped fixture array")
    observations = []
    seen: set[tuple[str, datetime]] = set()
    for row in raw:
        if not isinstance(row, dict) or (
            row.get("player_id") != player_id or row.get("event_id") != event_id
        ):
            raise MalformedPayloadError("availability does not match the selected player and event")
        role, status = row.get("role"), row.get("status")
        if (
            not isinstance(role, str)
            or role not in (*_OFFICIAL, _EDITORIAL)
            or not isinstance(status, str)
            or status not in _STATUSES
        ):
            raise MalformedPayloadError("unrecognized availability source role or status")
        updated_at = aware_timestamp(row.get("last_update"))
        require_fresh(updated_at, retrieved_at, max_age)
        if (role, updated_at) in seen:
            raise MalformedPayloadError("duplicate or conflicting availability observation")
        seen.add((role, updated_at))
        observations.append(FixtureAvailabilityObservation(role, status, updated_at))

    # Timestamp wins when official records disagree. For identical statuses at the same
    # timestamp, preserve the Injury Report's authority. A tied contradiction stays open.
    officials = [item for item in observations if item.role in _OFFICIAL]
    newest = max((item.updated_at for item in officials), default=None)
    latest = [item for item in officials if item.updated_at == newest]
    selected = (
        min(latest, key=lambda item: _OFFICIAL.index(item.role))
        if latest and len({item.status for item in latest}) == 1
        else None
    )
    return FixtureAvailability(
        player_id, event_id, retrieved_at, payload_hash(body), tuple(observations), selected
    )


def replay_official_edition(
    body: bytes,
    *,
    reference: str,
    published_at: datetime,
    retrieved_at: datetime,
    max_age: timedelta,
    player_id: str,
    event_id: str,
) -> FixtureAvailability:
    """Bind normalized offline rows to the matching official edition metadata."""
    check_official_edition(reference, published_at, retrieved_at, max_age)
    record = resolve_fixture_availability(
        body,
        player_id=player_id,
        event_id=event_id,
        retrieved_at=retrieved_at,
        max_age=max_age,
    )
    if (
        len(record.observations) != 1
        or record.selected is None
        or (record.selected.role != _OFFICIAL[0] or record.selected.updated_at != published_at)
    ):
        raise MalformedPayloadError("availability row does not match the official report edition")
    return record
