from __future__ import annotations

import os
from pathlib import Path


_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    base_dir = Path(__file__).resolve().parent
    # Prefer project root .env so credentials in fixundfertig/.env are used (not only app/.env).
    candidates = [
        base_dir.parent / ".env",
        base_dir / ".env",
        Path("/app/.env"),
    ]

    loaded_path: Path | None = None
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:  # pragma: no cover - fallback for minimal environments
        load_dotenv = None  # type: ignore[assignment]

    for path in candidates:
        if not path.exists():
            continue
        loaded_path = path
        if load_dotenv is not None:
            # Do not override real environment variables by default (Docker/K8s should win).
            load_dotenv(dotenv_path=path, override=False)
        else:
            # Fallback parser (keeps old behavior if python-dotenv is missing).
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
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                os.environ.setdefault(key, value)

    if os.getenv("FF_DEBUG") == "1" and loaded_path is not None:
        print(f"DEBUG: Environment loaded from {loaded_path}")
