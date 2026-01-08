from passlib.context import CryptContext


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _ensure_min_length(plain: str) -> None:
    if len(plain) < 10:
        raise ValueError("Password must be at least 10 characters long.")


def hash_password(plain: str) -> str:
    _ensure_min_length(plain)
    return _pwd_context.hash(plain)


def verify_password(plain: str, hash: str) -> bool:
    _ensure_min_length(plain)
    return _pwd_context.verify(plain, hash)
