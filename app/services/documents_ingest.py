from __future__ import annotations

import hashlib
from pathlib import Path


def save_upload_bytes(destination: str | Path, data: bytes) -> tuple[str, int]:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    return sha, len(data)
