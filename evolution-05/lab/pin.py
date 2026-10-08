"""pin.py - pin tool descriptions by hash. First run writes tool-pins.json; later runs compare."""
import asyncio, hashlib, json, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
PINS = HERE / "tool-pins.json"

async def fetch_tools():
    cmd = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [sys.executable, str(HERE / "notes_server.py")]
    params = StdioServerParameters(command=cmd[0], args=cmd[1:])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return (await s.list_tools()).tools

def digest(tool):
    body = json.dumps({
        "name": tool.name,
        "description": tool.description,
        "schema": getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    }, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:16]

tools = asyncio.run(fetch_tools())
now = {t.name: digest(t) for t in tools}

if not PINS.exists() or "--repin" in sys.argv:
    PINS.write_text(json.dumps(now, indent=2))
    print("PINNED", now)
    sys.exit(0)

pinned = json.loads(PINS.read_text())
bad = 0

for name in sorted(set(now) | set(pinned)):
    ok = now.get(name) == pinned.get(name)
    bad += not ok
    print(f"{'OK ' if ok else 'CHANGED'} {name} pinned={pinned.get(name)} now={now.get(name)}")
    if not ok and name in {t.name for t in tools}:
        print(" description now:", next(t.description for t in tools if t.name == name))

sys.exit(1 if bad else 0)
