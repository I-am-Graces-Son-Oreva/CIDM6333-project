import asyncio
from unittest import result

from mcp import ClientSession
from mcp.client.streamable_http import (
    create_mcp_http_client,
    streamable_http_client,
)


async def main():
    headers = {
        "Authorization": "Bearer honest-read-token"
    }

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

                result = await session.read_resource("note://poisoned")

                print("POISONED RESOURCE READ:")
                print(result)


if __name__ == "__main__":
    asyncio.run(main())