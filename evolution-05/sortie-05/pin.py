"""Verify the scope and literal description of each registered MCP tool."""

import ast
import hashlib
import json
from pathlib import Path

from scopes import TOOL_SCOPES

HERE = Path(__file__).resolve().parent
PIN_FILE = HERE / "tool-pins.json"


def declaration_pins(path):
    declarations = {}
    for node in ast.parse(path.read_text()).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for item in node.decorator_list:
            if not isinstance(item, ast.Call) or ast.unparse(item.func) != "server.tool":
                continue
            labels = [field.value for field in item.keywords if field.arg == "description"]
            if len(labels) != 1 or node.name in declarations:
                raise ValueError(f"unstable description declaration: {node.name}")
            description = ast.literal_eval(labels[0])
            if not isinstance(description, str) or not description:
                raise ValueError(f"invalid description: {node.name}")
            declarations[node.name] = hashlib.sha256(description.encode()).hexdigest()
    if declarations.keys() != TOOL_SCOPES.keys():
        raise ValueError("declared tools and scope table differ")
    return {
        tool: {"required_scope": scope, "description_sha256": declarations[tool]}
        for tool, scope in TOOL_SCOPES.items()
    }


def main():
    expected = json.loads(PIN_FILE.read_text())
    actual = declaration_pins(HERE / "server.py")
    changed = sorted(tool for tool in expected.keys() | actual.keys() if expected.get(tool) != actual.get(tool))
    if changed:
        print("TP0 FAIL: tool declaration pins changed:", ", ".join(changed))
        return 1
    print("TP0 PASS: scope and description pins match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
