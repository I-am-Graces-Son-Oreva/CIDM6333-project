import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = Path.home() / "CIDM6333-private-e7" / "private-claim.json"


def load_fixture(path=FIXTURE_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_fixture_store(store_path, fixture=None):
    fixture = fixture or load_fixture()

    record = {
        "id": fixture["id"],
        "kind": fixture["kind"],
        "source": fixture["source"],
        "written": fixture["written"],
        "written_by": fixture["written_by"],
        "retain_until": fixture["retain_until"],
        "supersedes": fixture["supersedes"],
        "text": fixture["text"],
    }

    store_path = Path(store_path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return record


def claim_text(fixture=None):
    return (fixture or load_fixture())["text"]


def claim_hash(fixture=None):
    return hashlib.sha256(claim_text(fixture).encode("utf-8")).hexdigest()
