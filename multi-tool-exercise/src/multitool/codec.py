import base64
import codecs


def encode(scheme: str, text: str) -> str:
    if scheme == "rot13":
        return codecs.encode(text, "rot_13")
    if scheme == "base64":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    if scheme == "hex":
        return text.encode("utf-8").hex()
    raise ValueError(f"unknown codec scheme: {scheme}")


def decode(scheme: str, text: str) -> str:
    if scheme == "rot13":
        return codecs.decode(text, "rot_13")
    if scheme == "base64":
        return base64.b64decode(text, validate=True).decode("utf-8")
    if scheme == "hex":
        return bytes.fromhex(text).decode("utf-8")
    raise ValueError(f"unknown codec scheme: {scheme}")
