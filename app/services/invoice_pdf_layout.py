from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


def rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


# ---------------------------------------------------------
# SCHRIFTEN: IBM Plex gebündelt, Rückfall auf die eingebauten PDF-Schriften
# ---------------------------------------------------------
FONT_DIR = Path(__file__).resolve().parent / "fonts"

FONT_FILES = {
    "regular": "IBMPlexSans-Regular.ttf",
    "medium": "IBMPlexSans-Medium.ttf",
    "bold": "IBMPlexSans-SemiBold.ttf",
    "mono": "IBMPlexMono-Regular.ttf",
    "mono_medium": "IBMPlexMono-Medium.ttf",
}
FONT_FALLBACK = {
    "regular": "Helvetica",
    "medium": "Helvetica",
    "bold": "Helvetica-Bold",
    "mono": "Courier",
    "mono_medium": "Courier-Bold",
}


def load_fonts() -> dict[str, str]:
    """Font names per role; a missing or unreadable file falls back to a built-in font."""
    names: dict[str, str] = {}
    for role, filename in FONT_FILES.items():
        path = FONT_DIR / filename
        name = f"{path.stem}@{abs(hash(str(path))):x}"
        if name not in pdfmetrics.getRegisteredFontNames():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
            except Exception as exc:
                logger.warning("Invoice font %s unavailable, using %s: %s", path, FONT_FALLBACK[role], exc)
                name = FONT_FALLBACK[role]
        names[role] = name
    return names

# ---------------------------------------------------------
# LAYOUT KONFIGURATION
# ---------------------------------------------------------
LAYOUT = {
    "margin_x": 16 * mm,
    "margin_top": 15 * mm,
    "margin_bottom": 20 * mm,
    "font_reg": "Helvetica",
    "font_bold": "Helvetica-Bold",
    "fs_title": 16,
    "fs_text": 10,
    "fs_small": 8,
    "pos_address": 10 * mm,
    "pos_info": 40 * mm,
    "header_to_rec_gap_mm": 8,
    "header_left_w": 60 * mm,
    "header_gap": 10 * mm,
    "logo_max_w": 45 * mm,
    "logo_max_h": 25 * mm,
    "header_baseline_offset": 2 * mm,
    "header_title_leading": 6 * mm,
    "header_sub_leading": 4.5 * mm,
    "header_meta_gap": 6 * mm,
    "col_primary": (0, 0, 0),
    "col_line": (0.0, 0.0, 0.0),
    "col_header_bg": (1.0, 1.0, 1.0),
    # Designwerte der neuen Vorlage
    "col_ink": rgb("#14161a"),
    "col_muted": rgb("#5b606a"),
    "col_hair": rgb("#d9dbdf"),
    "col_surface": rgb("#f4f5f6"),
    "col_accent": rgb("#0f3d3e"),
    "line_width": 1.0,
    "recipient_leading_pt": 12,
    "meta_col_w_mm": 70,
    "txt_small_biz": "Als Kleinunternehmer im Sinne von § 19 Abs. 1 UStG wird keine Umsatzsteuer berechnet.",
    "col_w_desc": 0.50,
    "col_w_qty": 0.15,
    "col_w_price": 0.30,
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
