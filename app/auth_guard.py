from nicegui import app, ui


def require_auth() -> bool:
    if app.storage.user.get("auth_user"):
        return True
    ui.navigate.to("/login")
    return False


def clear_auth_session() -> None:
    app.storage.user.pop("auth_user", None)
