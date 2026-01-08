from nicegui import ui

from services.auth import (
    create_user_pending,
    create_verify_email_token,
    login_user,
    request_password_reset,
    reset_password,
    verify_email,
    verify_password,
)


@ui.page("/auth/test_signup")
def test_signup_page():
    ui.label("Test Signup")
    email_input = ui.input("Email")
    username_input = ui.input("Username")
    password_input = ui.input("Password").props("type=password")
    result = ui.label("")

    def handle_signup() -> None:
        try:
            user_id, email_value, token_str = create_user_pending(
                email_input.value,
                username_input.value,
                password_input.value,
            )
            if token_str:
                result.text = f"Verification token for {email_value} (id {user_id}): {token_str}"
            else:
                result.text = f"User {email_value} (id {user_id}) created without email verification"
        except Exception as exc:
            result.text = f"Error: {exc}"

    ui.button("Create user", on_click=handle_signup)


@ui.page("/auth/test_verify")
def test_verify_page():
    ui.label("Test Verify Email")
    token_input = ui.input("Token")
    result = ui.label("")

    def handle_verify() -> None:
        if verify_email(token_input.value or ""):
            result.text = "Email verified"
        else:
            result.text = "Invalid token"

    ui.button("Verify", on_click=handle_verify)


@ui.page("/auth/test_login")
def test_login_page():
    ui.label("Test Login")
    email_input = ui.input("Email")
    password_input = ui.input("Password").props("type=password")
    result = ui.label("")

    def handle_login() -> None:
        if not verify_password(email_input.value, password_input.value):
            result.text = "Invalid credentials"
            return
        if login_user(email_input.value):
            result.text = "Logged in"
        else:
            result.text = "Email verification required"

    ui.button("Login", on_click=handle_login)


@ui.page("/auth/test_reset_request")
def test_reset_request_page():
    ui.label("Test Reset Request")
    email_input = ui.input("Email")
    result = ui.label("")

    def handle_request() -> None:
        request_password_reset(email_input.value)
        result.text = "If the user exists, a reset token was created"

    ui.button("Request reset", on_click=handle_request)


@ui.page("/auth/test_reset_confirm")
def test_reset_confirm_page():
    ui.label("Test Reset Confirm")
    token_input = ui.input("Token")
    password_input = ui.input("New password").props("type=password")
    result = ui.label("")

    def handle_reset() -> None:
        if reset_password(token_input.value or "", password_input.value or ""):
            result.text = "Password reset"
        else:
            result.text = "Invalid token"

    ui.button("Reset password", on_click=handle_reset)
