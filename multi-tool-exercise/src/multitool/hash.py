import hashlib
from pathlib import Path


def _new_digest(algorithm: str) -> hashlib._Hash:
    if algorithm not in {"sha256", "md5"}:
        raise ValueError(f"unknown hash algorithm: {algorithm}")
    return hashlib.new(algorithm, usedforsecurity=False)


def hash_text(algorithm: str, text: str) -> str:
    digest = _new_digest(algorithm)
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def hash_file(algorithm: str, path: str | Path) -> str:
    digest = _new_digest(algorithm)
    with Path(path).open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
