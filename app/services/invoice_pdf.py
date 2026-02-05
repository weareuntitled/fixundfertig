# app/services/invoice_pdf.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
import os
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors

from services.storage import company_logo_path

# ---------------------------------------------------------
# HIER KANNST DU ALLES EINSTELLEN (DESIGN & LAYOUT)
# ---------------------------------------------------------
LAYOUT = {
    # Ränder
    "margin_x": 20 * mm,       # Rand links/rechts
    "margin_top": 20 * mm,     # Rand oben
    "margin_bottom": 20 * mm,  # Rand unten

    # Schriftarten
    "font_reg": "Helvetica",
    "font_bold": "Helvetica-Bold",
    
    # Schriftgrößen
    "fs_title": 16,     # Größe "Rechnung"
    "fs_text": 10,      # Normaler Text
    "fs_small": 8,      # Kleingedrucktes (Footer)

    # Positionen (von oben gemessen)
    "pos_address": 10 * mm,    # Wo fängt das Adressfeld an? (Ideal für Fensterkuvert)
    "pos_info": 40 * mm,       # Wo fängt der Datumsblock rechts an? (1 cm höher)

    # Header layout (Logo links, Titel rechts)
    "header_left_w": 60 * mm,          # reservierte Breite links für Logo/Firmenname
    "header_gap": 10 * mm,             # Abstand zwischen linker und rechter Header-Spalte
    "logo_max_w": 45 * mm,             # maximale Logobreite
    "logo_max_h": 25 * mm,             # maximale Logohöhe
    "header_baseline_offset": 2 * mm,  # Baseline-Abstand unterhalb des oberen Rands
    "header_title_leading": 6 * mm,    # Zeilenhöhe für den Titel
    "header_sub_leading": 4.5 * mm,    # Zeilenhöhe für Unterzeilen (z.B. Nr.)
    "header_meta_gap": 6 * mm,         # Mindestabstand zwischen Header und Metadaten

    # Farben (RGB: 0.0 bis 1.0)
    "col_primary": (0, 0, 0),        # Hauptfarbe Text (Schwarz)
    "col_line": (0.0, 0.0, 0.0),     # Farbe der Trennlinien (Schwarz)
    "col_header_bg": (1.0, 1.0, 1.0), # Hintergrund Tabellenkopf (Weiß)
    "line_width": 1.0,               # Linienbreite

    # Texte
    "txt_small_biz": "Als Kleinunternehmer im Sinne von § 19 Abs. 1 UStG wird keine Umsatzsteuer berechnet.",
    
    # Tabellenspalten (Prozent der Breite, Summe ca. 1.0)
    "col_w_desc": 0.50,
    "col_w_qty": 0.15,
    "col_w_price": 0.30
}
# ---------------------------------------------------------

def _safe_str(x: Any) -> str:
    return (str(x) if x is not None else "").strip()

def _wrap_text(text: str, font: str, size: int, max_width: float) -> list[str]:
    text = _safe_str(text)
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

def _get(obj: Any, *names: str, default: Any = "") -> Any:
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

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _prefixed_value(prefix: str, value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    return f"{prefix}{text}"

@dataclass
class _InvItem:
    description: str
    quantity: float
    unit_price: float

def render_invoice_to_pdf_bytes(invoice, company=None, customer=None) -> bytes:
    """
    Funktioniert exakt wie vorher, nutzt aber die LAYOUT Konfiguration oben.
    """
    
    # 1. DATEN HOLEN
    comp = company or _get(invoice, "company", default=None) or getattr(invoice, "__dict__", {}).get("company", None)
    if customer is None:
        customer = _get(invoice, "customer", default=None)

    # Recipient
    rec_name = _safe_str(_get(invoice, "recipient_name", "address_name", default=""))
    rec_street = _safe_str(_get(invoice, "recipient_street", "address_street", default=""))
    rec_zip = _safe_str(_get(invoice, "recipient_postal_code", "address_zip", default=""))
    rec_city = _safe_str(_get(invoice, "recipient_city", "address_city", default=""))
    rec_country = _safe_str(_get(invoice, "recipient_country", "address_country", default=""))

    if (not rec_name) and customer is not None:
        rec_name = _safe_str(_get(customer, "recipient_name", "display_name", "name", default=""))
        rec_street = _safe_str(_get(customer, "recipient_street", "strasse", default=""))
        rec_zip = _safe_str(_get(customer, "recipient_postal_code", "plz", default=""))
        rec_city = _safe_str(_get(customer, "recipient_city", "ort", default=""))
        rec_country = _safe_str(_get(customer, "country", default=""))

    # Items
    raw_items = _get(invoice, "line_items", "items", "positions", default=None)
    if raw_items is None:
        raw_items = getattr(invoice, "__dict__", {}).get("line_items", None)
    
    items: list[_InvItem] = []
    # Fallback für SQLModel Relations vs Dicts
    item_iter = raw_items if isinstance(raw_items, list) else (getattr(invoice, "items", []) or [])
    
    for it in item_iter:
        items.append(_InvItem(
            description=_safe_str(_get(it, "description", "desc", default="")),
            quantity=_safe_float(_get(it, "quantity", "qty", default=0)),
            unit_price=_safe_float(_get(it, "unit_price", "price", default=0)),
        ))

    # Steuern & Summen
    tax_rate = _safe_float(_get(invoice, "tax_rate", default=0.0))
    if tax_rate > 1.0:
        tax_rate = tax_rate / 100.0
    
    is_small_business = bool(_get(comp, "is_small_business", default=False)) if comp is not None else (tax_rate == 0.0)

    net = sum(i.quantity * i.unit_price for i in items)
    tax = net * tax_rate
    gross = net + tax

    # Datum
    inv_date = _safe_str(_get(invoice, "date", "invoice_date", default=""))
    service_date = _safe_str(_get(invoice, "delivery_date", default=""))
    if not service_date:
        service_from = _safe_str(_get(invoice, "service_from", default=""))
        service_to = _safe_str(_get(invoice, "service_to", default=""))
        if service_from and service_to and service_from != service_to:
            service_date = f"{service_from} bis {service_to}"
        else:
            service_date = service_from or service_to

    due_str = ""
    try:
        if inv_date:
            d = datetime.strptime(inv_date, "%Y-%m-%d").date()
            due_str = (d + timedelta(days=14)).strftime("%d.%m.%Y")
            inv_date = d.strftime("%d.%m.%Y") # Formatieren für Anzeige
    except Exception:
        pass

    # 2. PDF SETUP
    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4
    c.setLineWidth(LAYOUT["line_width"])

    # Layout Variablen laden
    mx = LAYOUT["margin_x"]
    my_top = h - LAYOUT["margin_top"]
    my_bot = LAYOUT["margin_bottom"]
    content_w = w - (2 * mx)

    font_r = LAYOUT["font_reg"]
    font_b = LAYOUT["font_bold"]

    # Helper Fonts
    def set_font(bold=False, size=10, color=LAYOUT["col_primary"]):
        c.setFont(font_b if bold else font_r, size)
        c.setFillColorRGB(*color)

    # 3. HEADER (Logo / Firmenname links, Titel rechts)
    header_top_y = my_top
    header_baseline_y = header_top_y - LAYOUT["header_baseline_offset"]
    left_w = min(float(LAYOUT["header_left_w"]), float(content_w) * 0.6)
    gap_w = float(LAYOUT["header_gap"])
    right_edge_x = w - mx
    right_col_w = max(float(content_w) - left_w - gap_w, 40 * mm)

    title = _safe_str(_get(invoice, "title", default="")) or "Rechnung"
    nr = _safe_str(_get(invoice, "nr", "invoice_number", default=""))

    logo = None
    comp_id = _get(comp, "id", default=None)
    if comp_id:
        logo_path = company_logo_path(comp_id)
        if os.path.exists(logo_path):
            try:
                logo = ImageReader(str(logo_path))
            except Exception:
                logo = None

    # Left header column: logo or company name (wrap inside left_w)
    if logo is not None:
        iw, ih = logo.getSize()
        max_w = float(LAYOUT["logo_max_w"])
        max_h = float(LAYOUT["logo_max_h"])
        scale = min(max_w / iw, max_h / ih, 1.0)
        draw_w = iw * scale
        draw_h = ih * scale
        c.drawImage(
            logo,
            mx,
            header_top_y - draw_h,
            width=draw_w,
            height=draw_h,
            mask="auto",
        )
        left_block_bottom_y = header_top_y - draw_h
    else:
        fallback_name = _safe_str(_get(comp, "name", default="")) or "DANEP"
        set_font(bold=True, size=12)
        name_lines = _wrap_text(fallback_name, font_b, 12, left_w)
        name_y = header_baseline_y
        for ln in name_lines[:2]:
            c.drawString(mx, name_y, ln)
            name_y -= float(LAYOUT["header_sub_leading"])
        left_block_bottom_y = name_y

    # Right header column: title + optional number (wrap inside right_col_w)
    set_font(bold=True, size=LAYOUT["fs_title"])
    title_lines = _wrap_text(title, font_b, LAYOUT["fs_title"], right_col_w)
    ty = header_baseline_y
    for ln in title_lines[:2]:
        c.drawRightString(right_edge_x, ty, ln)
        ty -= float(LAYOUT["header_title_leading"])

    if nr:
        set_font(bold=False, size=LAYOUT["fs_text"])
        c.drawRightString(right_edge_x, ty, f"Nr. {nr}")
        ty -= float(LAYOUT["header_sub_leading"])
    right_block_bottom_y = ty

    # 4. EMPFÄNGER
    y_addr = h - LAYOUT["pos_address"]

    sender_parts = []
    if comp:
        s_name = _safe_str(_get(comp, "name"))
        s_str = _safe_str(_get(comp, "street"))
        s_city = f"{_get(comp, 'postal_code','')} {_get(comp, 'city','')}".strip()
        sender_parts = [p for p in [s_name, s_str, s_city] if p]

    # Empfänger Block
    y_rec = y_addr - 5*mm
    set_font(size=LAYOUT["fs_text"], color=LAYOUT["col_primary"])
    
    rec_lines = [l for l in [rec_name, rec_street, f"{rec_zip} {rec_city}".strip(), rec_country] if l]
    if not rec_lines: rec_lines = ["(Kein Empfänger hinterlegt)"]

    for ln in rec_lines:
        c.drawString(mx, y_rec, ln)
        y_rec -= 12

    # 5. META DATEN (RECHTS)
    y_meta = h - LAYOUT["pos_info"]
    meta_x = w - mx

    header_bottom_y = min(left_block_bottom_y, right_block_bottom_y)
    min_gap = float(LAYOUT["header_meta_gap"])
    if y_meta > header_bottom_y - min_gap:
        y_meta = header_bottom_y - min_gap
    
    company_tax_id = _safe_str(_get(comp, "tax_id"))
    company_vat_id = _safe_str(_get(comp, "vat_id"))

    meta_data = []
    if sender_parts:
        meta_data.append(("Absender:", sender_parts[0]))
    meta_data.extend([
        ("Rechnungsnr.:", nr or "-"),
        ("Datum:", inv_date or "-"),
        ("Leistungszeitraum:", service_date or "-"),
        ("Zahlung bis:", due_str or "-"),
    ])

    if company_vat_id:
        meta_data.append(("USt-ID:", company_vat_id))
    elif company_tax_id:
        meta_data.append(("Steuernr.:", company_tax_id))

    for label, val in meta_data:
        set_font(bold=True, size=9)
        c.drawRightString(meta_x, y_meta, label)
        set_font(bold=False, size=9)
        c.drawRightString(meta_x, y_meta - 11, val)
        y_meta -= 24

    # Y synchronisieren (unter Empfänger oder Meta, je nachdem was tiefer ist)
    y = min(y_rec, y_meta) - 12*mm

    # 6. INTRO TEXT
    intro = _safe_str(_get(invoice, "intro_text", "intro", default=""))
    if not intro:
        intro = _safe_str(_get(comp, "invoice_intro", default="")) if comp is not None else ""
    if not intro:
        intro = "Vielen Dank für den Auftrag. Hiermit stelle ich folgende Leistungen in Rechnung."

    intro_lines = _wrap_text(intro, font_r, LAYOUT["fs_text"], content_w)
    set_font(size=LAYOUT["fs_text"])
    for ln in intro_lines:
        c.drawString(mx, y, ln)
        y -= 12
    y -= 12

    # 7. TABELLE
    # Spaltenbreiten berechnen
    w_desc = content_w * LAYOUT["col_w_desc"]
    w_qty = content_w * LAYOUT["col_w_qty"]
    # Der Rest ist Preis
    
    # Header Funktion
    def draw_table_header(curr_y):
        c.setFillColorRGB(*LAYOUT["col_header_bg"])
        c.rect(mx, curr_y - 16, content_w, 16, stroke=0, fill=1) # Hintergrund
        
        c.setStrokeColorRGB(*LAYOUT["col_line"])
        c.line(mx, curr_y - 16, w - mx, curr_y - 16) # Linie unten

        set_font(bold=True, size=11)
        c.drawString(mx + 6, curr_y - 12, "Beschreibung")
        c.drawRightString(mx + w_desc + w_qty - 6, curr_y - 12, "Menge")
        c.drawRightString(w - mx - 6, curr_y - 12, "Preis")
        return curr_y - 20

    y = draw_table_header(y)

    set_font(bold=False, size=9)

    for it in items:
        desc_lines = _wrap_text(it.description, font_r, 9, w_desc - 12)
        row_h = max(16, 8 + len(desc_lines) * 11)

        # Page Break Check
        if y - row_h < my_bot + 50*mm:
            c.showPage()
            c.setLineWidth(LAYOUT["line_width"])
            y = h - LAYOUT["margin_top"]
            y = draw_table_header(y)
            set_font(bold=False, size=9)

        # Draw Row
        ty = y - 12
        for ln in desc_lines:
            c.drawString(mx + 6, ty, ln)
            ty -= 11

        qty_str = f"{it.quantity:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        c.drawRightString(mx + w_desc + w_qty - 6, y - 12, qty_str)

        price_str = f"{it.unit_price:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        c.drawRightString(w - mx - 6, y - 12, price_str)
        
        # Linie pro Zeile
        c.setStrokeColorRGB(*LAYOUT["col_line"])
        c.line(mx, y - row_h, w - mx, y - row_h)

        y -= row_h

    # 8. SUMMEN
    y -= 20
    if y < my_bot + 60*mm:
        c.showPage()
        c.setLineWidth(LAYOUT["line_width"])
        y = h - LAYOUT["margin_top"]

    val_x = w - mx - 10
    lbl_x = val_x - 30*mm

    def draw_total_line(lbl, val, bold=False, offset=12):
        set_font(bold=bold, size=10)
        c.drawString(lbl_x, y, lbl)
        c.drawRightString(val_x, y, val)
        return y - offset

    net_s = f"{net:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    y = draw_total_line("Netto:", net_s)

    gross_s = f"{gross:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

    if tax_rate > 0:
        tax_s = f"{tax:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        y = draw_total_line(f"USt ({int(tax_rate*100)}%):", tax_s)
        c.line(lbl_x, y+2, val_x, y+2) # Summenstrich
        y -= 4
        y = draw_total_line("Gesamt:", gross_s, bold=True)
    else:
        # Kleinunternehmer -> Nur Gesamt
        y = draw_total_line("Gesamt:", gross_s, bold=True)
    
    # Hinweis Text (Kleinunternehmer)
    if is_small_business:
        y -= 10
        set_font(size=8)
        c.drawString(mx, y, LAYOUT["txt_small_biz"])

    # 9. FOOTER (Wird auf die aktuelle Seite gemalt)
    footer_y = my_bot + 25*mm
    c.setStrokeColorRGB(*LAYOUT["col_line"])
    c.line(mx, footer_y, w - mx, footer_y)
    
    footer_y -= 5*mm
    set_font(size=7, color=(0.4, 0.4, 0.4))
    
    # Footer Daten
    f_addr = [_safe_str(_get(comp, "name")), _safe_str(_get(comp, "email")), _safe_str(_get(comp, "phone"))]
    f_bank = [
        _safe_str(_get(comp, "bank_name")),
        _prefixed_value("IBAN: ", _get(comp, "iban")),
        _prefixed_value("BIC: ", _get(comp, "bic", "swift", "swift_code")),
    ]
    f_legal = [
        _prefixed_value("Steuernr.: ", company_tax_id),
        _prefixed_value("USt-ID: ", company_vat_id),
        _safe_str(_get(comp, "business_type")),
    ]
    
    col_w = content_w / 3
    
    for i, (head, lines) in enumerate(zip(["Kontakt", "Bankverbindung", "Rechtliches"], [f_addr, f_bank, f_legal])):
        tx = mx + (i * col_w)
        ty = footer_y
        
        c.setFont(font_b, 7)
        c.drawString(tx, ty, head)
        c.setFont(font_r, 7)
        
        ty -= 8
        for l in lines:
            if l:
                c.drawString(tx, ty, str(l))
                ty -= 8

    c.save()
    return buf.getvalue()
