"""Synthetic, offline fixtures shared by M6 tests."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fifth_pick.evidence import (
    EvidenceEffect,
    EvidenceGap,
    EvidenceItem,
    EvidenceKind,
    EvidenceSignificance,
    PerformanceSample,
)
from fifth_pick.methodology import (
    CandidateCase,
    Confidence,
    MethodologyDisposition,
    MethodologyJudgment,
)
from fifth_pick.models import (
    Category,
    Direction,
    Evidence,
    Observation,
    Platform,
    Provenance,
    Snapshot,
)
from fifth_pick.registry import canonical_player_id
from fifth_pick.snapshots import SnapshotEvidence, snapshot_2_target
from fifth_pick.sources.base import EvidenceMode
from fifth_pick.sources.odds_api import SOURCE_ID

NOW = datetime(2026, 11, 15, 17, 0, tzinfo=UTC)
TIPOFF = datetime(2026, 11, 15, 20, 0, tzinfo=UTC)
EVENT_ID = "fixture-m6-event"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "evidence" / "m6-history.json"
FIXTURE_DATA = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def candidate_key(
    name: str,
    *,
    platform: Platform = Platform.PRIZEPICKS,
    category: Category = Category.POINTS,
    direction: Direction = Direction.HIGHER,
) -> str:
    identity = json.dumps(
        [EVENT_ID, platform.value, canonical_player_id(name), category.value, direction.value],
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def make_snapshots(
    name: str = "Luka Doncic",
    *,
    platform: Platform = Platform.PRIZEPICKS,
    category: Category = Category.POINTS,
    direction: Direction = Direction.HIGHER,
    projections: tuple[float, float, float] = (32.5, 33.0, 33.5),
    tipoff_at: datetime = TIPOFF,
    late_snapshot_3: bool = False,
) -> tuple[SnapshotEvidence, ...]:
    times = (
        NOW,
        datetime(2026, 11, 15, 18, 20, tzinfo=UTC),
        (
            datetime(2026, 11, 15, 19, 45, tzinfo=UTC)
            if late_snapshot_3
            else datetime(2026, 11, 15, 19, 38, tzinfo=UTC)
        ),
    )
    key = candidate_key(name, platform=platform, category=category, direction=direction)
    records: list[SnapshotEvidence] = []
    for number, (retrieved_at, projection) in enumerate(zip(times, projections, strict=True), 1):
        observation = Observation(
            platform=platform,
            player=name,
            category=category,
            projection=projection,
            direction=direction,
            event=EVENT_ID,
            source_update_time=retrieved_at - timedelta(minutes=2),
            retrieved_at=retrieved_at,
            snapshot_number=number,
            source=SOURCE_ID,
        )
        excerpt = {
            "platform": platform.value,
            "provider_player_name": name,
            "category": category.value,
            "projection": projection,
            "direction": direction.value,
            "event_id": EVENT_ID,
            "source_update_time": observation.source_update_time.isoformat(),
            "retrieved_at": retrieved_at.isoformat(),
        }
        provenance = Provenance(
            source=SOURCE_ID,
            retrieved_at=retrieved_at,
            source_timestamp=observation.source_update_time,
            access_method="synthetic-fixture-transport",
            reference=f"{SOURCE_ID}:event:{EVENT_ID}",
            payload_hash=("a" if number == 1 else "b" if number == 2 else "c") * 64,
        )
        records.append(
            SnapshotEvidence(
                snapshot=Snapshot(number, observation, retrieved_at),
                candidate_id=canonical_player_id(name),
                candidate_key=key,
                evidence_mode=EvidenceMode.FIXTURE,
                event_id=EVENT_ID,
                event_start=tipoff_at,
                target_at=(
                    None
                    if number == 1
                    else (
                        snapshot_2_target(times[0], tipoff_at)
                        if number == 2
                        else tipoff_at - timedelta(minutes=20)
                    )
                ),
                late=number == 3 and late_snapshot_3,
                provenance=provenance,
                source_excerpt=excerpt,
            )
        )
    return tuple(records)


def make_evidence_item(
    key: str,
    evidence_id: str,
    kind: EvidenceKind,
    *,
    effect: EvidenceEffect = EvidenceEffect.SUPPORTS,
    significance: EvidenceSignificance = EvidenceSignificance.IMPORTANT,
    samples: tuple[PerformanceSample, ...] = (),
    facts: dict[str, str | int | float | bool] | None = None,
) -> EvidenceItem:
    provenance = Provenance(
        source="synthetic-fixture",
        retrieved_at=NOW,
        source_timestamp=NOW - timedelta(minutes=1),
        access_method="synthetic-fixture",
        reference=f"fixture:evidence/{evidence_id}",
        payload_hash=hashlib.sha256(evidence_id.encode()).hexdigest(),
    )
    return EvidenceItem(
        evidence_id=evidence_id,
        candidate_key=key,
        kind=kind,
        evidence=Evidence(
            claim=f"Synthetic fixture evidence {evidence_id}.",
            provenance=provenance,
            excerpt=f"Synthetic fixture excerpt {evidence_id}.",
        ),
        evidence_mode=EvidenceMode.FIXTURE,
        effect=effect,
        significance=significance,
        samples=samples,
        facts={} if facts is None else facts,
    )


def make_evidence_set(
    key: str,
    *,
    include_foul_trouble: bool = False,
    role_effect: EvidenceEffect = EvidenceEffect.SUPPORTS,
    role_significance: EvidenceSignificance = EvidenceSignificance.IMPORTANT,
) -> tuple[EvidenceItem, ...]:
    def samples(field: str) -> tuple[PerformanceSample, ...]:
        return tuple(
            PerformanceSample(
                played_at=datetime.fromisoformat(row["played_at"]),
                value=row["value"],
                opponent=row["opponent"],
                season=row["season"],
            )
            for row in FIXTURE_DATA[field]
        )

    evidence = [
        make_evidence_item(
            key,
            "matchup",
            EvidenceKind.MATCHUP,
            facts={
                "team": FIXTURE_DATA["team"],
                "opponent": FIXTURE_DATA["opponent"],
                "season": FIXTURE_DATA["season"],
            },
        ),
        make_evidence_item(key, "last8", EvidenceKind.LAST_8, samples=samples("last_8")),
        make_evidence_item(
            key,
            "h2h",
            EvidenceKind.SAME_SEASON_H2H,
            samples=samples("same_season_h2h"),
        ),
        make_evidence_item(
            key,
            "role",
            EvidenceKind.ROLE_MINUTES,
            effect=role_effect,
            significance=role_significance,
            facts={"role": "synthetic-starter", "minutes_security": "stable"},
        ),
        make_evidence_item(
            key,
            "game-total",
            EvidenceKind.GAME_TOTAL,
            significance=EvidenceSignificance.MEANINGFUL,
            facts={"total": FIXTURE_DATA["game_total"]},
        ),
        make_evidence_item(
            key,
            "spread",
            EvidenceKind.POINT_SPREAD,
            significance=EvidenceSignificance.MEANINGFUL,
            facts={"spread": FIXTURE_DATA["point_spread"]},
        ),
        make_evidence_item(
            key,
            "blowout-risk",
            EvidenceKind.BLOWOUT_RISK,
            effect=EvidenceEffect.CONCERN,
            significance=EvidenceSignificance.MEANINGFUL,
        ),
    ]
    if include_foul_trouble:
        evidence.append(
            make_evidence_item(
                key,
                "foul-trouble",
                EvidenceKind.FOUL_TROUBLE,
                effect=EvidenceEffect.CONCERN,
                significance=EvidenceSignificance.MINOR,
            )
        )
    return tuple(evidence)


def make_judgment(
    evidence: tuple[EvidenceItem, ...],
    *,
    confidence=None,
    disposition=MethodologyDisposition.QUALIFY,
    senior_lower_support_ids: tuple[str, ...] = (),
    senior_lower_disclosure: str = "",
) -> MethodologyJudgment:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    return MethodologyJudgment(
        disposition=disposition,
        confidence=Confidence.HIGH if confidence is None else confidence,
        rationale="Synthetic fixture judgment with cited supporting signals.",
        supporting_evidence_ids=("last8", "role"),
        meaningful_risk_ids=(("blowout-risk",) if "blowout-risk" in evidence_by_id else ()),
        sufficient_evidence=True,
        major_unresolved_concern=False,
        senior_lower_support_ids=senior_lower_support_ids,
        senior_lower_disclosure=senior_lower_disclosure,
    )


def make_case(
    *,
    name: str = "Luka Doncic",
    platform: Platform = Platform.PRIZEPICKS,
    category: Category = Category.POINTS,
    direction: Direction = Direction.HIGHER,
    evidence: tuple[EvidenceItem, ...] | None = None,
    gaps: tuple[EvidenceGap, ...] = (),
    judgment: MethodologyJudgment | None = None,
    projections: tuple[float, float, float] = (32.5, 33.0, 33.5),
    late_snapshot_3: bool = False,
) -> CandidateCase:
    snapshots = make_snapshots(
        name,
        platform=platform,
        category=category,
        direction=direction,
        projections=projections,
        late_snapshot_3=late_snapshot_3,
    )
    key = snapshots[0].candidate_key
    items = make_evidence_set(key) if evidence is None else evidence
    assessment = make_judgment(items) if judgment is None else judgment
    return CandidateCase(
        snapshots=snapshots,
        missed=(),
        evidence=items,
        gaps=gaps,
        judgment=assessment,
    )
