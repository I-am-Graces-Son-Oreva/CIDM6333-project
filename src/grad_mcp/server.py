"""Evolution 4 MCP server for graduate-application triage."""

import json
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "evolution-04" / "data"
LOG_FILE = ROOT / "evolution-04" / "server.log"

DATA_DIR.mkdir(parents=True, exist_ok=True)

server = FastMCP("grad-triage-e4")


def log_call(client: str, tool: str, **details) -> None:
    event = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "client": client,
        "tool": tool,
        **details,
    }

    with LOG_FILE.open("a") as handle:
        handle.write(json.dumps(event) + "\n")


@server.tool(description="Read a graduate-triage note by name.")
def read_triage_note(name: str, client: str) -> str:
    safe_name = Path(name).name
    log_call(client, "read_triage_note", name=safe_name)

    path = DATA_DIR / f"{safe_name}.txt"

    if not path.exists():
        return f"No triage note named {safe_name}."

    return path.read_text()


@server.tool(description="Write a graduate-triage note by name.")
def write_triage_note(name: str, text: str, client: str) -> str:
    safe_name = Path(name).name
    log_call(client, "write_triage_note", name=safe_name)

    path = DATA_DIR / f"{safe_name}.txt"
    path.write_text(text)

    return f"Wrote triage note {safe_name}."


if __name__ == "__main__":
    server.run()
