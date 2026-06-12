from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app"
if str(APP_PATH) not in __import__("sys").path:
    __import__("sys").path.append(str(APP_PATH))

shared = importlib.import_module("pages._shared")


def test_shared_module_defines_public_export_list_without_private_names() -> None:
    exports = getattr(shared, "__all__", None)
    assert isinstance(exports, list)
    assert exports
    assert all(not str(name).startswith("_") for name in exports)
