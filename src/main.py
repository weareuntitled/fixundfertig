"""Run the FixundFertig NiceGUI app."""

from app import main as app_main
from nicegui import ui


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
