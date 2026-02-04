from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
import sys

@dataclass(frozen=True)
class AppContainer:
    repo: ModuleType
    commands: ModuleType
    queries: ModuleType
    controller: ModuleType


def _find_app_root() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [repo_root / "app", repo_root]
    for candidate in candidates:
        if (candidate / "main.py").exists() and (candidate / "pages").exists():
            return candidate
    return repo_root


def _ensure_app_path() -> Path:
    app_root = _find_app_root()
    app_root_str = str(app_root)
    if app_root_str not in sys.path:
        sys.path.insert(0, app_root_str)
    return app_root


def create_app_container() -> AppContainer:
    _ensure_app_path()
    import data
    import logic
    from pages import _shared as queries
    import main as controller

    return AppContainer(
        repo=data,
        commands=logic,
        queries=queries,
        controller=controller,
    )
