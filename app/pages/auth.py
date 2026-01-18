from __future__ import annotations

from contextlib import contextmanager
import logging

from nicegui import app, ui
from starlette.requests import Request

from services.auth import (
    create_user_pending,
    login_user,
    request_password_reset,
    reset_password,
    verify_email,
    verify_password,
)

ERROR_TEXT = "text-sm text-rose-600"
LINK_TEXT = "text-sm text-slate-500 hover:text-slate-900 no-underline"
TITLE_TEXT = "text-2xl font-semibold text-slate-900 text-center"
SUBTITLE_TEXT = "text-sm text-slate-500 text-center"
INPUT_CLASSES = "w-full"
PRIMARY_BUTTON = "w-full bg-slate-900 text-white rounded-lg hover:bg-slate-800"
CARD_CLASSES = "w-full max-w-[400px] bg-white rounded-xl shadow-lg border border-slate-200 p-6"
BG_CLASSES = "min-h-screen w-full bg-slate-50 flex items-center justify-center px-4"
logger = logging.getLogger(__name__)


@contextmanager
def auth_layout(title: str, subtitle: str):
    with ui.element("div").classes(BG_CLASSES):
        with ui.column().classes("w-full items-center gap-6"):
            ui.label("FixundFertig").classes("text-lg font-semibold text-slate-900")
            with ui.column().classes(f"{CARD_CLASSES} gap-4"):
                ui.label(title).classes(TITLE_TEXT)
                if subtitle:
                    ui.label(subtitle).classes(SUBTITLE_TEXT)
                with ui.column().classes("w-full gap-4") as card:
                    yield card


def _error_label() -> ui.label:
    label = ui.label("").classes(ERROR_TEXT)
    label.set_visibility(False)
    return label


def _set_error(label: ui.label, message: str) -> None:
    label.text = message
    label.set_visibility(bool(message))


def _show_success(
    card: ui.column,
    message: str,
    link_text: str | None = None,
    link_href: str | None = None,
    icon: str | None = None,
) -> None:
    card.clear()
    with card:
        if icon:
            ui.icon(icon).classes("text-emerald-500 text-4xl self-center")
        ui.label(message).classes("text-sm text-slate-500 text-center")
        if link_text and link_href:
            ui.link(link_text, link_href).classes(f"{LINK_TEXT} self-center")


def _mask_token_prefix(token: str | None, visible: int = 6) -> str:
    if not token:
        return ""
    token_str = str(token)
    if len(token_str) <= visible:
        return "***"
    return f"{token_str[:visible]}..."


@ui.page("/login")
def login_page():
    with auth_layout("Welcome back", "Sign in to your account") as card:
        with ui.column().classes("w-full gap-1"):
            identifier_input = ui.input("Email or username").props("outlined dense").classes(INPUT_CLASSES)
            identifier_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            password_input = ui.input("Password").props("outlined dense type=password").classes(INPUT_CLASSES)
            password_error = _error_label()
        status_error = _error_label()

        def handle_login() -> None:
            _set_error(identifier_error, "")
            _set_error(password_error, "")
            _set_error(status_error, "")
            identifier = (identifier_input.value or "").strip()
            password = password_input.value or ""
            if not identifier:
                _set_error(identifier_error, "Email or username is required")
            if not password:
                _set_error(password_error, "Password is required")
            if not identifier or not password:
                return
            login_button.loading = True
            try:
                if not verify_password(identifier, password):
                    _set_error(status_error, "Invalid credentials")
                    return
                if login_user(identifier):
                    app.storage.user["auth_user"] = identifier
                    app.storage.user["page"] = "dashboard"
                    ui.navigate.to("/")
                else:
                    _set_error(status_error, "Please verify your email before logging in.")
            finally:
                login_button.loading = False

        login_button = ui.button("Log in", on_click=handle_login).props("loading=false").classes(PRIMARY_BUTTON)
        with ui.row().classes("w-full justify-between"):
            ui.link("Forgot password?", "/forgot").classes(LINK_TEXT)
            ui.link("Create account", "/signup").classes(LINK_TEXT)


@ui.page("/signup")
def signup_page():
    with auth_layout("Create account", "Start with your email and a password") as card:
        with ui.column().classes("w-full gap-1"):
            email_input = ui.input("Email").props("outlined dense").classes(INPUT_CLASSES)
            email_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            username_input = ui.input("Username (optional)").props("outlined dense").classes(INPUT_CLASSES)
            username_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            password_input = ui.input("Password").props("outlined dense type=password").classes(INPUT_CLASSES)
            password_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            confirm_input = ui.input("Confirm password").props("outlined dense type=password").classes(INPUT_CLASSES)
            confirm_error = _error_label()
        status_error = _error_label()

        def handle_signup() -> None:
            _set_error(email_error, "")
            _set_error(username_error, "")
            _set_error(password_error, "")
            _set_error(confirm_error, "")
            _set_error(status_error, "")
            email = (email_input.value or "").strip()
            username = (username_input.value or "").strip()
            password = password_input.value or ""
            confirm = confirm_input.value or ""
            if not email:
                _set_error(email_error, "Email is required")
            if not password:
                _set_error(password_error, "Password is required")
            if password and confirm != password:
                _set_error(confirm_error, "Passwords do not match")
            if not email or not password or (password and confirm != password):
                return
            signup_button.loading = True
            try:
                try:
                    _, _, token = create_user_pending(email, username, password)
                except Exception as exc:
                    logger.warning(
                        "signup.failed",
                        exc_info=exc,
                        extra={
                            "email": email,
                            "username": username or None,
                            "token": _mask_token_prefix(None),
                        },
                    )
                    _set_error(status_error, str(exc))
                    return
                logger.info(
                    "signup.success",
                    extra={
                        "email": email,
                        "username": username or None,
                        "token": _mask_token_prefix(token),
                    },
                )
                if token:
                    message = "Account created. Please check your email to verify your account."
                else:
                    message = "Account created. You can now log in."
                _show_success(card, message, "Go to login", "/login")
            finally:
                signup_button.loading = False

        signup_button = ui.button("Create account", on_click=handle_signup).props("loading=false").classes(
            PRIMARY_BUTTON
        )
        with ui.row().classes("w-full justify-between"):
            ui.link("Already have an account?", "/login").classes(LINK_TEXT)


@ui.page("/verify")
def verify_page(request: Request):
    token_prefill = (request.query_params.get("token") or "").strip()
    with auth_layout("Verify your email", "Enter the verification token") as card:
        with ui.column().classes("w-full gap-1"):
            token_input = ui.input("Verification token", value=token_prefill).props("outlined dense").classes(
                INPUT_CLASSES
            )
            token_error = _error_label()
        status_error = _error_label()

        def handle_verify() -> None:
            _set_error(token_error, "")
            _set_error(status_error, "")
            token = (token_input.value or "").strip()
            if not token:
                _set_error(token_error, "Verification token is required")
                return
            if verify_email(token):
                _show_success(card, "Email verified. Redirecting to login...", icon="check_circle")
                ui.timer(2.0, lambda: ui.navigate.to("/login"), once=True)
            else:
                _set_error(status_error, "Invalid or expired token")

        ui.button("Verify email", on_click=handle_verify).classes(PRIMARY_BUTTON)
        ui.link("Back to login", "/login").classes(LINK_TEXT)


@ui.page("/forgot")
def forgot_page():
    with auth_layout("Forgot password", "We will email you a reset link") as card:
        with ui.column().classes("w-full gap-1"):
            email_input = ui.input("Email").props("outlined dense").classes(INPUT_CLASSES)
            email_error = _error_label()

        def handle_request() -> None:
            _set_error(email_error, "")
            email = (email_input.value or "").strip()
            if not email:
                _set_error(email_error, "Email is required")
                return
            request_password_reset(email)
            _show_success(
                card,
                "If an account exists for this email, a reset link is on the way.",
                "Return to login",
                "/login",
            )

        ui.button("Send reset link", on_click=handle_request).classes(PRIMARY_BUTTON)
        ui.link("Back to login", "/login").classes(LINK_TEXT)


@ui.page("/reset")
def reset_page(request: Request):
    token_prefill = (request.query_params.get("token") or "").strip()
    with auth_layout("Reset password", "Enter your token and choose a new password") as card:
        with ui.column().classes("w-full gap-1"):
            token_input = ui.input("Reset token", value=token_prefill).props("outlined dense").classes(INPUT_CLASSES)
            token_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            password_input = ui.input("New password").props("outlined dense type=password").classes(INPUT_CLASSES)
            password_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            confirm_input = ui.input("Confirm password").props("outlined dense type=password").classes(INPUT_CLASSES)
            confirm_error = _error_label()
        status_error = _error_label()

        def handle_reset() -> None:
            _set_error(token_error, "")
            _set_error(password_error, "")
            _set_error(confirm_error, "")
            _set_error(status_error, "")
            token = (token_input.value or "").strip()
            password = password_input.value or ""
            confirm = confirm_input.value or ""
            if not token:
                _set_error(token_error, "Reset token is required")
            if not password:
                _set_error(password_error, "Password is required")
            if password and confirm != password:
                _set_error(confirm_error, "Passwords do not match")
            if not token or not password or (password and confirm != password):
                return
            if reset_password(token, password):
                _show_success(card, "Password updated. You can now log in.", "Go to login", "/login")
            else:
                _set_error(status_error, "Invalid or expired token")

        ui.button("Reset password", on_click=handle_reset).classes(PRIMARY_BUTTON)
        ui.link("Back to login", "/login").classes(LINK_TEXT)
