from __future__ import annotations

from nicegui import ui

from composition_root.container import create_app_container


def register_pages(container) -> None:
    _ = container.controller


def main() -> None:
    container = create_app_container()
    register_pages(container)
    storage_secret = getattr(container.controller, "storage_secret", None)

    ui.run(
        title="FixundFertig",
        host="0.0.0.0",
        port=8000,
        language="de",
        storage_secret=storage_secret,
        favicon="🚀",
    )


if __name__ == "__main__":
    main()
