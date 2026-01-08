from sqlmodel import select

from data import User, get_session


def login_user(session_storage, user_id: int) -> None:
    session_storage["user_id"] = user_id


def logout_user(session_storage) -> None:
    session_storage.pop("user_id", None)


def get_current_user(session_storage):
    user_id = session_storage.get("user_id")
    if not user_id:
        return None
    with get_session() as session:
        return session.exec(select(User).where(User.id == user_id)).first()
