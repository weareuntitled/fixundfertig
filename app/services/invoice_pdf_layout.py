from __future__ import annotations

from dataclasses import dataclass
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

# ---------------------------------------------------------
# LAYOUT KONFIGURATION
# ---------------------------------------------------------
LAYOUT = {
    "margin_x": 20 * mm,
    "margin_top": 20 * mm,
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


def prefixed_value(prefix: str, value) -> str:
    text = safe_str(value)
    return f"{prefix}{text}" if text else ""


def wrap_text(text: str, font: str, size: int, max_width: float) -> list[str]:
    text = safe_str(text)
    if not text:
        return [""]
    words = text.replace("\n", " ").split()
    lines: list[str] = []
    cur = ""
    for w in words:
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
