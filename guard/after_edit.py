import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    path = sys.argv[1]
    try:
        result = subprocess.run(["uv", "run", "ruff", "format", path], check=False)
        exit_code = result.returncode
    except OSError:
        exit_code = 127

    receipts = Path(".receipts")
    try:
        receipts.mkdir(exist_ok=True)
        with (receipts / "after-edit.jsonl").open("a", encoding="utf-8") as output:
            output.write(
                json.dumps(
                    {
                        "time": datetime.now(UTC).isoformat(),
                        "path": path,
                        "ruff_exit_code": exit_code,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        return 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
