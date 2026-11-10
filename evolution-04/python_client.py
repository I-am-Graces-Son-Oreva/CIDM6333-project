"""Second MCP client for Evolution 4."""

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.grad_mcp.server"],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]

            print("CLIENT=python-client")
            print("TOOLS=", names)

            result = await session.call_tool(
                "read_triage_note",
                {
                    "name": "demo",
                    "client": "python-client",
                },
            )

            print("READ_RESULT=", result.content)


if __name__ == "__main__":
    asyncio.run(main())
