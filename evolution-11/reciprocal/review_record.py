"""Verify a synthetic evidence record and print its verdict."""

import hashlib
import json
import sys
from pathlib import Path


def verdict(record: object) -> dict[str, str]:
    if not isinstance(record, dict):
        return {"status": "BLOCKED", "reason": "INCOMPLETE_EVIDENCE"}
    if any(not isinstance(record.get(key), str) or not record[key].strip()
           for key in ("source", "evidence", "sha256")):
        return {"status": "BLOCKED", "reason": "INCOMPLETE_EVIDENCE"}
    actual = hashlib.sha256(record["evidence"].encode("utf-8")).hexdigest()
    if record["sha256"] != actual:
        return {"status": "BLOCKED", "reason": "CONTRADICTORY_EVIDENCE"}
    return {"status": "ACCEPTED", "reason": "EVIDENCE_CONSISTENT"}


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        print(json.dumps({"status": "BLOCKED", "reason": "INVALID_INPUT"}))
        return 1
    result = verdict(record)
    print(json.dumps(result))
    return int(result["status"] == "BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
