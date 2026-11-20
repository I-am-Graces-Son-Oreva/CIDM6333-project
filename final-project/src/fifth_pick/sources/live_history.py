"""Read receipt-bound history archives without contacting a provider."""

import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from fifth_pick.config import load_configs
from fifth_pick.evidence import EvidenceEffect, EvidenceItem, EvidenceKind, EvidenceSignificance
from fifth_pick.models import Category, Evidence, Provenance
from fifth_pick.receipts import Receipt
from fifth_pick.sources.base import EvidenceMode, LiveAuthorizationError, MalformedPayloadError
from fifth_pick.sources.bdl_history import HistoryRetrieval, verify_history_replay
from fifth_pick.sources.odds_api import validate_event_id
from fifth_pick.sources.player_history import HistoryGameTiming, reconcile_history_timing
from fifth_pick.sources.supporting_fixture import (
    aware_timestamp,
    decode_payload,
    payload_hash,
    require_fresh,
)
from fifth_pick.storage import RunStore, _atomic_write, collection_lock

_SOURCE = "balldontlie-nba-history"
_METHOD = "balldontlie:nba:stats"


def read_live_history_items(
    store: RunStore,
    run_id: str,
    *,
    event_id: str,
    player_id: str,
    candidate_key: str,
    category: Category,
    phase: str,
    as_of: datetime,
    event_teams: tuple[str, str],
) -> tuple[EvidenceItem, ...]:
    """Recheck approved history, including a separately receipted chronology and coverage."""
    if phase not in ("analysis", "t20") or as_of.utcoffset() is None:
        raise MalformedPayloadError("history requires an exact phase and aware clock")
    validate_event_id(event_id)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", player_id):
        raise MalformedPayloadError("history requires a canonical player identifier")
    key = f"live-history-{phase}-{event_id}-{player_id}"
    rows = {
        suffix: [
            row for row in store.read_receipts(run_id) if row["event_key"] == f"{key}-{suffix}"
        ]
        for suffix in ("request", "response", "corroboration")
    }
    if not any(rows.values()):
        return ()
    _require_history_source()
    if any(len(matches) != 1 for matches in rows.values()):
        raise MalformedPayloadError("history receipt chain is incomplete or ambiguous")
    subject = f"{event_id}:{player_id}:{phase}"
    directory = store.run_directory(run_id)

    def archive(suffix, event, result):
        row = rows[suffix][0]
        if (
            row["event"] != event
            or row["result"] != result
            or row["run_id"] != run_id
            or row["subject"] != subject
            or row["source"] != ("fifth-pick" if suffix == "corroboration" else _SOURCE)
        ):
            raise MalformedPayloadError("history receipt is not bound to this source and stage")
        path = directory / f"{key}-{suffix}.json"
        if path.is_symlink():
            raise MalformedPayloadError("history archive path is invalid")
        raw = path.read_bytes()
        if payload_hash(raw) != row["reason"]:
            raise MalformedPayloadError("history archive digest differs from receipt")
        return decode_payload(raw), aware_timestamp(row["timestamp"]), payload_hash(raw)

    try:
        request, requested, request_digest = archive("request", "LIVE_HISTORY_REQUEST", "ATTEMPTED")
        response, retrieved, digest = archive("response", "LIVE_HISTORY_RESPONSE", "HTTP_200")
        corroboration, confirmed, proof_digest = archive(
            "corroboration", "LIVE_HISTORY_CORROBORATION", "VERIFIED"
        )
    except (OSError, TypeError, ValueError, KeyError, AttributeError, OverflowError) as exc:
        raise MalformedPayloadError("history receipt or archive is invalid") from exc
    return _validate_history(
        request,
        response,
        corroboration,
        requested=requested,
        retrieved=retrieved,
        confirmed=confirmed,
        request_digest=request_digest,
        digest=digest,
        proof_digest=proof_digest,
        event_id=event_id,
        player_id=player_id,
        candidate_key=candidate_key,
        category=category,
        phase=phase,
        as_of=as_of,
        event_teams=event_teams,
    )


def _require_history_source() -> None:
    source = next(
        (item for item in load_configs().approved_sources.sources if item.source_id == _SOURCE),
        None,
    )
    if (
        source is None
        or source.access_method != _METHOD
        or source.terms_review_status != "approved"
    ):
        raise LiveAuthorizationError("production player-history access is not approved")


def _validate_history(
    request: object,
    response: object,
    corroboration: object,
    *,
    requested: datetime,
    retrieved: datetime,
    confirmed: datetime,
    request_digest: str,
    digest: str,
    proof_digest: str,
    event_id: str,
    player_id: str,
    candidate_key: str,
    category: Category,
    phase: str,
    as_of: datetime,
    event_teams: tuple[str, str],
) -> tuple[EvidenceItem, ...]:
    try:
        if not all(isinstance(value, dict) for value in (request, response, corroboration)):
            raise ValueError
        assert isinstance(request, dict)
        assert isinstance(response, dict)
        assert isinstance(corroboration, dict)
        if (
            request["player_id"] != player_id
            or request["event_id"] != event_id
            or request["phase"] != phase
            or request["endpoint"] != "https://api.balldontlie.io/v1/stats"
            or request["full_game"] is not True
            or response["request_sha256"] != request_digest
            or corroboration["response_sha256"] != digest
            or corroboration["provider_player_id"] != request["provider_player_id"]
            or corroboration["coverage_complete"] is not True
            or not corroboration["identity_reference"].strip()
            or not corroboration["timing_reference"].strip()
            or {corroboration["canonical_event_opponent"], corroboration["canonical_player_team"]}
            != set(event_teams)
            or len(set(event_teams)) != 2
            or not requested <= retrieved <= confirmed <= as_of
        ):
            raise ValueError
        before = date.fromisoformat(request["before"])
        max_age = timedelta(seconds=request["max_age_seconds"])
        corrected = aware_timestamp(corroboration["corrections_checked_at"])
        require_fresh(corrected, as_of, max_age)
        if not retrieved <= corrected <= confirmed:
            raise ValueError
        payloads = tuple(page["body"].encode("utf-8") for page in response["pages"])
        retrievals = tuple(
            HistoryRetrieval(
                page["cursor"],
                aware_timestamp(page["retrieved_at"]),
                page["sha256"],
            )
            for page in response["pages"]
        )
        if any(not requested <= page.retrieved_at <= retrieved for page in retrievals):
            raise ValueError
        games = verify_history_replay(
            payloads,
            retrievals,
            provider_player_id=request["provider_player_id"],
            season=request["season"],
            before=before,
            as_of=as_of,
            max_age=max_age,
            page_limit=request["page_limit"],
        )
        timings = {}
        for row in corroboration["games"]:
            number = row["game_id"]
            if type(number) is not int or number in timings:
                raise ValueError
            timings[number] = HistoryGameTiming(
                date.fromisoformat(row["game_date"]),
                aware_timestamp(row["played_at"]),
                aware_timestamp(row["completed_at"]),
                row["season"],
                row["opponent_id"],
                row["canonical_opponent"],
            )
        completed = reconcile_history_timing(
            games,
            timings,
            provider_player_id=request["provider_player_id"],
            retrieved_at=retrieved,
        )
        if len(completed) < 8:
            raise MalformedPayloadError("verified history contains fewer than eight appearances")
        head = tuple(
            game
            for game in completed
            if game.opponent == corroboration["canonical_event_opponent"]
            and timings[int(game.game_id)].opponent_id == corroboration["event_opponent_id"]
        )
    except (OSError, TypeError, ValueError, KeyError, AttributeError, OverflowError) as exc:
        raise MalformedPayloadError("history archive has invalid scope or corroboration") from exc
    items = []
    for kind, sample_games in (
        (EvidenceKind.LAST_8, completed[:8]),
        (EvidenceKind.SAME_SEASON_H2H, head),
    ):
        if not sample_games:
            continue
        excerpt = f"{len(sample_games)} completed appearances with corroborated game timing"
        items.append(
            EvidenceItem(
                f"verified-history-{phase}-{kind.value}",
                candidate_key,
                kind,
                Evidence(
                    excerpt,
                    Provenance(_SOURCE, confirmed, corrected, _METHOD, request["endpoint"], digest),
                    excerpt,
                ),
                EvidenceMode.LIVE,
                EvidenceEffect.NEUTRAL,
                EvidenceSignificance.IMPORTANT,
                samples=tuple(game.sample(category) for game in sample_games),
                facts={
                    "canonical_player_id": player_id,
                    "event_id": event_id,
                    "corroboration_sha256": proof_digest,
                },
            )
        )
    return tuple(items)


def issue_live_history(
    store: RunStore,
    run_id: str,
    *,
    event_id: str,
    player_id: str,
    candidate_key: str,
    category: Category,
    phase: str,
    event_teams: tuple[str, str],
    request: dict[str, object],
    pages: tuple[tuple[bytes, HistoryRetrieval], ...],
    corroboration: dict[str, object],
    requested: datetime,
    retrieved: datetime,
    confirmed: datetime,
    controller_confirmed: bool = False,
) -> tuple[EvidenceItem, ...]:
    """Seal a validated captured response and independently supplied corroboration."""
    _require_history_source()
    validate_event_id(event_id)
    if (
        controller_confirmed is not True
        or phase not in ("analysis", "t20")
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", player_id)
        or any(value.utcoffset() is None for value in (requested, retrieved, confirmed))
    ):
        raise LiveAuthorizationError("history issuance requires exact Controller authorization")
    for field in ("identity_reference", "timing_reference"):
        reference = corroboration.get(field)
        if not isinstance(reference, str):
            raise MalformedPayloadError("independent history references are required")
        url = urlsplit(reference)
        if url.scheme != "https" or url.netloc not in ("nba.com", "www.nba.com"):
            raise MalformedPayloadError(
                "history corroboration requires an independent NBA reference"
            )
        if not url.path or url.path.startswith("/stats/") or url.query or url.fragment:
            raise MalformedPayloadError("history corroboration reference is outside official scope")

    def encode(value: object) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

    request_bytes = encode(request)
    response = {
        "request_sha256": payload_hash(request_bytes),
        "pages": [
            {
                "body": body.decode("utf-8"),
                "cursor": page.cursor,
                "retrieved_at": page.retrieved_at.isoformat(),
                "sha256": page.payload_sha256,
            }
            for body, page in pages
        ],
    }
    response_bytes = encode(response)
    proof = dict(corroboration, response_sha256=payload_hash(response_bytes))
    proof_bytes = encode(proof)
    items = _validate_history(
        request,
        response,
        proof,
        requested=requested,
        retrieved=retrieved,
        confirmed=confirmed,
        request_digest=payload_hash(request_bytes),
        digest=payload_hash(response_bytes),
        proof_digest=payload_hash(proof_bytes),
        event_id=event_id,
        player_id=player_id,
        candidate_key=candidate_key,
        category=category,
        phase=phase,
        as_of=confirmed,
        event_teams=event_teams,
    )
    key = f"live-history-{phase}-{event_id}-{player_id}"
    subject = f"{event_id}:{player_id}:{phase}"
    entries = (
        ("request", "LIVE_HISTORY_REQUEST", "ATTEMPTED", _SOURCE, requested, request_bytes),
        ("response", "LIVE_HISTORY_RESPONSE", "HTTP_200", _SOURCE, retrieved, response_bytes),
        (
            "corroboration",
            "LIVE_HISTORY_CORROBORATION",
            "VERIFIED",
            "fifth-pick",
            confirmed,
            proof_bytes,
        ),
    )
    with collection_lock(store, run_id):
        directory = store.run_directory(run_id)
        existing = store.read_receipts(run_id)
        for suffix, *_ in entries:
            path = directory / f"{key}-{suffix}.json"
            if (
                path.exists()
                or path.is_symlink()
                or any(row["event_key"] == f"{key}-{suffix}" for row in existing)
            ):
                raise MalformedPayloadError("history archive already exists; preserve the run")
        for suffix, event, result, source, timestamp, raw in entries:
            _atomic_write(directory / f"{key}-{suffix}.json", raw)
            store.append_receipt(
                Receipt(
                    timestamp.isoformat(),
                    event,
                    result,
                    subject,
                    source,
                    payload_hash(raw),
                    run_id,
                    f"{key}-{suffix}",
                )
            )
    return items
