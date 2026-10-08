"""notes_server.py - a two-tool MCP server for the E5 tool-poisoning lab (stdio)."""
import json, os, sys, time
from pathlib import Path

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:  # MCP Python SDK 1.x
    from mcp.server.fastmcp import FastMCP as Server

HERE = Path(__file__).resolve().parent
NOTES = HERE / "notes"
LOG = HERE / "calls.log"
NOTES.mkdir(exist_ok=True)

server = Server("notes")

def log(tool, **args):
    with LOG.open("a") as f:
        f.write(json.dumps({"t": time.strftime("%H:%M:%S"), "tool": tool, **args}) + "\n")

READ_DESC = "Read one note from the notes folder and return its text."

@server.tool(description=READ_DESC)
def read_note(name: str) -> str:
    log("read_note", name=name)
    path = NOTES / f"{Path(name).name}.md"
    return path.read_text() if path.exists() else f"No note named {name}."

@server.tool(description="Write a note (creates or overwrites notes/<name>.md).")
def write_note(name: str, text: str) -> str:
    log("write_note", name=name, text=text[:80])
    (NOTES / f"{Path(name).name}.md").write_text(text)
    return f"Wrote {name}."

if __name__ == "__main__":
    server.run()  # stdio by default
