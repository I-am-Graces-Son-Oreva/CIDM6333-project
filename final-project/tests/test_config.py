import operator
import re
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fifth_pick.config import (
    CONFIG_FILENAMES,
    DEFAULT_CONFIG_DIR,
    CategoryMapConfig,
    ConfigError,
    load_configs,
)
from fifth_pick.models import Category, Direction

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "docs/superpowers/specs/2026-11-13-fifth-pick-design.md"


def read_frozen_spec() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def first_fenced_block_after(text: str, heading: str) -> str:
    start = text.index(heading)
    match = re.search(r"```text\n(.*?)\n```", text[start:], re.DOTALL)
    if match is None:
        raise AssertionError(f"no text block after {heading!r}")
    return match.group(1)


def parse_universe_entries(text: str) -> dict[str, str]:
    block = first_fenced_block_after(text, "### Part II 9.1 — Explicit Universe")
    entries: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        name, separator, _rest = line.partition(" = ")
        if not separator:
            raise AssertionError(f"unparsable universe entry: {line!r}")
        entries[name] = line
    return entries


def parse_trust_list(text: str, heading: str) -> tuple[str, ...]:
    block = first_fenced_block_after(text, heading)
    return tuple(line.strip() for line in block.splitlines() if line.strip())


CATEGORY_TOKENS = (
    ("rebounds+assists", Category.REBOUNDS_ASSISTS),
    ("3-point attempts", Category.THREE_POINT_ATTEMPTS),
    ("points", Category.POINTS),
    ("assists", Category.ASSISTS),
    ("rebounds", Category.REBOUNDS),
    ("pra", Category.PRA),
)


def parse_segment_directions(segment: str) -> tuple[Direction, ...] | None:
    lowered = segment.lower()
    if "higher/lower" in lowered:
        return (Direction.HIGHER, Direction.LOWER)
    if "lower" in lowered:
        return (Direction.LOWER,)
    if "higher" in lowered:
        return (Direction.HIGHER,)
    return None


def expected_categories(source_entry: str) -> tuple[tuple[Category, tuple[Direction, ...]], ...]:
    after_equals = source_entry.partition(" = ")[2]
    parsed: list[tuple[Category, tuple[Direction, ...] | None]] = []

    for raw_segment in after_equals.split(" / "):
        segment = raw_segment.strip()
        if not segment or segment.lower() == "foul trouble":
            continue

        lowered = segment.lower()
        category = next(
            (category for token, category in CATEGORY_TOKENS if token in lowered),
            None,
        )
        if category is None:
            raise AssertionError(f"unparsable category segment: {segment!r}")

        parsed.append((category, parse_segment_directions(segment)))

    general = next((directions for _category, directions in parsed if directions is not None), None)
    if general is None:
        general = (Direction.HIGHER, Direction.LOWER)

    result: list[tuple[Category, tuple[Direction, ...]]] = []
    for category, directions in parsed:
        result.append((category, directions if directions is not None else general))
    return tuple(result)


def copy_config_dir(destination: Path) -> Path:
    copied = destination / "fifth-pick"
    shutil.copytree(DEFAULT_CONFIG_DIR, copied)
    return copied


class ConfigLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_configs()
        cls.spec = read_frozen_spec()

    def test_all_six_configs_load_with_schema_version_one(self) -> None:
        configs = {
            "approved-universe": self.bundle.approved_universe.metadata,
            "trust-tiers": self.bundle.trust_tiers.metadata,
            "methodology": self.bundle.methodology.metadata,
            "governance": self.bundle.governance.metadata,
            "category-map": self.bundle.category_map.metadata,
            "approved-sources": self.bundle.approved_sources.metadata,
        }

        self.assertEqual(tuple(configs), CONFIG_FILENAMES)
        for name, metadata in configs.items():
            with self.subTest(config=name):
                self.assertEqual(metadata.schema_version, 1)
                self.assertTrue(metadata.provenance)

    def test_approved_universe_preserves_owner_metadata_and_provenance(self) -> None:
        metadata = self.bundle.approved_universe.metadata

        self.assertEqual(metadata.content_version, "v1")
        self.assertEqual(metadata.effective_date, "2026-11-15")
        provenance = "\n".join(metadata.provenance)
        self.assertIn("Part II 9.1", provenance)
        self.assertIn("2026-11-15", provenance)

    def test_non_universe_configs_have_null_owner_metadata_without_inference(self) -> None:
        for name, metadata in {
            "trust-tiers": self.bundle.trust_tiers.metadata,
            "methodology": self.bundle.methodology.metadata,
            "governance": self.bundle.governance.metadata,
            "category-map": self.bundle.category_map.metadata,
            "approved-sources": self.bundle.approved_sources.metadata,
        }.items():
            with self.subTest(config=name):
                self.assertIsNone(metadata.content_version)
                self.assertIsNone(metadata.effective_date)

    def test_missing_required_config_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_dir = copy_config_dir(Path(temporary_directory))
            (config_dir / "category-map.yaml").unlink()

            with self.assertRaises(ConfigError):
                load_configs(config_dir)

    def test_missing_owner_metadata_on_universe_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_dir = copy_config_dir(Path(temporary_directory))
            universe_path = config_dir / "approved-universe.yaml"
            universe_path.write_text(
                universe_path.read_text(encoding="utf-8").replace(
                    'content_version: "v1"',
                    "content_version: null",
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_configs(config_dir)

    def test_inferred_owner_metadata_on_non_universe_config_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_dir = copy_config_dir(Path(temporary_directory))
            governance_path = config_dir / "governance.yaml"
            governance_path.write_text(
                governance_path.read_text(encoding="utf-8").replace(
                    "content_version: null",
                    'content_version: "v1"',
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_configs(config_dir)

    def test_unsupported_schema_version_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_dir = copy_config_dir(Path(temporary_directory))
            methodology_path = config_dir / "methodology.yaml"
            methodology_path.write_text(
                methodology_path.read_text(encoding="utf-8").replace(
                    "schema_version: 1",
                    "schema_version: 2",
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_configs(config_dir)

    def test_duplicate_yaml_keys_fail_closed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_dir = copy_config_dir(Path(temporary_directory))
            category_map_path = config_dir / "category-map.yaml"
            original = category_map_path.read_text(encoding="utf-8")
            category_map_path.write_text(
                original.replace(
                    "mappings:",
                    "schema_version: 1\nmappings:",
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_configs(config_dir)

    def test_modified_v1_universe_entries_fail_closed(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            config_dir = copy_config_dir(Path(temporary_directory))
            universe_path = config_dir / "approved-universe.yaml"
            original = universe_path.read_text(encoding="utf-8")
            universe_path.write_text(
                original.rstrip("\n")
                + "\n"
                + '  - name: "Outside Universe Player"\n'
                + '    source_entry: "Outside Universe Player = higher/lower points"\n'
                + "    categories:\n"
                + "      - category: POINTS\n"
                + "        directions: [HIGHER, LOWER]\n",
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                load_configs(config_dir)

    def test_universe_entries_match_frozen_part_two_9_1_exactly(self) -> None:
        spec_entries = parse_universe_entries(self.spec)
        config_entries = {
            entry.name: entry.source_entry for entry in self.bundle.approved_universe.entries
        }

        expected_names = set(spec_entries) | {"Malik Monk"}
        self.assertEqual(set(config_entries), expected_names)
        for name, source_entry in spec_entries.items():
            with self.subTest(player=name):
                self.assertEqual(config_entries[name], source_entry)

        malik = next(
            entry for entry in self.bundle.approved_universe.entries if entry.name == "Malik Monk"
        )
        self.assertEqual(malik.categories, ())
        self.assertFalse(malik.foul_trouble)

    def test_normalized_categories_apply_a1_and_a2(self) -> None:
        entries = {entry.name: entry for entry in self.bundle.approved_universe.entries}

        def directions(name: str) -> dict[Category, tuple[Direction, ...]]:
            return {item.category: item.directions for item in entries[name].categories}

        self.assertEqual(
            directions("Tyrese Haliburton"),
            {
                Category.POINTS: (Direction.LOWER,),
                Category.ASSISTS: (Direction.HIGHER, Direction.LOWER),
            },
        )
        self.assertEqual(
            directions("Rudy Gobert"),
            {
                Category.POINTS: (Direction.LOWER,),
                Category.REBOUNDS: (Direction.HIGHER,),
            },
        )
        self.assertEqual(
            directions("Ivica Zubac"),
            {
                Category.POINTS: (Direction.HIGHER, Direction.LOWER),
                Category.REBOUNDS: (Direction.HIGHER, Direction.LOWER),
            },
        )
        self.assertEqual(
            directions("Luka Doncic"),
            {
                Category.POINTS: (Direction.HIGHER, Direction.LOWER),
                Category.ASSISTS: (Direction.HIGHER, Direction.LOWER),
                Category.REBOUNDS: (Direction.HIGHER, Direction.LOWER),
                Category.PRA: (Direction.HIGHER, Direction.LOWER),
            },
        )
        self.assertEqual(
            directions("LeBron James"),
            {
                Category.POINTS: (Direction.HIGHER, Direction.LOWER),
                Category.REBOUNDS_ASSISTS: (Direction.HIGHER, Direction.LOWER),
            },
        )
        self.assertEqual(
            directions("De'Aaron Fox"),
            {
                Category.POINTS: (Direction.LOWER,),
                Category.PRA: (Direction.LOWER,),
            },
        )

    def test_all_normalized_categories_follow_a1_and_a2(self) -> None:
        spec_entries = parse_universe_entries(self.spec)
        config_entries = {entry.name: entry for entry in self.bundle.approved_universe.entries}

        for name, source_entry in spec_entries.items():
            with self.subTest(player=name):
                actual = tuple(
                    (item.category, item.directions) for item in config_entries[name].categories
                )
                self.assertEqual(actual, expected_categories(source_entry))

    def test_three_point_attempts_is_preserved_only_where_frozen_9_1_lists_it(self) -> None:
        with_threes = {
            entry.name
            for entry in self.bundle.approved_universe.entries
            if any(item.category is Category.THREE_POINT_ATTEMPTS for item in entry.categories)
        }

        self.assertEqual(with_threes, {"Naz Reid", "Grayson Allen"})

    def test_foul_trouble_annotations_match_frozen_9_1(self) -> None:
        spec_entries = parse_universe_entries(self.spec)
        expected = {
            name for name, source_entry in spec_entries.items() if "foul trouble" in source_entry
        }
        actual = {
            entry.name for entry in self.bundle.approved_universe.entries if entry.foul_trouble
        }

        self.assertEqual(actual, expected)

    def test_trust_tiers_preserve_every_frozen_value(self) -> None:
        trust = self.bundle.trust_tiers

        self.assertEqual(
            trust.senior,
            parse_trust_list(self.spec, "## Part II Section 13 — Senior Players"),
        )
        self.assertEqual(
            trust.pra_trust,
            parse_trust_list(self.spec, "### Part II 12.1 — PRA Trust"),
        )
        self.assertEqual(
            trust.assist_trust,
            parse_trust_list(self.spec, "### Part II 12.2 — Assist Trust"),
        )
        self.assertEqual(
            trust.rebound_trust,
            parse_trust_list(self.spec, "### Part II 12.3 — Rebound Trust"),
        )

    def test_category_map_is_exact_and_never_maps_threes(self) -> None:
        self.assertEqual(
            dict(self.bundle.category_map.mappings),
            {
                "player_points": Category.POINTS,
                "player_assists": Category.ASSISTS,
                "player_rebounds": Category.REBOUNDS,
                "player_points_rebounds_assists": Category.PRA,
                "player_rebounds_assists": Category.REBOUNDS_ASSISTS,
            },
        )
        self.assertIsNone(self.bundle.category_map.resolve("player_threes"))
        self.assertIsNone(self.bundle.category_map.resolve("player_steals"))
        self.assertIsNone(self.bundle.category_map.resolve("PLAYER_POINTS"))

    def test_category_map_mappings_are_immutable(self) -> None:
        mappings = {
            "player_points": Category.POINTS,
            "player_assists": Category.ASSISTS,
            "player_rebounds": Category.REBOUNDS,
            "player_points_rebounds_assists": Category.PRA,
            "player_rebounds_assists": Category.REBOUNDS_ASSISTS,
        }
        category_map = CategoryMapConfig(
            metadata=self.bundle.category_map.metadata,
            mappings=mappings,
        )
        readonly_mappings: Any = category_map.mappings

        with self.assertRaises(TypeError):
            operator.setitem(
                readonly_mappings,
                "player_threes",
                Category.THREE_POINT_ATTEMPTS,
            )

        mappings["player_threes"] = Category.THREE_POINT_ATTEMPTS
        self.assertIsNone(category_map.resolve("player_threes"))

    def test_approved_sources_list_only_frozen_sources_and_null_unknown_fields(self) -> None:
        sources = {source.source_id: source for source in self.bundle.approved_sources.sources}

        self.assertEqual(
            set(sources),
            {
                "the-odds-api-us-dfs",
                "nba-com",
                "official-nba-injury-report",
                "sports-illustrated-nba",
            },
        )
        odds_api = sources["the-odds-api-us-dfs"]
        self.assertEqual(odds_api.role, "projection-board")
        self.assertEqual(odds_api.access_method, "the-odds-api:us_dfs")
        self.assertEqual(
            odds_api.approved_data,
            ("POINTS", "ASSISTS", "REBOUNDS", "PRA", "REBOUNDS_ASSISTS"),
        )

        for source in self.bundle.approved_sources.sources:
            with self.subTest(source=source.source_id):
                self.assertIsNone(source.freshness_policy)
                self.assertIsNone(source.terms_review_status)
                if source.source_id != "the-odds-api-us-dfs":
                    self.assertIsNone(source.access_method)

        self.assertIn(
            "A supporting source must not override the fantasy platform's projection board.",
            self.bundle.approved_sources.rules,
        )

    def test_methodology_and_governance_encode_frozen_values_without_m6_logic(self) -> None:
        methodology = self.bundle.methodology
        governance = self.bundle.governance

        self.assertEqual(methodology.confidence_levels, ("HIGH", "MEDIUM", "LOW"))
        self.assertIn(
            "Foul trouble is a caution signal, not a deterministic block "
            "or an automatic confidence cap.",
            methodology.rules,
        )
        self.assertIn(
            "Only Joseph may promote a LOW-confidence candidate into the final slate.",
            methodology.rules,
        )

        self.assertEqual(governance.owner, "Joseph Edafiadhe")
        self.assertEqual(governance.authority, "Governance Zero")
        self.assertEqual(governance.approval_actions, ("APPROVE", "REJECT", "MODIFY"))
        self.assertTrue(governance.zero_selections_valid)
        self.assertTrue(governance.never_fill_slots)

        ceilings = {ceiling.label: ceiling for ceiling in governance.ceilings}
        self.assertEqual(ceilings["HALF"].minimum_games, 1)
        self.assertEqual(ceilings["HALF"].maximum_games, 4)
        self.assertEqual(ceilings["HALF"].maximum_selections, 4)
        self.assertEqual(ceilings["FULL"].minimum_games, 5)
        self.assertIsNone(ceilings["FULL"].maximum_games)
        self.assertEqual(ceilings["FULL"].maximum_selections, 5)
