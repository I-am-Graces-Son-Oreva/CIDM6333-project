import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from fifth_pick.config import (
    ApprovedUniverseConfig,
    ConfigMetadata,
    UniverseCategory,
    UniverseEntry,
    load_configs,
)
from fifth_pick.errors import ValidationError
from fifth_pick.identity import IdentityResolver
from fifth_pick.models import Category, Direction, ReasonCode
from fifth_pick.receipts import Receipt
from fifth_pick.registry import Registry, RegistryError, canonical_player_id
from fifth_pick.storage import RunStore

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_FIXTURE = REPO_ROOT / "tests/fixtures/registry/provider-aliases.yaml"


def make_metadata() -> ConfigMetadata:
    return ConfigMetadata(
        schema_version=1,
        content_version="v1",
        effective_date="2026-11-15",
        provenance=("Part II 9.1", "2026-11-15"),
    )


def make_entry(
    name: str,
    *,
    categories: tuple[UniverseCategory, ...] = (
        UniverseCategory(category=Category.POINTS, directions=(Direction.HIGHER,)),
    ),
    aliases: tuple[str, ...] = (),
) -> UniverseEntry:
    return UniverseEntry(
        name=name,
        source_entry=f"{name} = test entry",
        categories=categories,
        aliases=aliases,
        foul_trouble=False,
    )


def make_universe(*entries: UniverseEntry) -> ApprovedUniverseConfig:
    return ApprovedUniverseConfig(metadata=make_metadata(), entries=entries)


def load_provider_aliases() -> dict[str, tuple[str, ...]]:
    document = yaml.safe_load(PROVIDER_FIXTURE.read_text(encoding="utf-8"))
    return {item["provider_name"]: tuple(item["candidate_ids"]) for item in document["aliases"]}


class IdentityResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_configs()
        cls.registry = Registry.from_universe(cls.bundle.approved_universe)
        cls.resolver = IdentityResolver(cls.registry)

    def test_canonical_name_resolves_to_stable_local_id(self) -> None:
        resolution = self.resolver.resolve_canonical("Luka Doncic")

        self.assertTrue(resolution.resolved)
        assert resolution.player is not None
        self.assertEqual(resolution.player.player_id, "luka-doncic")
        self.assertEqual(canonical_player_id("Luka Doncic"), "luka-doncic")
        self.assertEqual(len({player.player_id for player in self.registry.players()}), 156)

    def test_only_explicit_luka_diacritic_alias_is_registered(self) -> None:
        resolution = self.resolver.resolve_canonical("Luka Dončić")

        self.assertTrue(resolution.resolved)
        assert resolution.player is not None
        self.assertEqual(resolution.player.player_id, "luka-doncic")
        self.assertEqual(
            {alias for player in self.registry.players() for alias in player.aliases},
            {"Luka Dončić"},
        )

    def test_no_implicit_name_fallback(self) -> None:
        for variant in (
            "luka doncic",
            "LUKA DONCIC",
            "Luka  Doncic",
            " Luka Doncic",
            "Luka Doncic ",
            "Luka Doncic.",
            "Luka Doncıc",
            "Luka Dončić ",
        ):
            with self.subTest(variant=variant):
                resolution = self.resolver.resolve_canonical(variant)
                self.assertFalse(resolution.resolved)
                self.assertIs(resolution.reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_unknown_identity_fails_closed(self) -> None:
        resolution = self.resolver.resolve_canonical("Unknown Player")

        self.assertFalse(resolution.resolved)
        self.assertIsNone(resolution.player)
        self.assertIs(resolution.reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_malik_monk_is_registered_without_grants(self) -> None:
        resolution = self.resolver.resolve_canonical("Malik Monk")

        self.assertTrue(resolution.resolved)
        assert resolution.player is not None
        self.assertEqual(resolution.player.player_id, "malik-monk")
        self.assertEqual(resolution.player.grants, frozenset())
        self.assertEqual(resolution.player.aliases, ())

    def test_duplicate_canonical_identity_fails_closed(self) -> None:
        with self.assertRaises(RegistryError):
            Registry.from_universe(
                make_universe(make_entry("Same Player"), make_entry("Same Player"))
            )

    def test_canonical_id_collision_fails_closed(self) -> None:
        with self.assertRaises(RegistryError):
            Registry.from_universe(
                make_universe(make_entry("Player-One"), make_entry("Player One"))
            )

    def test_alias_collision_fails_closed(self) -> None:
        with self.assertRaises(RegistryError):
            Registry.from_universe(
                make_universe(
                    make_entry("Player One", aliases=("Shared Alias",)),
                    make_entry("Player Two", aliases=("Shared Alias",)),
                )
            )

    def test_alias_cannot_shadow_another_canonical_name(self) -> None:
        with self.assertRaises(RegistryError):
            Registry.from_universe(
                make_universe(
                    make_entry("Player One", aliases=("Player Two",)),
                    make_entry("Player Two"),
                )
            )


class ProviderIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bundle = load_configs()
        cls.registry = Registry.from_universe(bundle.approved_universe)
        cls.resolver = IdentityResolver(
            cls.registry,
            provider_aliases=load_provider_aliases(),
        )

    def test_explicit_provider_alias_resolves(self) -> None:
        resolution = self.resolver.resolve_provider("L. Doncic")

        self.assertTrue(resolution.resolved)
        assert resolution.player is not None
        self.assertEqual(resolution.player.player_id, "luka-doncic")

    def test_ambiguous_provider_name_is_unresolved(self) -> None:
        resolution = self.resolver.resolve_provider("Ambiguous Guard")

        self.assertFalse(resolution.resolved)
        self.assertIs(resolution.reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_name_only_match_is_insufficient(self) -> None:
        resolution = self.resolver.resolve_provider("Jayson Tatum")

        self.assertFalse(resolution.resolved)
        self.assertIs(resolution.reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_unknown_provider_alias_fails_closed(self) -> None:
        resolution = self.resolver.resolve_provider("Ghost Player")

        self.assertFalse(resolution.resolved)
        self.assertIs(resolution.reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_canonical_lookup_does_not_use_provider_aliases(self) -> None:
        resolution = self.resolver.resolve_canonical("L. Doncic")

        self.assertFalse(resolution.resolved)
        self.assertIs(resolution.reason, ReasonCode.PLAYER_IDENTITY_UNRESOLVED)

    def test_provider_alias_to_unknown_id_fails_closed(self) -> None:
        with self.assertRaises(ValidationError):
            IdentityResolver(
                self.registry,
                provider_aliases={"Mislabeled Star": ("not-a-player",)},
            )

    def test_identity_denial_is_recorded_in_receipts(self) -> None:
        resolution = self.resolver.resolve_canonical("Unknown Player")
        assert resolution.reason is not None

        with TemporaryDirectory() as temporary_root:
            store = RunStore(temporary_root)
            receipt = Receipt(
                timestamp="2026-11-15T17:00:00+00:00",
                event="IDENTITY_RESOLUTION",
                result="DENIED",
                subject=resolution.input_name,
                source="identity-resolver",
                reason=resolution.reason.value,
                run_id="run-identity",
                event_key="identity-unknown-1",
            )

            store.append_receipt(receipt)
            stored = store.read_receipts("run-identity")

        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["result"], "DENIED")
        self.assertEqual(stored[0]["reason"], "PLAYER_IDENTITY_UNRESOLVED")
