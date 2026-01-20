from nicegui import app, ui

from services.auth import is_identifier_allowed


def require_auth() -> bool:
    identifier = app.storage.user.get("auth_user")
    if identifier and is_identifier_allowed(identifier):
        return True
    if identifier:
        app.storage.user.pop("auth_user", None)
    ui.navigate.to("/login")
    return False


def clear_auth_session() -> None:
    app.storage.user.pop("auth_user", None)
