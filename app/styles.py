# =========================
# APP/STYLES.PY
# =========================

from __future__ import annotations

"""
Strict design system (light slate, shadcn-inspired).

Rules:
- No Quasar elevation shadows (we reset them globally + wrappers use flat/no-shadow).
- Avoid long inline class strings across pages; prefer STYLE_* constants or wrappers in `ui_components.py`.
- One padding source: outer container/card defines padding; inner layout uses gap only.
"""

# Typography
C_FONT_STACK = '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
C_NUMERIC = "tabular-nums"

# WICHTIG: Alle CSS-Klammern {{ }} sind doppelt, damit Python sie nicht als Variablen liest!
APP_FONT_CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root, body, .q-body {{
    font-family: {C_FONT_STACK};
    letter-spacing: -0.01em;
    color-scheme: light;

    /* Light slate tokens */
    --ff-bg: #f8fafc;            /* slate-50 */
    --ff-surface: #ffffff;       /* white */
    --ff-surface-2: #f1f5f9;     /* slate-100 */
    --ff-border: #e2e8f0;        /* slate-200 */
    --ff-border-strong: #cbd5e1; /* slate-300 */
    --ff-text: #0f172a;          /* slate-900 */
    --ff-muted: #64748b;         /* slate-500 */
    --ff-muted-2: #94a3b8;       /* slate-400 */

    /* Brand accent (used for focus ring / highlights) */
    --brand-primary: #f59e0b;     /* amber-500 */
    --brand-accent: #d97706;      /* amber-600 */

    --ff-ring: rgba(245, 158, 11, 0.25);
  }}

  body, .q-body, .nicegui-content {{
    background: var(--ff-bg) !important;
    color: var(--ff-text) !important;
  }}

  a {{ color: var(--brand-accent); }}
  a.q-link {{ color: inherit; }}
  ::selection {{ background: color-mix(in srgb, var(--brand-primary) 35%, transparent); }}

  /* --- QUASAR: disable elevation everywhere (no double design) --- */
  [class*="q-elevation--"],
  .q-card,
  .q-menu,
  .q-dialog,
  .q-notification,
  .q-tooltip {{
    box-shadow: none !important;
  }}
  .q-btn {{
    box-shadow: none !important;
  }}

  /* Button contrast guard: prevents unreadable label/icon combinations */
  .q-btn[class*="bg-white"],
  .q-btn[class*="bg-slate-50"],
  .q-btn[class*="bg-amber-50"] {{
    color: var(--ff-text) !important;
  }}
  .q-btn[class*="bg-slate-900"],
  .q-btn[class*="bg-rose-600"] {{
    color: #fff !important;
  }}
  .q-btn .q-icon {{
    color: inherit !important;
  }}

  /* --- QUASAR: fields & inputs (outlined dense -> shadcn-like) --- */
  .q-field__label {{
    color: var(--ff-muted) !important;
    font-weight: 500;
  }}
  .q-field--focused .q-field__label {{
    color: var(--ff-text) !important;
    font-weight: 600;
  }}

  .q-field__control {{
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
  }}
  .q-field--outlined .q-field__control {{
    background: var(--ff-surface) !important;
    border-radius: 0.75rem;
  }}
  .q-field--outlined .q-field__control:before {{
    border-color: var(--ff-border) !important;
    border-width: 1px !important;
  }}
  .q-field--outlined.q-field--focused .q-field__control:after {{
    border-color: var(--brand-accent) !important;
    border-width: 1px !important;
    opacity: 1;
  }}
  .q-field--outlined.q-field--focused .q-field__control {{
    box-shadow: 0 0 0 3px var(--ff-ring) !important;
  }}

  .q-field__native,
  .q-field__prefix,
  .q-field__suffix,
  .q-field__input {{
    color: var(--ff-text) !important;
  }}
  .q-field__native::placeholder {{
    color: var(--ff-muted-2) !important;
  }}

  /* Field error/hint text (Quasar bottom slot) – ensure readable on light background */
  .q-field__bottom,
  .q-field__messages,
  .q-field .q-field__bottom .q-field__messages,
  .q-field [class*="text-negative"] {{
    color: #b91c1c !important;
    opacity: 1 !important;
  }}

  /* Auth (login/signup) error text – always visible */
  .ff-auth-error {{
    color: #b91c1c !important;
    opacity: 1 !important;
  }}

  /* Dropdown menus */
  .q-menu {{
    background: var(--ff-surface) !important;
    border: 1px solid var(--ff-border) !important;
    border-radius: 0.75rem;
  }}
  .q-menu .q-item {{ color: var(--ff-text) !important; }}
  .q-menu .q-item__label {{ color: var(--ff-text) !important; }}
  .q-menu .q-item:hover {{ background: var(--ff-surface-2) !important; }}
  .q-menu .q-item--active {{ background: color-mix(in srgb, var(--brand-primary) 12%, white) !important; }}

  /* Notifications */
  .q-notification {{
    background: var(--ff-surface) !important;
    color: var(--ff-text) !important;
    border: 1px solid var(--ff-border) !important;
    border-left: 3px solid var(--brand-primary) !important;
    border-radius: 12px;
  }}
  .q-notification__message,
  .q-notification__caption,
  .q-notification__icon,
  .q-notification__content {{
    color: var(--ff-text) !important;
  }}
  .q-notification__caption {{
    color: var(--ff-muted) !important;
  }}

  /* Checkboxes */
  .q-checkbox__inner--truthy .q-checkbox__bg {{
    background: var(--brand-primary);
    border-color: var(--brand-primary);
  }}
  .q-checkbox__inner--falsy .q-checkbox__bg {{
    border-color: var(--ff-border-strong);
  }}
  .q-checkbox__label {{
    color: var(--ff-text);
  }}

  /* Header search (top bar) */
  .ff-header-search {{
    box-shadow: none !important;
    background: transparent !important;
  }}
  .ff-header-search .q-field__control:before,
  .ff-header-search .q-field__control:after {{
    border-color: transparent !important;
  }}
  .ff-header-search .q-field__control {{
    background: transparent !important;
  }}
  .ff-header-search .q-field__native::placeholder {{
    color: var(--ff-muted-2) !important;
  }}

  /* Documents: compact pill selects/inputs (kept for compatibility) */
  .ff-stroke-input .q-field__control {{
    background: transparent !important;
    border-radius: 9999px !important;
  }}
  .ff-stroke-input .q-field__control:before {{
    border-color: var(--ff-border-strong) !important;
  }}
  .ff-stroke-input.q-field--focused .q-field__control:after {{
    border-color: var(--brand-accent) !important;
  }}

  .ff-select-fill .q-field__control {{
    background: var(--ff-surface) !important;
    border-radius: 9999px !important;
    padding-left: 16px !important;
    padding-right: 16px !important;
    justify-content: center !important;
    align-items: center !important;
  }}
  .ff-select-fill .q-field__control:before {{
    border-color: var(--ff-border) !important;
  }}

  /* Invoice preview (editor) */
  .ff-invoice-preview-frame {{
    border: 1px solid var(--ff-border) !important;
    background: var(--ff-surface) !important;
    border-radius: 16px;
    overflow: hidden;
  }}
  .ff-invoice-preview-frame iframe {{
    display: block;
    width: 100%;
    height: 78vh;
    border: 0;
    background: var(--ff-surface);
  }}

  /* Utilities */
  input:-webkit-autofill {{
    -webkit-text-fill-color: var(--ff-text) !important;
    box-shadow: 0 0 0px 1000px var(--ff-surface) inset !important;
  }}
</style>
"""

# -------------------------
# Design system class tokens
# -------------------------

STYLE_BG = "bg-slate-50 text-slate-900 min-h-screen"
STYLE_CONTAINER = "w-full max-w-6xl mx-auto px-6 py-6 gap-6"

STYLE_CARD = "bg-white border border-slate-200 shadow-sm rounded-xl"
STYLE_CARD_HOVER = "transition-colors hover:bg-slate-50 hover:border-slate-300"

STYLE_HEADING = "text-2xl font-bold tracking-tight text-slate-900"
STYLE_PAGE_TITLE = STYLE_HEADING
STYLE_SECTION_TITLE = "text-sm font-semibold text-slate-900"
STYLE_TEXT_MUTED = "text-sm text-slate-600"
STYLE_TEXT_SUBTLE = "text-sm text-slate-500"
STYLE_TEXT_HINT = "text-sm text-slate-400"

STYLE_BTN_PRIMARY = (
    "bg-slate-900 text-white hover:bg-slate-800 active:scale-[0.99] rounded-lg px-4 py-2 text-sm "
    "font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/40"
)
STYLE_BTN_SECONDARY = (
    "bg-white text-slate-900 border border-slate-200 hover:bg-slate-50 active:scale-[0.99] rounded-lg px-4 py-2 "
    "text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/30"
)
STYLE_BTN_GHOST = (
    "text-slate-600 hover:text-slate-900 hover:bg-slate-100 active:scale-[0.99] rounded-md px-3 py-2 text-sm "
    "font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/30"
)
STYLE_BTN_MUTED = (
    "bg-slate-100 text-slate-700 border border-slate-200 hover:bg-slate-200 active:scale-[0.99] rounded-lg px-4 py-2 "
    "text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/30"
)
STYLE_BTN_DANGER = (
    "bg-rose-600 text-white hover:bg-rose-700 active:scale-[0.99] rounded-lg px-4 py-2 text-sm "
    "font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/30"
)
STYLE_BTN_ACCENT = (
    "rounded-full justify-center items-center bg-white hover:bg-amber-50 shadow-none border border-amber-300 "
    "text-amber-700 active:scale-[0.99] px-4 py-2 text-sm font-semibold transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/40"
)

STYLE_INPUT = "w-full text-sm"
STYLE_INPUT_ROUNDED = "rounded-full"

STYLE_DROPDOWN_PANEL = f"absolute left-0 right-0 mt-1 z-10 {STYLE_CARD} p-1"
STYLE_DROPDOWN_OPTION = "w-full text-left px-3 py-2 text-sm rounded-md hover:bg-slate-100"
STYLE_DROPDOWN_OPTION_ACTIVE = "bg-slate-100"
STYLE_DROPDOWN_LABEL = "text-left text-slate-900"

STYLE_STEPPER_ACTIVE = "text-slate-900 font-semibold text-sm"
STYLE_STEPPER_INACTIVE = "text-slate-500 text-sm"
STYLE_STEPPER_ARROW = "text-slate-400 text-sm"

STYLE_TABLE_HEADER = "w-full px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600 border-b border-slate-200"
STYLE_TABLE_ROW = "w-full px-3 py-2 text-sm text-slate-800 border-b border-slate-200/70"

STYLE_BADGE_GREEN = "bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full text-xs font-medium text-center"
STYLE_BADGE_BLUE = "bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded-full text-xs font-medium text-center"
STYLE_BADGE_GRAY = "bg-slate-100 text-slate-700 border border-slate-200 px-2 py-0.5 rounded-full text-xs font-medium text-center"
STYLE_BADGE_YELLOW = "bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full text-xs font-medium text-center"
STYLE_BADGE_RED = "bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded-full text-xs font-medium text-center"

# -------------------------
# Backwards-compatible aliases (temporary)
# -------------------------

C_BG = STYLE_BG
C_CONTAINER = STYLE_CONTAINER

C_CARD = STYLE_CARD
C_CARD_HOVER = STYLE_CARD_HOVER
C_GLASS_CARD = STYLE_CARD
C_GLASS_CARD_HOVER = STYLE_CARD_HOVER

C_BTN_PRIM = STYLE_BTN_PRIMARY
C_BTN_SEC = STYLE_BTN_SECONDARY
C_BTN_MUTED = STYLE_BTN_MUTED
C_BTN_ORANGE = STYLE_BTN_PRIMARY

C_INPUT = STYLE_INPUT
C_INPUT_ROUNDED = STYLE_INPUT_ROUNDED

C_BADGE_GREEN = STYLE_BADGE_GREEN
C_BADGE_BLUE = STYLE_BADGE_BLUE
C_BADGE_GRAY = STYLE_BADGE_GRAY
C_BADGE_YELLOW = STYLE_BADGE_YELLOW
C_BADGE_RED = STYLE_BADGE_RED

C_PAGE_TITLE = STYLE_PAGE_TITLE
C_SECTION_TITLE = STYLE_SECTION_TITLE

C_TABLE_HEADER = STYLE_TABLE_HEADER
C_TABLE_ROW = STYLE_TABLE_ROW
