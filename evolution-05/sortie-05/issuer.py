"""Local signed-token issuer for the E5 Sortie."""

import base64
import hashlib
import hmac
import json
import time

TOKEN_SECRET = b"e5-sortie-local-signing-key"
CANONICAL_AUDIENCE = "http://127.0.0.1:8000/mcp"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def issue_token(
    sub: str,
    scope: str,
    aud: str = CANONICAL_AUDIENCE,
    lifetime: int = 3600,
) -> str:
    """Sign a test token containing sub, aud, scope, and exp."""
    claims = {
        "sub": sub,
        "aud": aud,
        "scope": scope,
        "exp": int(time.time()) + lifetime,
    }

    payload = _b64encode(
        json.dumps(
            claims,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )

    signature = hmac.new(
        TOKEN_SECRET,
        payload.encode(),
        hashlib.sha256,
    ).digest()

    return f"{payload}.{_b64encode(signature)}"


if __name__ == "__main__":
    print(
        issue_token(
            sub="honest-client",
            scope="notes:read",
        )
    )
