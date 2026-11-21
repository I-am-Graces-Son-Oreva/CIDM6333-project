"""Replay supplied DunkAPI archives offline. No source or LIVE admission is implied."""

from dataclasses import asdict
from datetime import date
from urllib.parse import urlsplit

from fifth_pick.registry import Registry
from fifth_pick.sources.base import MalformedPayloadError
from fifth_pick.sources.dunkapi_history import (
    HistoryScope,
    Participation,
    decode_history,
    decode_identity,
)
from fifth_pick.sources.history_reconciliation import GameCorroboration, reconcile_game
from fifth_pick.sources.player_history import CompletedPlayerGame
from fifth_pick.sources.supporting_fixture import aware_timestamp, decode_payload, payload_hash


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedPayloadError("history corroboration requires an object")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise MalformedPayloadError("history corroboration requires nonempty text")
    return value


def _reference(value: object) -> str:
    reference = _text(value)
    parsed = urlsplit(reference)
    if parsed.scheme == "synthetic" and parsed.path and not parsed.netloc:
        return reference
    host = (parsed.hostname or "").rstrip(".")
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or host == "dunkapi.com"
        or host.endswith(".dunkapi.com")
    ):
        raise MalformedPayloadError("history requires an independent corroboration reference")
    return reference


def _game(value: object) -> GameCorroboration:
    proof = _object(value)
    raw_date = _text(proof.get("game_date"))
    game_date = date.fromisoformat(raw_date)
    if game_date.isoformat() != raw_date:
        raise MalformedPayloadError("invalid corroborated game date")
    return GameCorroboration(
        game_id=_text(proof.get("game_id")),
        game_date=game_date,
        season=_text(proof.get("season")),
        canonical_player_id=_text(proof.get("canonical_player_id")),
        home_team=_text(proof.get("home_team")),
        away_team=_text(proof.get("away_team")),
        player_team=_text(proof.get("player_team")),
        provider_opponent=_text(proof.get("provider_opponent")),
        played_at=aware_timestamp(proof.get("actual_played_at")),
        completed_at=aware_timestamp(proof.get("actual_completed_at")),
        game_timezone=_text(proof.get("game_timezone")),
        reference=_reference(proof.get("reference")),
    )


def replay_dunkapi_history(
    identity_body: bytes,
    pages: tuple[tuple[int, bytes], ...],
    corroboration_body: bytes,
    *,
    expected_corroboration_sha256: str,
    scope: HistoryScope,
    registry: Registry,
    canonical_player_id: str,
    event_id: str,
    event_teams: tuple[str, str],
) -> tuple[CompletedPlayerGame, ...]:
    """Replay a pinned manifest and complete page chain with independently supplied facts.

    The caller supplies the trusted manifest digest out of band. Its retrieved_at is the
    earliest archived page retrieval when there are multiple pages. References describe
    external corroboration. Hashes bind bytes but do not authenticate those references
    or establish coverage, correction freshness, or Controller approval.
    """
    _text(event_id)
    if (
        registry.player_by_id(canonical_player_id) is None
        or len(event_teams) != 2
        or len({_text(team) for team in event_teams}) != 2
        or payload_hash(corroboration_body) != expected_corroboration_sha256
    ):
        raise MalformedPayloadError("history corroboration digest or replay scope is invalid")

    try:
        proof = _object(decode_payload(corroboration_body))
        request = asdict(scope) | {
            "first_date": scope.first_date.isoformat(),
            "last_date": scope.last_date.isoformat(),
        }
        if (
            proof.get("provider") != "dunkapi"
            or proof.get("request") != request
            or proof.get("event_id") != event_id
            or proof.get("event_teams") != list(event_teams)
            or proof.get("identity_sha256") != payload_hash(identity_body)
            or proof.get("pages")
            != [{"offset": offset, "sha256": payload_hash(body)} for offset, body in pages]
        ):
            raise MalformedPayloadError(
                "history archive does not match its pinned request or bytes"
            )

        retrieved_at = aware_timestamp(proof.get("retrieved_at"))
        binding = _object(proof.get("identity"))
        team = _text(binding.get("canonical_team"))
        labels = binding.get("provider_team_labels")
        if (
            binding.get("canonical_player_id") != canonical_player_id
            or binding.get("provider_player_id") != scope.player_id
            or team not in event_teams
            or not isinstance(labels, list)
        ):
            raise MalformedPayloadError("history identity contradicts player or event scope")
        _reference(binding.get("reference"))
        decode_identity(
            identity_body,
            player_id=scope.player_id,
            name=_text(binding.get("provider_name")),
            team_labels=tuple(_text(label) for label in labels),
        )

        history = decode_history(pages, scope)
        raw_games = proof.get("games")
        if not isinstance(raw_games, list) or len(raw_games) != len(history.games):
            raise MalformedPayloadError("history timing does not cover the exact archive")
        timings = {}
        for raw in raw_games:
            timing = _game(raw)
            if timing.game_id in timings:
                raise MalformedPayloadError("duplicate history corroboration game")
            timings[timing.game_id] = timing
        if timings.keys() != {row.game_id for row in history.games}:
            raise MalformedPayloadError("history game IDs do not match the timing archive")
        if len({timing.played_at for timing in timings.values()}) != len(timings):
            raise MalformedPayloadError("history has ambiguous simultaneous game starts")

        games = []
        for row in history.games:
            if row.participation is Participation.UNKNOWN:
                raise MalformedPayloadError("history participation remains unresolved")
            game = reconcile_game(
                timings[row.game_id],
                game_id=row.game_id,
                game_date=row.game_date,
                season=row.season,
                canonical_player_id=canonical_player_id,
                provider_opponent=row.opponent,
                home=row.home,
                stats=row.stats,
                retrieved_at=retrieved_at,
                provider_completed_at=row.metadata.completed_at,
            )
            if game is not None:
                games.append(game)
    except (ValueError, RecursionError) as exc:
        raise MalformedPayloadError("invalid history corroboration archive") from exc
    return tuple(sorted(games, key=lambda game: game.played_at, reverse=True))
