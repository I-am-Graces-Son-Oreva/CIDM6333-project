"""TP0 - verify the MCP tool/scope security contract."""

import json
from pathlib import Path

from scopes import TOOL_SCOPES


HERE = Path(__file__).resolve().parent
PIN_FILE = HERE / "tool-pins.json"


def main():
    expected = json.loads(PIN_FILE.read_text())

    actual = {
        tool: {"required_scope": scope}
        for tool, scope in TOOL_SCOPES.items()
    }

    print("=== TP0 TOOL PIN CHECK ===")
    print("Expected:", expected)
    print("Actual:  ", actual)

    if actual != expected:
        print("TP0 FAIL: tool/scope contract changed")
        raise SystemExit(1)

    print("TP0 PASS: tool/scope contract matches pinned configuration")


if __name__ == "__main__":
    main()
