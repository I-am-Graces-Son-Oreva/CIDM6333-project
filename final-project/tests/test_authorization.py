import operator
import unittest
from tempfile import TemporaryDirectory
from typing import Any

from fifth_pick.authorization import (
    AuthorizationGate,
    DuplicatePlayerError,
    validate_one_player_one_slot,
)
from fifth_pick.config import CategoryMapConfig, load_configs
from fifth_pick.models import LIVE_MVP_CATEGORIES, Category, Direction, ReasonCode
from fifth_pick.receipts import Receipt
from fifth_pick.registry import AuthorizationGrant, Registry, RegistryPlayer
from fifth_pick.storage import RunStore


class AuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_configs()
        cls.registry = Registry.from_universe(cls.bundle.approved_universe)
        cls.gate = AuthorizationGate()

    def legacy_gate_kwargs(self, **overrides: object) -> dict[str, object]:
        return {
            "registry": self.registry,
            "category_map": self.bundle.category_map,
            "universe_version": "v1",
            "universe_effective_date": "2026-11-15",
            **overrides,
        }

    def custom_registry_with_extra_player(self) -> Registry:
        extra = RegistryPlayer(
            player_id="outside-universe-player",
            canonical_name="Outside Universe Player",
            grants=frozenset(
                {
                    AuthorizationGrant(Category.POINTS, Direction.HIGHER),
                    AuthorizationGrant(Category.THREE_POINT_ATTEMPTS, Direction.HIGHER),
                }
            ),
        )
        return Registry((*self.registry.players(), extra))

    def player_id(self, name: str) -> str:
        player = self.registry.player_by_canonical_name(name)
        assert player is not None
        return player.player_id

    def test_every_live_universe_grant_is_authorized_exactly(self) -> None:
        for player in self.registry.players():
            for grant in player.grants:
                with self.subTest(player=player.canonical_name, grant=grant):
                    decision = self.gate.authorize(
                        player.player_id,
                        grant.category,
                        grant.direction,
                    )
                    if grant.category is Category.THREE_POINT_ATTEMPTS:
                        self.assertFalse(decision.allowed)
                        self.assertIs(decision.reason, ReasonCode.CATEGORY_NOT_AUTHORIZED)
                    else:
                        self.assertTrue(decision.allowed)
                        self.assertIsNone(decision.reason)

    def test_unauthorized_direction_is_denied(self) -> None:
        lower_only = self.player_id("Mitchell Robinson")

        denied = self.gate.authorize(lower_only, Category.POINTS, Direction.HIGHER)
        allowed = self.gate.authorize(lower_only, Category.POINTS, Direction.LOWER)

        self.assertFalse(denied.allowed)
        self.assertIs(denied.reason, ReasonCode.CATEGORY_NOT_AUTHORIZED)
        self.assertTrue(allowed.allowed)

    def test_unauthorized_category_is_denied(self) -> None:
        decision = self.gate.authorize(
            self.player_id("Derrick White"),
            Category.PRA,
            Direction.HIGHER,
        )

        self.assertFalse(decision.allowed)
        self.assertIs(decision.reason, ReasonCode.CATEGORY_NOT_AUTHORIZED)

    def test_trust_tier_does_not_authorize(self) -> None:
        cases = (
            ("Paolo Banchero", Category.PRA),
            ("Bam Adebayo", Category.PRA),
            ("Cade Cunningham", Category.ASSISTS),
        )

        for name, category in cases:
            with self.subTest(player=name, category=category):
                decision = self.gate.authorize(
                    self.player_id(name),
                    category,
                    Direction.HIGHER,
                )
                self.assertFalse(decision.allowed)
                self.assertIs(decision.reason, ReasonCode.CATEGORY_NOT_AUTHORIZED)

    def test_malik_monk_is_registered_but_denied(self) -> None:
        malik = self.registry.player_by_canonical_name("Malik Monk")
        assert malik is not None

        decision = self.gate.authorize(malik.player_id, Category.POINTS, Direction.HIGHER)

        self.assertEqual(malik.grants, frozenset())
        self.assertFalse(decision.allowed)
        self.assertIs(decision.reason, ReasonCode.CATEGORY_NOT_AUTHORIZED)

    def test_three_point_attempts_is_outside_live_mvp(self) -> None:
        for name in ("Naz Reid", "Grayson Allen"):
            with self.subTest(player=name):
                player = self.registry.player_by_canonical_name(name)
                assert player is not None
                self.assertTrue(
                    any(grant.category is Category.THREE_POINT_ATTEMPTS for grant in player.grants)
                )

                decision = self.gate.authorize(
                    player.player_id,
                    Category.THREE_POINT_ATTEMPTS,
                    Direction.HIGHER,
                )
                self.assertFalse(decision.allowed)
                self.assertIs(decision.reason, ReasonCode.CATEGORY_NOT_AUTHORIZED)

        self.assertIsNone(self.gate.map_category("player_threes"))
        self.assertIsNone(self.gate.map_category("player_three_point_attempts"))
        self.assertIsNone(self.gate.map_category("player_threes_made"))

    def test_outside_universe_candidate_is_denied(self) -> None:
        decision = self.gate.authorize("outside-universe-player", Category.POINTS, Direction.HIGHER)

        self.assertFalse(decision.allowed)
        self.assertIs(decision.reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)
        self.assertIsNone(decision.player_id)

    def test_authorization_records_universe_provenance(self) -> None:
        decision = self.gate.authorize(
            self.player_id("Luka Doncic"),
            Category.POINTS,
            Direction.HIGHER,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.universe_version, "v1")
        self.assertEqual(decision.universe_effective_date, "2026-11-15")

    def test_gate_rejects_caller_supplied_registry(self) -> None:
        custom_registry = self.custom_registry_with_extra_player()
        self.assertIsNotNone(custom_registry.player_by_id("outside-universe-player"))

        with self.assertRaises(TypeError):
            AuthorizationGate(**self.legacy_gate_kwargs(registry=custom_registry))

        self.assertFalse(
            self.gate.authorize(
                "outside-universe-player",
                Category.POINTS,
                Direction.HIGHER,
            ).allowed
        )

    def test_gate_rejects_caller_supplied_category_map(self) -> None:
        custom_category_map = CategoryMapConfig(
            metadata=self.bundle.category_map.metadata,
            mappings={
                **self.bundle.category_map.mappings,
                "player_threes": Category.THREE_POINT_ATTEMPTS,
            },
        )

        with self.assertRaises(TypeError):
            AuthorizationGate(**self.legacy_gate_kwargs(category_map=custom_category_map))

    def test_gate_rejects_caller_supplied_live_categories(self) -> None:
        widened_categories = frozenset({*LIVE_MVP_CATEGORIES, Category.THREE_POINT_ATTEMPTS})

        with self.assertRaises(TypeError):
            AuthorizationGate(**self.legacy_gate_kwargs(live_categories=widened_categories))

    def test_gate_rejects_caller_supplied_universe_metadata(self) -> None:
        with self.assertRaises(TypeError):
            AuthorizationGate(
                **self.legacy_gate_kwargs(
                    universe_version="v999",
                    universe_effective_date="2099-01-01",
                )
            )

    def test_gate_state_is_immutable_after_construction(self) -> None:
        gate = AuthorizationGate()
        replaced_registry = self.custom_registry_with_extra_player()
        widened_categories = frozenset({*LIVE_MVP_CATEGORIES, Category.THREE_POINT_ATTEMPTS})

        for attribute, value in (
            ("_registry", replaced_registry),
            ("_category_map", self.bundle.category_map),
            ("_live_categories", widened_categories),
            ("_universe_version", "v999"),
            ("_universe_effective_date", "2099-01-01"),
        ):
            with self.subTest(attribute=attribute), self.assertRaises(AttributeError):
                setattr(gate, attribute, value)

        self.assertFalse(
            gate.authorize("outside-universe-player", Category.POINTS, Direction.HIGHER).allowed
        )
        self.assertFalse(
            gate.authorize(
                self.player_id("Naz Reid"),
                Category.THREE_POINT_ATTEMPTS,
                Direction.HIGHER,
            ).allowed
        )

    def test_registry_indexes_are_immutable(self) -> None:
        gate = AuthorizationGate()
        registry = gate._registry
        injected = RegistryPlayer(
            player_id="outside-universe-player",
            canonical_name="Outside Universe Player",
            grants=frozenset({AuthorizationGrant(Category.POINTS, Direction.HIGHER)}),
        )
        injections = {
            "_by_id": injected.player_id,
            "_by_name": injected.canonical_name,
            "_by_alias": "Outside Alias",
        }

        for attribute, key in injections.items():
            with self.subTest(attribute=attribute):
                index = getattr(registry, attribute)
                with self.assertRaises(TypeError):
                    operator.setitem(index, key, injected)
                with self.assertRaises(AttributeError):
                    setattr(registry, attribute, {key: injected})

        self.assertIsNone(registry.player_by_id(injected.player_id))
        self.assertIsNone(registry.player_by_canonical_name(injected.canonical_name))
        self.assertIsNone(registry.player_by_alias("Outside Alias"))
        self.assertFalse(
            gate.authorize(injected.player_id, Category.POINTS, Direction.HIGHER).allowed
        )

    def test_gate_category_map_is_immutable(self) -> None:
        gate = AuthorizationGate()
        mappings: Any = gate._category_map.mappings

        with self.assertRaises(TypeError):
            operator.setitem(mappings, "player_threes", Category.THREE_POINT_ATTEMPTS)

        self.assertIsNone(gate.map_category("player_threes"))

    def test_one_player_one_slot_constraint(self) -> None:
        luka = self.player_id("Luka Doncic")
        jayson = self.player_id("Jayson Tatum")

        self.assertEqual(validate_one_player_one_slot(()), ())
        self.assertEqual(validate_one_player_one_slot((luka,)), (luka,))
        self.assertEqual(validate_one_player_one_slot((luka, jayson)), (luka, jayson))
        with self.assertRaises(DuplicatePlayerError):
            validate_one_player_one_slot((luka, jayson, luka))

    def test_allow_and_deny_receipts_use_existing_reason_codes(self) -> None:
        allowed = self.gate.authorize(
            self.player_id("Luka Doncic"),
            Category.POINTS,
            Direction.HIGHER,
        )
        denied = self.gate.authorize(
            self.player_id("Derrick White"),
            Category.PRA,
            Direction.HIGHER,
        )
        unresolved = self.gate.authorize(
            "outside-universe-player",
            Category.POINTS,
            Direction.HIGHER,
        )

        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            store.append_receipt(
                Receipt(
                    timestamp="2026-11-15T17:00:00+00:00",
                    event="AUTHORIZATION_CHECK",
                    result="ALLOWED" if allowed.allowed else "DENIED",
                    subject="luka-doncic:POINTS:HIGHER",
                    source="authorization-gate",
                    reason=allowed.reason.value if allowed.reason is not None else None,
                    run_id="run-authorization",
                    event_key="authorization-allow-1",
                )
            )
            store.append_receipt(
                Receipt(
                    timestamp="2026-11-15T17:01:00+00:00",
                    event="AUTHORIZATION_CHECK",
                    result="ALLOWED" if denied.allowed else "DENIED",
                    subject="derrick-white:PRA:HIGHER",
                    source="authorization-gate",
                    reason=denied.reason.value if denied.reason is not None else None,
                    run_id="run-authorization",
                    event_key="authorization-deny-1",
                )
            )
            store.append_receipt(
                Receipt(
                    timestamp="2026-11-15T17:02:00+00:00",
                    event="AUTHORIZATION_CHECK",
                    result="DENIED",
                    subject="outside-universe-player:POINTS:HIGHER",
                    source="authorization-gate",
                    reason=unresolved.reason.value if unresolved.reason is not None else None,
                    run_id="run-authorization",
                    event_key="authorization-deny-2",
                )
            )

            stored = store.read_receipts("run-authorization")

        self.assertEqual([receipt["result"] for receipt in stored], ["ALLOWED", "DENIED", "DENIED"])
        self.assertIsNone(stored[0]["reason"])
        self.assertEqual(stored[1]["reason"], "CATEGORY_NOT_AUTHORIZED")
        self.assertEqual(stored[2]["reason"], "PLAYER_IDENTITY_UNRESOLVED")

    def test_category_map_rejects_unapproved_markets(self) -> None:
        self.assertIs(self.gate.map_category("player_points"), Category.POINTS)
        self.assertIs(self.gate.map_category("player_assists"), Category.ASSISTS)
        self.assertIs(self.gate.map_category("player_rebounds"), Category.REBOUNDS)
        self.assertIs(
            self.gate.map_category("player_points_rebounds_assists"),
            Category.PRA,
        )
        self.assertIs(
            self.gate.map_category("player_rebounds_assists"),
            Category.REBOUNDS_ASSISTS,
        )
        self.assertIsNone(self.gate.map_category("player_blocks"))
