"""Verify and replay a pinned, single-game offline DunkAPI evidence package.

A manifest binds the Stage 2 corroboration bytes, ordered page retrieval records,
and separate coverage and correction archives. Every version has its own digest.
The caller supplies a trusted manifest digest and the replay clock. Structural
validation cannot authenticate external references or authorize LIVE use.
"""

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Literal
from urllib.parse import urlsplit

from fifth_pick.registry import Registry
from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.dunkapi_history import HistoryScope
from fifth_pick.sources.dunkapi_replay import replay_dunkapi_history
from fifth_pick.sources.player_history import CompletedPlayerGame
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    payload_hash,
    require_fresh,
)

Provenance = Literal["synthetic", "external-unverified"]


@dataclass(frozen=True, slots=True)
class EvidencePackageReplay:
    game: CompletedPlayerGame
    provenance: Provenance
    manifest_sha256: str
    version: int
    previous_sha256: str | None


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedPayloadError("expected an evidence-package object")
    return value


def _reference(value: object, provenance: Provenance) -> str:
    if not isinstance(value, str) or not value.isprintable():
        raise MalformedPayloadError("invalid archived source reference")
    ref = urlsplit(value)
    if provenance == "synthetic":
        valid = ref.scheme == "synthetic" and bool(ref.path) and not ref.netloc
    else:
        valid = ref.scheme == "https" and bool(ref.hostname) and ref.username is None
    if not valid or ref.query or ref.fragment:
        raise MalformedPayloadError("archived source reference contradicts package provenance")
    return value


def _artifact(
    body: bytes,
    binding: object,
    kind: str,
    subject: dict[str, object],
    provenance: Provenance,
) -> tuple[dict[str, object], str]:
    artifact = _object(decode_payload(body))
    reference = _reference(artifact.get("reference"), provenance)
    if (
        binding != {"reference": reference, "sha256": payload_hash(body)}
        or artifact.get("kind") != kind
        or artifact.get("subject") != subject
    ):
        raise MalformedPayloadError("evidence artifact does not match its manifest binding")
    return artifact, reference


def _version(
    manifest: dict[str, object], sealed_at: datetime, previous: bytes | None
) -> tuple[int, str | None, datetime | None]:
    version, predecessor = manifest.get("version"), manifest.get("previous_sha256")
    if type(version) is not int or version < 1 or "previous_sha256" not in manifest:
        raise MalformedPayloadError("invalid evidence-package version")
    if version == 1 and predecessor is None and previous is None:
        return version, None, None
    if version <= 1 or not isinstance(predecessor, str) or previous is None:
        raise MalformedPayloadError("a new evidence version requires its prior manifest")
    if payload_hash(previous) != predecessor:
        raise MalformedPayloadError("evidence predecessor digest differs from manifest")
    prior = _object(decode_payload(previous))
    prior_version = prior.get("version")
    prior_sealed_at = aware_timestamp(prior.get("sealed_at"))
    if (
        type(prior_version) is not int
        or prior_version != version - 1
        or prior.get("subject") != manifest.get("subject")
        or prior.get("provenance") != manifest.get("provenance")
        or prior_sealed_at >= sealed_at
    ):
        raise MalformedPayloadError(
            "evidence predecessor scope, version, or time contradicts manifest"
        )
    return version, predecessor, prior_sealed_at


def _page_times(
    records: object, pages: tuple[tuple[int, bytes], ...], earliest: datetime
) -> tuple[datetime, ...]:
    if not isinstance(records, list) or not pages or len(records) != len(pages):
        raise MalformedPayloadError("evidence package does not cover the exact page chain")
    times: list[datetime] = []
    for raw, (offset, body) in zip(records, pages, strict=True):
        item = _object(raw)
        if (
            type(item.get("offset")) is not int
            or item["offset"] != offset
            or item.get("sha256") != payload_hash(body)
        ):
            raise MalformedPayloadError("page archive does not match its evidence binding")
        times.append(aware_timestamp(item.get("retrieved_at")))
    if times[0] != earliest or any(left >= right for left, right in pairwise(times)):
        raise MalformedPayloadError("page retrieval times contradict archived chronology")
    return tuple(times)


def replay_evidence_package(
    manifest_body: bytes,
    *,
    identity_body: bytes,
    pages: tuple[tuple[int, bytes], ...],
    corroboration_body: bytes,
    coverage_body: bytes,
    correction_body: bytes,
    expected_manifest_sha256: str,
    previous_manifest_body: bytes | None = None,
    scope: HistoryScope,
    registry: Registry,
    canonical_player_id: str,
    event_id: str,
    event_teams: tuple[str, str],
    game_id: str,
    as_of: datetime,
    coverage_max_age: timedelta,
    correction_max_age: timedelta,
) -> EvidencePackageReplay:
    """Check structure and content of the supplied archives and emit one played game."""
    digest = payload_hash(manifest_body)
    if digest != expected_manifest_sha256:
        raise MalformedPayloadError(
            "evidence package manifest digest differs from its pinned value"
        )
    try:
        manifest = _object(decode_payload(manifest_body))
        label = manifest.get("provenance")
        if label not in ("synthetic", "external-unverified"):
            raise MalformedPayloadError("evidence package requires explicit unverified provenance")
        provenance: Provenance = "synthetic" if label == "synthetic" else "external-unverified"
        subject: dict[str, object] = {
            "event_id": event_id,
            "event_teams": list(event_teams),
            "canonical_player_id": canonical_player_id,
            "game_id": game_id,
            "request": asdict(scope)
            | {
                "first_date": scope.first_date.isoformat(),
                "last_date": scope.last_date.isoformat(),
            },
        }
        if manifest.get("subject") != subject or manifest.get(
            "corroboration_sha256"
        ) != payload_hash(corroboration_body):
            raise MalformedPayloadError("evidence package scope or corroboration digest differs")
        sealed_at = aware_timestamp(manifest.get("sealed_at"))
        version, previous, prior_seal = _version(manifest, sealed_at, previous_manifest_body)
        proof = _object(decode_payload(corroboration_body))
        timing = proof.get("games")
        if not isinstance(timing, list) or len(timing) != 1:
            raise MalformedPayloadError("the offline package requires one exact game timing record")
        timing_reference = _reference(_object(timing[0]).get("reference"), provenance)
        identity_reference = _reference(_object(proof.get("identity")).get("reference"), provenance)
        times = _page_times(
            manifest.get("pages"), pages, aware_timestamp(proof.get("retrieved_at"))
        )
        coverage, coverage_ref = _artifact(
            coverage_body, manifest.get("coverage"), "history-coverage", subject, provenance
        )
        correction, correction_ref = _artifact(
            correction_body,
            manifest.get("correction"),
            "history-correction-check",
            subject,
            provenance,
        )
        if (
            coverage.get("complete") is not True
            or coverage.get("game_ids") != [game_id]
            or len({coverage_ref, correction_ref, timing_reference, identity_reference}) != 4
        ):
            raise MalformedPayloadError(
                "coverage or independent evidence references are incomplete"
            )
        for record, max_age in ((coverage, coverage_max_age), (correction, correction_max_age)):
            observed = aware_timestamp(record.get("observed_at"))
            require_fresh(observed, as_of, max_age)
            if not times[-1] <= observed <= sealed_at <= as_of:
                raise MalformedPayloadError("evidence observation falls outside package chronology")
        if prior_seal is not None and aware_timestamp(correction.get("observed_at")) <= prior_seal:
            raise MalformedPayloadError("a replacement archive requires a new correction check")

        games = replay_dunkapi_history(
            identity_body,
            pages,
            corroboration_body,
            expected_corroboration_sha256=payload_hash(corroboration_body),
            scope=scope,
            registry=registry,
            canonical_player_id=canonical_player_id,
            event_id=event_id,
            event_teams=event_teams,
        )
        if len(games) != 1 or games[0].game_id != game_id:
            raise MalformedPayloadError("replayed history does not match the one-game package")
        game = games[0]
        stats = _object(correction.get("stats"))
        minutes = stats.get("minutes")
        if (
            any(type(stats.get(field)) is not int for field in ("points", "rebounds", "assists"))
            or not isinstance(minutes, int | float)
            or isinstance(minutes, bool)
            or not math.isfinite(minutes)
            or stats
            != {
                "points": game.points,
                "rebounds": game.rebounds,
                "assists": game.assists,
                "minutes": game.minutes,
            }
        ):
            raise MalformedPayloadError("correction check disagrees with archived game statistics")
    except (ValueError, OverflowError, RecursionError) as exc:
        raise MalformedPayloadError("malformed offline evidence-package archive") from exc
    return EvidencePackageReplay(game, provenance, digest, version, previous)
