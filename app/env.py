import os
from pathlib import Path


_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    base_dir = Path(__file__).resolve().parent
    candidates = [
        base_dir / ".env",
        base_dir.parent / ".env",
        Path("/app/.env"),
    ]

    loaded_path: Path | None = None
    for path in candidates:
        if not path.exists():
            continue
        loaded_path = path
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("export "):
                stripped = stripped[len("export ") :].lstrip()
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1]
            os.environ[key] = value

    if os.getenv("FF_DEBUG") == "1" and loaded_path is not None:
        print(f"DEBUG: Environment loaded from {loaded_path}")
