from __future__ import annotations

from contextlib import contextmanager

from nicegui import app, ui

from services.auth import (
    create_user_pending,
    login_user,
    request_password_reset,
    reset_password,
    verify_email,
    verify_password,
)
from styles import C_BG, C_BTN_PRIM, C_CARD, C_CONTAINER, C_INPUT, C_PAGE_TITLE

ERROR_TEXT = "text-sm text-rose-600"
LINK_TEXT = "text-sm text-blue-600 hover:text-blue-700"


@contextmanager
def auth_shell(title: str, subtitle: str):
    with ui.element("div").classes(C_BG + " w-full"):
        with ui.column().classes(C_CONTAINER + " items-center"):
            with ui.column().classes("w-full max-w-md gap-4"):
                ui.label(title).classes(C_PAGE_TITLE + " text-center")
                if subtitle:
                    ui.label(subtitle).classes("text-sm text-slate-500 text-center")
                card = ui.column().classes(C_CARD + " w-full p-6 gap-4")
                with card:
                    yield card


def _error_label() -> ui.label:
    label = ui.label("").classes(ERROR_TEXT)
    label.set_visibility(False)
    return label


def _set_error(label: ui.label, message: str) -> None:
    label.text = message
    label.set_visibility(bool(message))


def _show_success(card: ui.column, message: str, link_text: str | None = None, link_href: str | None = None) -> None:
    card.clear()
    with card:
        ui.label(message).classes("text-sm text-slate-600")
        if link_text and link_href:
            ui.link(link_text, link_href).classes(LINK_TEXT)


@ui.page("/login")
def login_page():
    with auth_shell("Welcome back", "Sign in to your account") as card:
        with ui.column().classes("w-full gap-1"):
            identifier_input = ui.input("Email or username").classes(C_INPUT)
            identifier_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            password_input = ui.input("Password").props("type=password").classes(C_INPUT)
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
            if not verify_password(identifier, password):
                _set_error(status_error, "Invalid credentials")
                return
            if login_user(identifier):
                app.storage.user["auth_user"] = identifier
                _show_success(card, "Logged in successfully.", "Go to dashboard", "/")
            else:
                _set_error(status_error, "Login failed")

        ui.button("Log in", on_click=handle_login).classes(C_BTN_PRIM + " w-full")
        with ui.row().classes("w-full justify-between"):
            ui.link("Forgot password?", "/forgot").classes(LINK_TEXT)
            ui.link("Create account", "/signup").classes(LINK_TEXT)


@ui.page("/signup")
def signup_page():
    with auth_shell("Create account", "Start with your email and a password") as card:
        with ui.column().classes("w-full gap-1"):
            email_input = ui.input("Email").classes(C_INPUT)
            email_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            username_input = ui.input("Username (optional)").classes(C_INPUT)
            username_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            password_input = ui.input("Password").props("type=password").classes(C_INPUT)
            password_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            confirm_input = ui.input("Confirm password").props("type=password").classes(C_INPUT)
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
            try:
                _, _, _ = create_user_pending(email, username, password)
            except Exception as exc:
                _set_error(status_error, str(exc))
                return
            _show_success(card, "Account created. Please check your email to verify your account.", "Go to login", "/login")

        ui.button("Create account", on_click=handle_signup).classes(C_BTN_PRIM + " w-full")
        with ui.row().classes("w-full justify-between"):
            ui.link("Already have an account?", "/login").classes(LINK_TEXT)


@ui.page("/verify")
def verify_page(request):
    token_prefill = (request.query.get("token") or "").strip()
    with auth_shell("Verify your email", "Enter the verification token") as card:
        with ui.column().classes("w-full gap-1"):
            token_input = ui.input("Verification token", value=token_prefill).classes(C_INPUT)
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
                _show_success(card, "Email verified. You can now log in.", "Go to login", "/login")
            else:
                _set_error(status_error, "Invalid or expired token")

        ui.button("Verify email", on_click=handle_verify).classes(C_BTN_PRIM + " w-full")
        ui.link("Back to login", "/login").classes(LINK_TEXT)


@ui.page("/forgot")
def forgot_page():
    with auth_shell("Forgot password", "We will email you a reset link") as card:
        with ui.column().classes("w-full gap-1"):
            email_input = ui.input("Email").classes(C_INPUT)
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

        ui.button("Send reset link", on_click=handle_request).classes(C_BTN_PRIM + " w-full")
        ui.link("Back to login", "/login").classes(LINK_TEXT)


@ui.page("/reset")
def reset_page(request):
    token_prefill = (request.query.get("token") or "").strip()
    with auth_shell("Reset password", "Enter your token and choose a new password") as card:
        with ui.column().classes("w-full gap-1"):
            token_input = ui.input("Reset token", value=token_prefill).classes(C_INPUT)
            token_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            password_input = ui.input("New password").props("type=password").classes(C_INPUT)
            password_error = _error_label()
        with ui.column().classes("w-full gap-1"):
            confirm_input = ui.input("Confirm password").props("type=password").classes(C_INPUT)
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

        ui.button("Reset password", on_click=handle_reset).classes(C_BTN_PRIM + " w-full")
        ui.link("Back to login", "/login").classes(LINK_TEXT)
