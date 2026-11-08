import asyncio

from issuer import issue_token

from mcp import ClientSession
from mcp.client.streamable_http import (
    create_mcp_http_client,
    streamable_http_client,
)


async def attempt(label, headers, arguments):
    print(f"\n=== TP3 {label} ===")

    try:
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

                    await session.call_tool(
                        "write_note",
                        arguments,
                    )

                    print("FAIL: write_note was not denied")

    except Exception as exc:
        text = str(exc)

        if "403 insufficient_scope" in text:
            print("PASS: 403 insufficient_scope")
        else:
            print("ERROR:", text)


async def main():
    # 1. Forged scope in HTTP header.
    await attempt(
        "FORGED HEADER",
        {
            "Authorization": f"Bearer {issue_token(sub='red-client', scope='notes:read')}",
            "X-Claimed-Scope": "notes:write",
        },
        {
            "name": "tp3-header",
            "text": "SHOULD NOT WRITE",
        },
    )

    # 2. Forged scope in JSON/body-style data.
    await attempt(
        "FORGED BODY",
        {
            "Authorization": f"Bearer {issue_token(sub='red-client', scope='notes:read')}",
            "X-Claimed-Scope-Body": "notes:write",
        },
        {
            "name": "tp3-body",
            "text": "SHOULD NOT WRITE",
        },
    )

    # 3. Forged scope as a tool argument.
    await attempt(
        "FORGED TOOL ARGUMENT",
        {
            "Authorization": f"Bearer {issue_token(sub='red-client', scope='notes:read')}",
        },
        {
            "name": "tp3-argument",
            "text": "SHOULD NOT WRITE",
            "scope": "notes:write",
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
