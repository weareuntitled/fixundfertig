import threading
from typing import Optional, Tuple

_MIN_IBAN_LENGTH = 15
_MAX_IBAN_LENGTH = 34
_LOOKUP_TIMEOUT_SECONDS = 2.0

_cache_lock = threading.Lock()
_cache: dict[str, Tuple[Optional[str], Optional[str]]] = {}


def normalize_iban(iban: str) -> str:
    if iban is None:
        raise ValueError("IBAN is required")
    normalized = "".join(iban.split()).upper()
    length = len(normalized)
    if length < _MIN_IBAN_LENGTH or length > _MAX_IBAN_LENGTH:
        raise ValueError("IBAN length is invalid")
    return normalized


def _external_lookup(_iban: str, *, timeout: float) -> Tuple[Optional[str], Optional[str]]:
    """Placeholder for future external lookup implementation."""
    _ = timeout
    return None, None


def lookup_bank_from_iban(iban: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (bic, bank_name) or (None, None) without raising on failure."""
    try:
        normalized = normalize_iban(iban)
    except (TypeError, ValueError):
        return None, None

    with _cache_lock:
        cached = _cache.get(normalized)
    if cached is not None:
        return cached

    try:
        result = _external_lookup(normalized, timeout=_LOOKUP_TIMEOUT_SECONDS)
    except Exception:
        result = None, None

    with _cache_lock:
        _cache[normalized] = result

    return result
