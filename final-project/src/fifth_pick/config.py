"""Authoritative YAML configuration loading and metadata validation."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

import yaml

from fifth_pick.errors import ValidationError
from fifth_pick.models import Category, Direction

CONFIG_FILENAMES: Final[tuple[str, ...]] = (
    "approved-universe",
    "trust-tiers",
    "methodology",
    "governance",
    "category-map",
    "approved-sources",
)
_PACKAGED_CONFIG = Path(__file__).with_name("data") / "config"
DEFAULT_CONFIG_DIR: Final[Path] = (
    _PACKAGED_CONFIG
    if _PACKAGED_CONFIG.is_dir()
    else Path(__file__).resolve().parents[2] / "config" / "fifth-pick"
)
SCHEMA_VERSION: Final[int] = 1
UNIVERSE_CONTENT_VERSION: Final[str] = "v1"
UNIVERSE_EFFECTIVE_DATE: Final[str] = "2026-11-15"
APPROVED_UNIVERSE_ENTRIES_SHA256: Final[str] = (
    "5b80fc42654e72f0a04d184fa078e319126bfbdb9117d672be71529d0ec6c121"
)
APPROVED_CATEGORY_MAPPINGS: Final[dict[str, Category]] = {
    "player_points": Category.POINTS,
    "player_assists": Category.ASSISTS,
    "player_rebounds": Category.REBOUNDS,
    "player_points_rebounds_assists": Category.PRA,
    "player_rebounds_assists": Category.REBOUNDS_ASSISTS,
}


class ConfigError(ValidationError):
    """Raised when authoritative configuration is missing or malformed."""


@dataclass(frozen=True, slots=True)
class ConfigMetadata:
    """Schema and owner metadata for one authoritative config file."""

    schema_version: int
    content_version: str | None
    effective_date: str | None
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UniverseCategory:
    """One explicitly authorized category and its exact directions."""

    category: Category
    directions: tuple[Direction, ...]


@dataclass(frozen=True, slots=True)
class UniverseEntry:
    """One player entry from the approved universe."""

    name: str
    source_entry: str
    categories: tuple[UniverseCategory, ...]
    aliases: tuple[str, ...] = ()
    foul_trouble: bool = False


@dataclass(frozen=True, slots=True)
class ApprovedUniverseConfig:
    """The owner-approved player, category, and direction universe."""

    metadata: ConfigMetadata
    entries: tuple[UniverseEntry, ...]


@dataclass(frozen=True, slots=True)
class TrustTiersConfig:
    """Frozen evaluation classifications. These never grant authorization."""

    metadata: ConfigMetadata
    senior: tuple[str, ...]
    pra_trust: tuple[str, ...]
    assist_trust: tuple[str, ...]
    rebound_trust: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MethodologyConfig:
    """Frozen methodology values without M6 evaluation logic."""

    metadata: ConfigMetadata
    confidence_levels: tuple[str, ...]
    rules: tuple[str, ...]
    heuristics: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class SlateCeiling:
    """One frozen slate-size ceiling."""

    label: str
    minimum_games: int
    maximum_games: int | None
    maximum_selections: int


@dataclass(frozen=True, slots=True)
class GovernanceConfig:
    """Frozen owner authority, ceilings, and approval vocabulary."""

    metadata: ConfigMetadata
    owner: str
    authority: str
    ceilings: tuple[SlateCeiling, ...]
    approval_actions: tuple[str, ...]
    zero_selections_valid: bool
    never_fill_slots: bool
    universe_change_control: str


@dataclass(frozen=True, slots=True)
class CategoryMapConfig:
    """Exact provider-market to canonical-category mapping."""

    metadata: ConfigMetadata
    mappings: Mapping[str, Category]

    def __post_init__(self) -> None:
        object.__setattr__(self, "mappings", MappingProxyType(dict(self.mappings)))

    def resolve(self, market_label: str) -> Category | None:
        """Return a category only for an exact registered market label."""

        return self.mappings.get(market_label)


@dataclass(frozen=True, slots=True)
class ApprovedSource:
    """One approved source and the restrictions present in the frozen design."""

    source_id: str
    display_name: str
    role: str
    approved_data: tuple[str, ...]
    access_method: str | None
    freshness_policy: str | None
    terms_review_status: str | None
    restrictions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ApprovedSourcesConfig:
    """Approved sources and cross-source precedence rules."""

    metadata: ConfigMetadata
    rules: tuple[str, ...]
    sources: tuple[ApprovedSource, ...]


@dataclass(frozen=True, slots=True)
class ConfigBundle:
    """The six loaded authoritative configs."""

    config_dir: Path
    approved_universe: ApprovedUniverseConfig
    trust_tiers: TrustTiersConfig
    methodology: MethodologyConfig
    governance: GovernanceConfig
    category_map: CategoryMapConfig
    approved_sources: ApprovedSourcesConfig


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    if not isinstance(node, yaml.MappingNode):
        raise ConfigError("expected a YAML mapping")

    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_yaml(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"missing required config: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"cannot read config: {path}") from exc

    try:
        document = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}") from exc

    if not isinstance(document, dict):
        raise ConfigError(f"{path} must contain a YAML mapping")

    result: dict[str, object] = {}
    for key, value in document.items():
        if not isinstance(key, str):
            raise ConfigError(f"{path} has a non-string key")
        result[key] = value
    return result


def _require_mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")

    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigError(f"{field} has a non-string key")
        result[key] = item
    return result


def _require_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ConfigError(f"{field} must be a list")
    return value


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a non-empty string")
    return value


def _require_optional_str(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, field)


def _require_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{field} must be an integer")
    return value


def _require_optional_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, field)


def _require_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{field} must be a boolean")
    return value


def _require_str_list(value: object, field: str) -> tuple[str, ...]:
    items = _require_list(value, field)
    return tuple(_require_str(item, f"{field}[{index}]") for index, item in enumerate(items))


def _require_unique_str_list(value: object, field: str) -> tuple[str, ...]:
    items = _require_str_list(value, field)
    if len(set(items)) != len(items):
        raise ConfigError(f"{field} contains duplicate values")
    return items


def _require_keys(
    document: Mapping[str, object],
    *,
    config_name: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    actual = set(document)
    missing = required - actual
    unknown = actual - required - optional
    if missing:
        raise ConfigError(f"{config_name} is missing keys: {sorted(missing)}")
    if unknown:
        raise ConfigError(f"{config_name} has unknown keys: {sorted(unknown)}")


def _parse_metadata(
    document: Mapping[str, object],
    *,
    config_name: str,
    owner_metadata: bool,
) -> ConfigMetadata:
    schema_version = _require_int(document["schema_version"], f"{config_name}.schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ConfigError(f"{config_name}.schema_version must be {SCHEMA_VERSION}")

    content_version = _require_optional_str(
        document["content_version"],
        f"{config_name}.content_version",
    )
    effective_date = _require_optional_str(
        document["effective_date"],
        f"{config_name}.effective_date",
    )
    provenance = _require_str_list(document["provenance"], f"{config_name}.provenance")
    if not provenance:
        raise ConfigError(f"{config_name}.provenance must not be empty")

    if owner_metadata:
        if content_version != UNIVERSE_CONTENT_VERSION:
            raise ConfigError(f"{config_name}.content_version must be {UNIVERSE_CONTENT_VERSION!r}")
        if effective_date != UNIVERSE_EFFECTIVE_DATE:
            raise ConfigError(f"{config_name}.effective_date must be {UNIVERSE_EFFECTIVE_DATE!r}")
        provenance_text = "\n".join(provenance)
        if "Part II 9.1" not in provenance_text or UNIVERSE_EFFECTIVE_DATE not in provenance_text:
            raise ConfigError(f"{config_name}.provenance must name Part II 9.1 and 2026-11-15")
    elif content_version is not None or effective_date is not None:
        raise ConfigError(
            f"{config_name} must not infer owner metadata; "
            "content_version and effective_date must be null"
        )

    return ConfigMetadata(
        schema_version=schema_version,
        content_version=content_version,
        effective_date=effective_date,
        provenance=provenance,
    )


def _parse_universe_category(value: object, field: str) -> UniverseCategory:
    document = _require_mapping(value, field)
    _require_keys(
        document,
        config_name=field,
        required=frozenset({"category", "directions"}),
    )

    category_name = _require_str(document["category"], f"{field}.category")
    try:
        category = Category(category_name)
    except ValueError as exc:
        raise ConfigError(f"{field}.category is not canonical: {category_name!r}") from exc

    raw_directions = _require_list(document["directions"], f"{field}.directions")
    if not raw_directions:
        raise ConfigError(f"{field}.directions must not be empty")

    directions: list[Direction] = []
    for index, raw_direction in enumerate(raw_directions):
        direction_name = _require_str(raw_direction, f"{field}.directions[{index}]")
        try:
            direction = Direction(direction_name)
        except ValueError as exc:
            raise ConfigError(f"{field}.directions[{index}] is not canonical") from exc
        if direction in directions:
            raise ConfigError(f"{field}.directions contains a duplicate")
        directions.append(direction)

    return UniverseCategory(category=category, directions=tuple(directions))


def _parse_universe_entry(value: object, index: int) -> UniverseEntry:
    field = f"approved-universe.entries[{index}]"
    document = _require_mapping(value, field)
    _require_keys(
        document,
        config_name=field,
        required=frozenset({"name", "source_entry", "categories"}),
        optional=frozenset({"aliases", "foul_trouble"}),
    )

    name = _require_str(document["name"], f"{field}.name")
    source_entry = _require_str(document["source_entry"], f"{field}.source_entry")
    raw_categories = _require_list(document["categories"], f"{field}.categories")

    categories: list[UniverseCategory] = []
    for category_index, raw_category in enumerate(raw_categories):
        category = _parse_universe_category(
            raw_category,
            f"{field}.categories[{category_index}]",
        )
        if any(existing.category is category.category for existing in categories):
            raise ConfigError(f"{field} repeats category {category.category.value}")
        categories.append(category)

    raw_aliases = document.get("aliases", [])
    aliases = _require_unique_str_list(raw_aliases, f"{field}.aliases")
    foul_trouble = _require_bool(document.get("foul_trouble", False), f"{field}.foul_trouble")

    return UniverseEntry(
        name=name,
        source_entry=source_entry,
        categories=tuple(categories),
        aliases=aliases,
        foul_trouble=foul_trouble,
    )


def _canonical_entries_digest(raw_entries: list[object]) -> str:
    """Return the SHA-256 of the canonical JSON of the parsed universe entries.

    Canonicalization is deterministic: sorted object keys, compact separators,
    UTF-8 encoding, and preserved list order. Only the ``entries`` content is
    hashed, so metadata edits cannot silently re-authorize a different universe.
    """

    canonical = json.dumps(
        raw_entries,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_approved_universe(document: Mapping[str, object]) -> ApprovedUniverseConfig:
    config_name = "approved-universe"
    _require_keys(
        document,
        config_name=config_name,
        required=frozenset(
            {"schema_version", "content_version", "effective_date", "provenance", "entries"}
        ),
    )
    metadata = _parse_metadata(document, config_name=config_name, owner_metadata=True)

    raw_entries = _require_list(document["entries"], f"{config_name}.entries")
    if not raw_entries:
        raise ConfigError(f"{config_name}.entries must not be empty")

    if _canonical_entries_digest(raw_entries) != APPROVED_UNIVERSE_ENTRIES_SHA256:
        raise ConfigError(
            f"{config_name}.entries do not match the authorized "
            f"{UNIVERSE_CONTENT_VERSION} content digest"
        )

    entries = tuple(
        _parse_universe_entry(raw_entry, index) for index, raw_entry in enumerate(raw_entries)
    )
    names = [entry.name for entry in entries]
    if len(set(names)) != len(names):
        raise ConfigError(f"{config_name}.entries contains duplicate player names")

    return ApprovedUniverseConfig(metadata=metadata, entries=entries)


def _parse_trust_tiers(document: Mapping[str, object]) -> TrustTiersConfig:
    config_name = "trust-tiers"
    _require_keys(
        document,
        config_name=config_name,
        required=frozenset(
            {
                "schema_version",
                "content_version",
                "effective_date",
                "provenance",
                "senior",
                "pra_trust",
                "assist_trust",
                "rebound_trust",
            }
        ),
    )
    metadata = _parse_metadata(document, config_name=config_name, owner_metadata=False)

    return TrustTiersConfig(
        metadata=metadata,
        senior=_require_unique_str_list(document["senior"], f"{config_name}.senior"),
        pra_trust=_require_unique_str_list(document["pra_trust"], f"{config_name}.pra_trust"),
        assist_trust=_require_unique_str_list(
            document["assist_trust"],
            f"{config_name}.assist_trust",
        ),
        rebound_trust=_require_unique_str_list(
            document["rebound_trust"],
            f"{config_name}.rebound_trust",
        ),
    )


def _parse_methodology(document: Mapping[str, object]) -> MethodologyConfig:
    config_name = "methodology"
    _require_keys(
        document,
        config_name=config_name,
        required=frozenset(
            {
                "schema_version",
                "content_version",
                "effective_date",
                "provenance",
                "confidence_levels",
                "rules",
                "heuristics",
            }
        ),
    )
    metadata = _parse_metadata(document, config_name=config_name, owner_metadata=False)

    confidence_levels = _require_unique_str_list(
        document["confidence_levels"],
        f"{config_name}.confidence_levels",
    )
    if confidence_levels != ("HIGH", "MEDIUM", "LOW"):
        raise ConfigError(f"{config_name}.confidence_levels must be HIGH, MEDIUM, LOW")

    rules = _require_str_list(document["rules"], f"{config_name}.rules")
    if not rules:
        raise ConfigError(f"{config_name}.rules must not be empty")

    raw_heuristics = _require_mapping(document["heuristics"], f"{config_name}.heuristics")
    heuristics = {
        _require_str(key, f"{config_name}.heuristics key"): _require_str(
            value,
            f"{config_name}.heuristics.{key}",
        )
        for key, value in raw_heuristics.items()
    }

    return MethodologyConfig(
        metadata=metadata,
        confidence_levels=confidence_levels,
        rules=rules,
        heuristics=heuristics,
    )


def _parse_ceiling(value: object, index: int) -> SlateCeiling:
    field = f"governance.ceilings[{index}]"
    document = _require_mapping(value, field)
    _require_keys(
        document,
        config_name=field,
        required=frozenset({"label", "minimum_games", "maximum_games", "maximum_selections"}),
    )
    return SlateCeiling(
        label=_require_str(document["label"], f"{field}.label"),
        minimum_games=_require_int(document["minimum_games"], f"{field}.minimum_games"),
        maximum_games=_require_optional_int(
            document["maximum_games"],
            f"{field}.maximum_games",
        ),
        maximum_selections=_require_int(
            document["maximum_selections"],
            f"{field}.maximum_selections",
        ),
    )


def _parse_governance(document: Mapping[str, object]) -> GovernanceConfig:
    config_name = "governance"
    _require_keys(
        document,
        config_name=config_name,
        required=frozenset(
            {
                "schema_version",
                "content_version",
                "effective_date",
                "provenance",
                "owner",
                "authority",
                "ceilings",
                "approval_actions",
                "zero_selections_valid",
                "never_fill_slots",
                "universe_change_control",
            }
        ),
    )
    metadata = _parse_metadata(document, config_name=config_name, owner_metadata=False)

    raw_ceilings = _require_list(document["ceilings"], f"{config_name}.ceilings")
    ceilings = tuple(
        _parse_ceiling(raw_ceiling, index) for index, raw_ceiling in enumerate(raw_ceilings)
    )
    if {ceiling.label for ceiling in ceilings} != {"HALF", "FULL"}:
        raise ConfigError(f"{config_name}.ceilings must define HALF and FULL")

    approval_actions = _require_unique_str_list(
        document["approval_actions"],
        f"{config_name}.approval_actions",
    )
    if approval_actions != ("APPROVE", "REJECT", "MODIFY"):
        raise ConfigError(f"{config_name}.approval_actions must be APPROVE, REJECT, MODIFY")

    return GovernanceConfig(
        metadata=metadata,
        owner=_require_str(document["owner"], f"{config_name}.owner"),
        authority=_require_str(document["authority"], f"{config_name}.authority"),
        ceilings=ceilings,
        approval_actions=approval_actions,
        zero_selections_valid=_require_bool(
            document["zero_selections_valid"],
            f"{config_name}.zero_selections_valid",
        ),
        never_fill_slots=_require_bool(
            document["never_fill_slots"],
            f"{config_name}.never_fill_slots",
        ),
        universe_change_control=_require_str(
            document["universe_change_control"],
            f"{config_name}.universe_change_control",
        ),
    )


def _parse_category_map(document: Mapping[str, object]) -> CategoryMapConfig:
    config_name = "category-map"
    _require_keys(
        document,
        config_name=config_name,
        required=frozenset(
            {"schema_version", "content_version", "effective_date", "provenance", "mappings"}
        ),
    )
    metadata = _parse_metadata(document, config_name=config_name, owner_metadata=False)

    raw_mappings = _require_mapping(document["mappings"], f"{config_name}.mappings")
    mappings: dict[str, Category] = {}
    for market_label, raw_category in raw_mappings.items():
        category_name = _require_str(
            raw_category,
            f"{config_name}.mappings.{market_label}",
        )
        try:
            category = Category(category_name)
        except ValueError as exc:
            raise ConfigError(f"{config_name}.mappings.{market_label} is not canonical") from exc
        if market_label in mappings:
            raise ConfigError(f"{config_name}.mappings repeats {market_label!r}")
        mappings[market_label] = category

    if mappings != APPROVED_CATEGORY_MAPPINGS:
        raise ConfigError(f"{config_name}.mappings must contain exactly the approved live markets")

    return CategoryMapConfig(metadata=metadata, mappings=mappings)


def _parse_approved_source(value: object, index: int) -> ApprovedSource:
    field = f"approved-sources.sources[{index}]"
    document = _require_mapping(value, field)
    _require_keys(
        document,
        config_name=field,
        required=frozenset(
            {
                "source_id",
                "display_name",
                "role",
                "approved_data",
                "access_method",
                "freshness_policy",
                "terms_review_status",
                "restrictions",
            }
        ),
    )
    return ApprovedSource(
        source_id=_require_str(document["source_id"], f"{field}.source_id"),
        display_name=_require_str(document["display_name"], f"{field}.display_name"),
        role=_require_str(document["role"], f"{field}.role"),
        approved_data=_require_str_list(document["approved_data"], f"{field}.approved_data"),
        access_method=_require_optional_str(document["access_method"], f"{field}.access_method"),
        freshness_policy=_require_optional_str(
            document["freshness_policy"],
            f"{field}.freshness_policy",
        ),
        terms_review_status=_require_optional_str(
            document["terms_review_status"],
            f"{field}.terms_review_status",
        ),
        restrictions=_require_str_list(document["restrictions"], f"{field}.restrictions"),
    )


def _parse_approved_sources(document: Mapping[str, object]) -> ApprovedSourcesConfig:
    config_name = "approved-sources"
    _require_keys(
        document,
        config_name=config_name,
        required=frozenset(
            {
                "schema_version",
                "content_version",
                "effective_date",
                "provenance",
                "rules",
                "sources",
            }
        ),
    )
    metadata = _parse_metadata(document, config_name=config_name, owner_metadata=False)

    raw_sources = _require_list(document["sources"], f"{config_name}.sources")
    if not raw_sources:
        raise ConfigError(f"{config_name}.sources must not be empty")
    sources = tuple(
        _parse_approved_source(raw_source, index) for index, raw_source in enumerate(raw_sources)
    )
    source_ids = [source.source_id for source in sources]
    if len(set(source_ids)) != len(source_ids):
        raise ConfigError(f"{config_name}.sources contains duplicate source ids")

    return ApprovedSourcesConfig(
        metadata=metadata,
        rules=_require_str_list(document["rules"], f"{config_name}.rules"),
        sources=sources,
    )


def load_configs(config_dir: str | Path = DEFAULT_CONFIG_DIR) -> ConfigBundle:
    """Load and validate the six authoritative configs from one directory."""

    root = Path(config_dir)
    if not root.is_dir():
        raise ConfigError(f"config directory does not exist: {root}")

    documents = {name: _load_yaml(root / f"{name}.yaml") for name in CONFIG_FILENAMES}

    return ConfigBundle(
        config_dir=root,
        approved_universe=_parse_approved_universe(documents["approved-universe"]),
        trust_tiers=_parse_trust_tiers(documents["trust-tiers"]),
        methodology=_parse_methodology(documents["methodology"]),
        governance=_parse_governance(documents["governance"]),
        category_map=_parse_category_map(documents["category-map"]),
        approved_sources=_parse_approved_sources(documents["approved-sources"]),
    )
