from __future__ import annotations

import re
from dataclasses import dataclass

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth


def rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


# ---------------------------------------------------------
# SCHRIFTEN: eingebaute PDF-Schriften, wie die Ausweichschrift der Website
# (Neue Haas Grotesk, Helvetica Neue, Helvetica). "medium" hat dort kein eigenes Gewicht.
# ---------------------------------------------------------
FONTS = {"regular": "Helvetica", "medium": "Helvetica-Bold", "bold": "Helvetica-Bold"}


# ---------------------------------------------------------
# LAYOUT KONFIGURATION
# ---------------------------------------------------------
LAYOUT = {
    "margin_x": 16 * mm,
    "margin_top": 15 * mm,
    "margin_bottom": 20 * mm,
    "fs_text": 10,
    "logo_max_w": 45 * mm,
    "logo_max_h": 25 * mm,
    "col_primary": (0, 0, 0),
    # Designwerte der neuen Vorlage
    "col_ink": rgb("#14161a"),
    "col_muted": rgb("#5b606a"),
    "col_hair": rgb("#d9dbdf"),
    "col_surface": rgb("#f4f5f6"),
    "col_accent": rgb("#0f3d3e"),
    "line_width": 1.0,
    "txt_small_biz": "Als Kleinunternehmer im Sinne von § 19 Abs. 1 UStG wird keine Umsatzsteuer berechnet.",
}


@dataclass
class InvItem:
    description: str
    quantity: float
    unit_price: float


def safe_str(x) -> str:
    return (str(x) if x is not None else "").strip()


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_attr(obj, *names, default=""):
    if obj is None:
        return default
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        return default
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v not in (None, ""):
                return v
    return default


_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def format_date(value) -> str:
    """ISO dates become DD.MM.YYYY; anything else is returned as written."""
    text = safe_str(value)
    match = _ISO_DATE.fullmatch(text)
    return f"{match.group(3)}.{match.group(2)}.{match.group(1)}" if match else text


def format_service_period(service_from, service_to) -> str:
    start, end = format_date(service_from), format_date(service_to)
    if start and end and start != end:
        return f"{start} bis {end}"
    return start or end


def format_amount(value: float) -> str:
    """1500 -> '1.500,00'"""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_money(value: float) -> str:
    return f"{format_amount(value)} €"


def group_iban(value) -> str:
    """DE89370400440532013000 -> 'DE89 3704 0044 0532 0130 00'"""
    compact = "".join(safe_str(value).split()).upper()
    return " ".join(compact[i:i + 4] for i in range(0, len(compact), 4))


def prefixed_value(prefix: str, value) -> str:
    text = safe_str(value)
    return f"{prefix}{text}" if text else ""


def wrap_text(text: str, font: str, size: float, max_width: float) -> list[str]:
    text = safe_str(text)
    if not text:
        return [""]
    words = text.replace("\n", " ").split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if stringWidth(w, font, size) > max_width:
            if cur:
                lines.append(cur)
                cur = ""
            for char in w:
                if cur and stringWidth(cur + char, font, size) > max_width:
                    lines.append(cur)
                    cur = ""
                cur += char
            continue
        cand = (cur + " " + w).strip() if cur else w
        if stringWidth(cand, font, size) <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]
