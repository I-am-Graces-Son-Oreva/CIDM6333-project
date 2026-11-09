import tempfile
from pathlib import Path

from .conditions import (
    EVIDENCE_LABEL,
    QUESTION_ABSENT,
    QUESTION_CONTROL,
    QUESTION_RECALL,
    SANDBOX_PROFILE,
    SERVICE_CONFIG,
    build_off_sandbox,
    build_on_sandbox,
    connection_probe,
    isolation_probes,
    probes_ok,
    run_wrapper,
    service_port,
    service_reachable,
    sha256_text,
    sidecar_path,
    tp5_isolation,
    verify_on_event,
    write_json,
)
from .fixture import FIXTURE_PATH, claim_hash, load_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "evolution-07" / "evidence"


def run_preflight(evidence_dir=EVIDENCE_DIR):
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    fixture = load_fixture()

    with tempfile.TemporaryDirectory(prefix="e7-preflight-") as temp:
        temp = Path(temp)
        off_sandbox = temp / "off"
        on_sandbox = temp / "on"
        private_dir = temp / "private"
        on_sidecar = sidecar_path(on_sandbox)

        off_manifest = build_off_sandbox(
            off_sandbox,
            private_paths=[on_sandbox, private_dir, on_sidecar],
        )
        on_manifest = build_on_sandbox(
            on_sandbox,
            private_dir,
            private_paths=[off_sandbox],
        )

        off_probes = isolation_probes(
            off_sandbox,
            off_sandbox / SANDBOX_PROFILE,
            extra_denied=[
                ("on_sandbox_service_config", on_sandbox / SERVICE_CONFIG),
                ("on_sandbox_profile", on_sandbox / SANDBOX_PROFILE),
                ("private_store", on_manifest["fixture_store"]),
                ("private_ledger", on_manifest["fixture_ledger"]),
                ("private_sidecar", on_manifest["sidecar"]),
            ],
        )

        on_port = service_port(on_sandbox)
        on_service_reachable_during_off = service_reachable(on_port)
        off_connection_attempt = connection_probe(
            off_sandbox / SANDBOX_PROFILE,
            off_sandbox,
            on_port,
        )

        recall_result = run_wrapper(on_sandbox, QUESTION_RECALL)
        control_result = run_wrapper(on_sandbox, QUESTION_CONTROL)
        absent_result = run_wrapper(on_sandbox, QUESTION_ABSENT)

        on_probes = isolation_probes(
            on_sandbox,
            on_sandbox / SANDBOX_PROFILE,
            extra_denied=[
                ("private_store", on_manifest["fixture_store"]),
                ("private_ledger", on_manifest["fixture_ledger"]),
                ("private_sidecar", on_manifest["sidecar"]),
                ("off_sandbox_profile", off_sandbox / SANDBOX_PROFILE),
            ],
        )

        event_matches, recall_event = verify_on_event(
            temp / "private" / "fixture-memory-ledger.jsonl",
            fixture["id"],
            fixture["source"],
            QUESTION_RECALL,
        )

        data = {
            "label": EVIDENCE_LABEL,
            "fixture": {
                "path": str(FIXTURE_PATH),
                "source": fixture["source"],
                "claim_sha256": claim_hash(),
                "question": QUESTION_RECALL,
                "expected_answer_sha256": sha256_text(
                    fixture["expected_answer"]
                ),
            },
            "conditions": {
                "memory-off": off_manifest,
                "memory-on": on_manifest,
            },
            "same_model": off_manifest["model"] == on_manifest["model"],
            "same_question": (
                off_manifest["question_recall"]
                == on_manifest["question_recall"]
                == QUESTION_RECALL
            ),
            "same_generation": (
                off_manifest["generation"]
                == on_manifest["generation"]
            ),
            "retriever": {
                "recall_output_sha256": sha256_text(recall_result.stdout),
                "control_output_sha256": sha256_text(control_result.stdout),
                "absent_output_sha256": sha256_text(absent_result.stdout),
                "recall_event_matches_fixture": event_matches,
                "recall_event": recall_event,
                "control_retriever_response": control_result.stdout.strip(),
                "absent_retriever_response": absent_result.stdout.strip(),
                "control_expected_agent_answer": "4",
            },
            "isolation": {
                "off_claim_present": off_manifest[
                    "claim_present_in_sandbox"
                ],
                "on_claim_present_in_sandbox": on_manifest[
                    "claim_present_in_sandbox"
                ],
                "on_fixture_store_outside_sandbox": on_manifest[
                    "fixture_store_outside_sandbox"
                ],
                "off_negative_probes": off_probes,
                "on_negative_probes": on_probes,
                "off_probes_ok": probes_ok(off_probes),
                "on_probes_ok": probes_ok(on_probes),
                "off_denied_private_artifacts": off_manifest[
                    "denied_private_artifacts"
                ],
                "on_denied_private_artifacts": on_manifest[
                    "denied_private_artifacts"
                ],
            },
            "network_isolation": {
                "mode": (
                    "lifecycle: the memory-ON retrieval service is not "
                    "started during memory-OFF; network access is not "
                    "claimed isolated"
                ),
                "on_service_reachable_during_off": (
                    on_service_reachable_during_off
                ),
                "off_connection_attempt": off_connection_attempt,
                "off_launch_starts_service": (
                    "serve-on"
                    in (off_sandbox / "launch.sh").read_text(
                        encoding="utf-8"
                    )
                ),
            },
        }

    isolation_path = evidence_dir / "preflight-isolation.json"
    write_json(isolation_path, data)

    tp5_data = tp5_isolation(
        evidence_dir / "preflight-tp5-isolation.json"
    )

    return data, tp5_data
