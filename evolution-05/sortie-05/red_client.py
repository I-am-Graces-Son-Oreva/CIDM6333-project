import asyncio
from asyncio import tools

from mcp import ClientSession
from mcp.client.streamable_http import (
    create_mcp_http_client,
    streamable_http_client,
)


async def main():
    headers = {
        "Authorization": "Bearer red-read-token",
        "X-Claimed-Scope": "notes:write",
    }
    
    print("FORGED CLAIM SENT: notes:write")
    print("ACTUAL TOKEN: red-read-token")

    async with create_mcp_http_client(headers=headers) as http_client:
        async with streamable_http_client(
            "http://127.0.0.1:8000/mcp",
            http_client=http_client,
        ) as (read_stream, write_stream):

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:

                await session.initialize()
                tools = await session.list_tools()
                print("AVAILABLE TOOLS:", [tool.name for tool in tools.tools])

                result = await session.call_tool(
                "write_note",
                {
                    "name": "forged-scope-test",
                    "text": "TP3 SHOULD NOT BE WRITTEN",
                },
            )

            print(result)


if __name__ == "__main__":
    asyncio.run(main())