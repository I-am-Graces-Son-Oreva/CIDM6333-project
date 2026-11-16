import unittest
from datetime import UTC, datetime

from fifth_pick.config import load_configs
from fifth_pick.identity import IdentityResolver
from fifth_pick.models import Category, Direction, Platform, ReasonCode
from fifth_pick.registry import Registry
from fifth_pick.sources.base import (
    BoardProvenance,
    SourceBoard,
    SourceEvent,
    SourceProjection,
)
from fifth_pick.sources.normalize import (
    MARKET_TO_CATEGORY,
    OUTCOME_TO_DIRECTION,
    ResolvedProjection,
    normalize_direction,
    normalize_market,
    resolve_board,
)
from fifth_pick.sources.quota import QuotaSnapshot

NOW = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)


def make_projection(
    *,
    provider_player_name: str = "Jayson Tatum",
    platform: Platform = Platform.PRIZEPICKS,
    category: Category = Category.POINTS,
    projection: float = 27.5,
    direction: Direction = Direction.HIGHER,
    event_id: str = "evt-1",
) -> SourceProjection:
    return SourceProjection(
        platform=platform,
        provider_player_name=provider_player_name,
        category=category,
        projection=projection,
        direction=direction,
        event_id=event_id,
        source_update_time=NOW,
        retrieved_at=NOW,
    )


def make_board(*projections: SourceProjection) -> SourceBoard:
    event_ids = sorted({projection.event_id for projection in projections})
    events = tuple(
        SourceEvent(
            event_id=event_id,
            home_team="Home Team",
            away_team="Away Team",
            commence_time=NOW,
            projections=tuple(
                projection for projection in projections if projection.event_id == event_id
            ),
        )
        for event_id in event_ids
    )
    provenance = BoardProvenance(
        source_id="the-odds-api-us-dfs",
        region="us_dfs",
        bookmakers=("prizepicks", "underdog"),
        markets=tuple(MARKET_TO_CATEGORY),
        request_timestamp=NOW,
        retrieved_at=NOW,
        source_update_time=NOW,
        payload_sha256="0" * 64,
        request_url="https://api.the-odds-api.com/v4/sports/basketball_nba/events",
        quota=QuotaSnapshot(remaining=None, used=None, last=None),
    )
    return SourceBoard(provenance=provenance, events=events)


class MarketMappingTests(unittest.TestCase):
    def test_market_mapping_is_exact(self) -> None:
        self.assertIs(normalize_market("player_points"), Category.POINTS)
        self.assertIs(normalize_market("player_assists"), Category.ASSISTS)
        self.assertIs(normalize_market("player_rebounds"), Category.REBOUNDS)
        self.assertIs(normalize_market("player_points_rebounds_assists"), Category.PRA)
        self.assertIs(normalize_market("player_rebounds_assists"), Category.REBOUNDS_ASSISTS)

    def test_threes_and_alternate_markets_are_rejected(self) -> None:
        for market_key in (
            "player_threes",
            "player_points_rebounds",
            "player_steals",
            "player_turnovers",
            "points",
        ):
            with self.subTest(market_key=market_key):
                self.assertIsNone(normalize_market(market_key))

    def test_three_point_attempts_is_not_a_live_market(self) -> None:
        self.assertNotIn(Category.THREE_POINT_ATTEMPTS, set(MARKET_TO_CATEGORY.values()))

    def test_market_mapping_matches_authoritative_category_map(self) -> None:
        bundle = load_configs()

        self.assertEqual(tuple(MARKET_TO_CATEGORY), tuple(bundle.category_map.mappings))
        self.assertEqual(dict(MARKET_TO_CATEGORY), dict(bundle.category_map.mappings))

    def test_direction_mapping_is_exact(self) -> None:
        self.assertIs(normalize_direction("Over"), Direction.HIGHER)
        self.assertIs(normalize_direction("Under"), Direction.LOWER)
        for outcome_name in ("over", "under", "Push", "Yes", ""):
            with self.subTest(outcome_name=outcome_name):
                self.assertIsNone(normalize_direction(outcome_name))

    def test_outcome_map_covers_both_directions(self) -> None:
        self.assertEqual(set(OUTCOME_TO_DIRECTION.values()), {Direction.HIGHER, Direction.LOWER})


class IdentityResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bundle = load_configs()
        cls.registry = Registry.from_universe(bundle.approved_universe)

    def test_unknown_provider_identity_fails_closed(self) -> None:
        resolver = IdentityResolver(self.registry)
        board = make_board(make_projection(provider_player_name="Ghost Player"))

        resolved = resolve_board(board, resolver)

        self.assertEqual(len(resolved), 1)
        self.assertFalse(resolved[0].resolved)
        self.assertIsNone(resolved[0].player)
        self.assertIs(resolved[0].reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_canonical_name_is_not_a_provider_alias(self) -> None:
        resolver = IdentityResolver(self.registry)
        board = make_board(make_projection(provider_player_name="Jayson Tatum"))

        resolved = resolve_board(board, resolver)

        self.assertFalse(resolved[0].resolved)
        self.assertIs(resolved[0].reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_injected_provider_alias_resolves(self) -> None:
        resolver = IdentityResolver(
            self.registry,
            provider_aliases={"Tatum, Jayson": ("jayson-tatum",)},
        )
        board = make_board(make_projection(provider_player_name="Tatum, Jayson"))

        resolved = resolve_board(board, resolver)

        self.assertTrue(resolved[0].resolved)
        assert resolved[0].player is not None
        self.assertEqual(resolved[0].player.player_id, "jayson-tatum")
        self.assertIsNone(resolved[0].reason)

    def test_ambiguous_provider_alias_fails_closed(self) -> None:
        resolver = IdentityResolver(
            self.registry,
            provider_aliases={"Ambiguous Guard": ("jayson-tatum", "luka-doncic")},
        )
        board = make_board(make_projection(provider_player_name="Ambiguous Guard"))

        resolved = resolve_board(board, resolver)

        self.assertFalse(resolved[0].resolved)
        self.assertIs(resolved[0].reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_platform_observations_remain_separate(self) -> None:
        resolver = IdentityResolver(self.registry)
        board = make_board(
            make_projection(platform=Platform.PRIZEPICKS, projection=27.5),
            make_projection(platform=Platform.UNDERDOG, projection=28.5),
        )

        resolved = resolve_board(board, resolver)

        platforms = [item.projection.platform for item in resolved]
        self.assertEqual(platforms, [Platform.PRIZEPICKS, Platform.UNDERDOG])
        self.assertEqual(
            sorted(item.projection.projection for item in resolved),
            [27.5, 28.5],
        )

    def test_resolved_projection_preserves_projection_fields(self) -> None:
        resolver = IdentityResolver(self.registry)
        projection = make_projection(
            category=Category.PRA,
            projection=41.5,
            direction=Direction.LOWER,
            event_id="evt-9",
        )
        board = make_board(projection)

        resolved = resolve_board(board, resolver)

        self.assertIsInstance(resolved[0], ResolvedProjection)
        self.assertIs(resolved[0].projection, projection)
        self.assertEqual(resolved[0].projection.category, Category.PRA)
        self.assertEqual(resolved[0].projection.direction, Direction.LOWER)
        self.assertEqual(resolved[0].projection.event_id, "evt-9")


if __name__ == "__main__":
    unittest.main()
