"""Run the FixundFertig NiceGUI app."""

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent.parent
_APP_ROOT = _ROOT / "app"
for path in (_ROOT, _APP_ROOT):
    if str(path) not in sys.path:
        sys.path.append(str(path))

from app import main as app_main
from nicegui import ui

app = app_main.app


def run() -> None:
    ui.run(
        title="FixundFertig",
        host="0.0.0.0",
        port=8000,
        language="de",
        storage_secret=app_main.storage_secret,
        favicon="🚀",
    )


if __name__ == "__main__":
    run()
