import tempfile
from pathlib import Path

from .conditions import (
    EVIDENCE_LABEL,
    QUESTION_ABSENT,
    QUESTION_CONTROL,
    QUESTION_RECALL,
    build_off_sandbox,
    build_on_sandbox,
    isolation_probes,
    probes_ok,
    run_wrapper,
    sha256_text,
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
        off_manifest = build_off_sandbox(temp / "off")
        on_manifest = build_on_sandbox(temp / "on", temp / "private")

        off_probes = isolation_probes(
            temp / "off",
            temp / "off" / "sandbox.sb",
        )
        recall_result = run_wrapper(temp / "on", QUESTION_RECALL)
        control_result = run_wrapper(temp / "on", QUESTION_CONTROL)
        absent_result = run_wrapper(temp / "on", QUESTION_ABSENT)

        on_probes = isolation_probes(
            temp / "on",
            temp / "on" / "sandbox.sb",
            extra_denied=[
                ("private_store", on_manifest["fixture_store"]),
                ("private_ledger", on_manifest["fixture_ledger"]),
                ("private_sidecar", on_manifest["sidecar"]),
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
            },
        }

    isolation_path = evidence_dir / "preflight-isolation.json"
    write_json(isolation_path, data)

    tp5_data = tp5_isolation(
        evidence_dir / "preflight-tp5-isolation.json"
    )

    return data, tp5_data
