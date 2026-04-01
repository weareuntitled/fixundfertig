# =========================
# APP/STYLES.PY
# =========================

from __future__ import annotations

"""
Strict design system (light slate, shadcn-inspired).

Rules:
- No Quasar elevation shadows on raw Quasar widgets (we reset them globally); our `STYLE_CARD` / shell may use light Tailwind shadows.
- Avoid long inline class strings across pages; prefer STYLE_* constants or wrappers in `ui_components.py`.
- One padding source: outer container/card defines padding; inner layout uses gap only.

Typography (3 sizes × 2 weights: 400 + 600 via Tailwind `font-normal` default / `font-semibold`):
- Page: `STYLE_PAGE_TITLE` (text-2xl/3xl, semibold)
- Section / table header: `STYLE_SECTION_TITLE` / `STYLE_TABLE_HEADER` (text-sm / text-xs uppercase, semibold)
- Body / muted / table rows: `STYLE_TEXT_*` / `STYLE_TABLE_ROW` (text-sm, normal weight unless semibold badge)
"""

# Typography
C_FONT_STACK = '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
C_NUMERIC = "tabular-nums"

# WICHTIG: Alle CSS-Klammern {{ }} sind doppelt, damit Python sie nicht als Variablen liest!
APP_FONT_CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root, body, .q-body {{
    font-family: {C_FONT_STACK};
    font-size: 13px;
    line-height: 1.5;
    letter-spacing: -0.01em;
    color-scheme: light;

    /* Light slate tokens */
    --ff-bg: #f8fafc;            /* near-white base */
    --ff-surface: #ffffff;       /* white */
    --ff-surface-2: #f1f5f9;     /* slate-100 */
    --ff-border: #e2e8f0;        /* slate-200 */
    --ff-border-strong: #cbd5e1; /* slate-300 */
    --ff-text: #0f172a;          /* slate-900 */
    --ff-muted: #64748b;         /* slate-500 */
    --ff-muted-2: #94a3b8;       /* slate-400 */

    /* Brand accent — indigo/violet (Stripe/Supabase aesthetic) */
    --brand-primary: #6366f1;     /* indigo-500 */
    --brand-accent: #4f46e5;      /* indigo-600 */
    --brand-subtle: #eef2ff;      /* indigo-50 */

    --ff-ring: rgba(99, 102, 241, 0.20);
  }}

  body, .q-body, .nicegui-content {{
    background-color: var(--ff-bg) !important;
    background-image:
      radial-gradient(ellipse 80% 50% at 80% 0%, rgba(99,102,241,0.07) 0%, transparent 60%),
      radial-gradient(ellipse 60% 40% at 10% 90%, rgba(139,92,246,0.05) 0%, transparent 55%),
      linear-gradient(180deg, #fafafa 0%, #f8fafc 100%) !important;
    background-attachment: fixed !important;
    color: var(--ff-text) !important;
    padding-left: env(safe-area-inset-left, 0px);
    padding-right: env(safe-area-inset-right, 0px);
  }}

  a {{ color: var(--brand-accent); }}
  a.q-link {{ color: inherit; }}
  ::selection {{ background: color-mix(in srgb, var(--brand-primary) 18%, transparent); }}

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

  /* --- QUASAR: fields & inputs (outlined dense -> shadcn-like) --- */
  .q-field__label {{
    color: var(--ff-muted) !important;
    font-weight: 400;
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
    border-radius: 0.375rem;
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
    transition: box-shadow 0.15s ease, border-color 0.15s ease !important;
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
    border: 1px solid rgba(15,23,42,0.08) !important;
    border-radius: 0.5rem;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.03) !important;
  }}
  .q-menu .q-item {{ color: var(--ff-text) !important; }}
  .q-menu .q-item__label {{ color: var(--ff-text) !important; }}
  .q-menu .q-item:hover {{ background: var(--ff-surface-2) !important; }}
  .q-menu .q-item--active {{
    background: var(--brand-subtle) !important;
    color: var(--brand-accent) !important;
  }}

  /* Notifications */
  .q-notification {{
    background: var(--ff-surface) !important;
    color: var(--ff-text) !important;
    border: 1px solid var(--ff-border) !important;
    border-left: 3px solid var(--brand-primary) !important;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06) !important;
    animation: ff-slide-up 0.2s cubic-bezier(0.4, 0, 0.2, 1) both;
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

  /* Desktop sidebar: ensure it is visible and sized on md+ (no reliance on Tailwind order). */
  .ff-desktop-sidebar {{
    display: none !important;
    flex-direction: column !important;
    position: fixed !important;
    left: 1.5rem !important;
    top: 1.5rem !important;
    bottom: 1.5rem !important;
    width: 13rem !important;
    min-width: 13rem !important;
    max-width: 13rem !important;
    z-index: 40 !important;
  }}
  @media (min-width: 768px) {{
    .ff-desktop-sidebar {{
      display: flex !important;
    }}
  }}
  @media (max-width: 767px) {{
    .ff-desktop-sidebar {{
      display: none !important;
    }}
  }}

  /* Drawers: we don't use Quasar side drawers for navigation anymore.
     Hide any leftover drawers on desktop, but DO NOT hide the drawer container
     (it also wraps the main layout/content in Quasar). */
  @media (min-width: 768px) {{
    .q-drawer {{
      display: none !important;
      width: 0 !important;
      max-width: 0 !important;
    }}
    .q-drawer__backdrop {{
      display: none !important;
    }}
  }}

  /* Checkboxes */
  .q-checkbox__inner--truthy .q-checkbox__bg {{
    background: var(--brand-primary);   /* indigo-500 */
    border-color: var(--brand-primary);
  }}
  .q-checkbox__inner--falsy .q-checkbox__bg {{
    border-color: var(--ff-border-strong);
    transition: border-color 0.12s ease;
  }}
  .q-checkbox__label {{
    color: var(--ff-text);
  }}
  .q-checkbox:hover .q-checkbox__inner--falsy .q-checkbox__bg {{
    border-color: var(--brand-primary);
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

  /* Unified upload dropzone */
  .ff-upload {{
    border: 1px dashed var(--ff-border-strong) !important;
    background: var(--ff-surface) !important;
    border-radius: 0.375rem !important;
    padding: 0.75rem !important;
  }}
  .ff-upload:hover {{
    border-color: var(--brand-accent) !important;
    background: color-mix(in srgb, var(--brand-primary) 5%, white) !important;
  }}
  .ff-upload .q-uploader__list {{
    border-top: 1px solid var(--ff-border) !important;
    margin-top: 0.5rem !important;
    padding-top: 0.5rem !important;
  }}

  /* Invoice preview (editor): desktop preview card – visible on md+ */
  .ff-invoice-preview-desktop {{
    display: none !important;
  }}
  @media (min-width: 768px) {{
    .ff-invoice-preview-desktop {{
      display: block !important;
    }}
  }}

  .ff-invoice-preview-frame {{
    border: 1px solid var(--ff-border) !important;
    background: var(--ff-surface) !important;
    border-radius: 8px;
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

  /* ===== ANIMATIONS & MICRO-INTERACTIONS ===== */

  /* Page content fade-in */
  @keyframes ff-fade-in {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .ff-page-enter {{
    animation: ff-fade-in 0.22s cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }}

  /* Slide up (cards, notifications) */
  @keyframes ff-slide-up {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}

  /* KPI cards staggered entrance */
  .ff-kpi-card {{ animation: ff-slide-up 0.3s cubic-bezier(0.4, 0, 0.2, 1) both; }}
  .ff-kpi-card:nth-child(1) {{ animation-delay: 0.04s; }}
  .ff-kpi-card:nth-child(2) {{ animation-delay: 0.08s; }}
  .ff-kpi-card:nth-child(3) {{ animation-delay: 0.12s; }}
  .ff-kpi-card:nth-child(4) {{ animation-delay: 0.16s; }}

  /* Nav buttons — override Quasar flat/text-primary defaults */
  .q-btn.ff-nav-btn {{
    color: #64748b !important;   /* slate-500 — neutral inactive */
  }}
  .q-btn.ff-nav-btn .q-icon {{
    color: #64748b !important;
  }}
  .q-btn.ff-nav-btn:hover {{
    color: #0f172a !important;
  }}
  .q-btn.ff-nav-btn:hover .q-icon {{
    color: #0f172a !important;
  }}

  /* Active nav button — filled indigo pill, override Quasar flat */
  .q-btn.ff-nav-btn.ff-nav-active {{
    background: #4f46e5 !important;
    color: white !important;
  }}
  .q-btn.ff-nav-btn.ff-nav-active::before {{
    background: transparent !important;
  }}
  .q-btn.ff-nav-btn.ff-nav-active .q-focus-helper {{
    display: none !important;
  }}
  .q-btn.ff-nav-btn.ff-nav-active .q-icon,
  .q-btn.ff-nav-btn.ff-nav-active .q-btn__content {{
    color: white !important;
  }}

  /* Nav item hover micro-slide */
  .ff-nav-btn {{
    transition: background 0.12s ease, color 0.12s ease, box-shadow 0.12s ease, transform 0.1s ease !important;
  }}
  .ff-nav-btn:not(.ff-nav-active):hover {{ transform: translateX(2px); }}

  /* Button smooth transitions */
  .q-btn {{
    transition: background 0.12s ease, color 0.12s ease, box-shadow 0.12s ease, transform 0.1s ease !important;
  }}
  .q-btn:active {{ transform: scale(0.98) !important; }}

  /* Card hover lift */
  .ff-card-hover-lift {{
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
  }}
  .ff-card-hover-lift:hover {{
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.08) !important;
  }}

  /* Mobile slide-in for dialog menu */
  @keyframes ff-slide-right {{
    from {{ opacity: 0; transform: translateX(-16px); }}
    to   {{ opacity: 1; transform: translateX(0); }}
  }}
  .q-dialog__inner {{
    animation: ff-slide-right 0.22s cubic-bezier(0.4, 0, 0.2, 1) both;
  }}

  /* Q-item transition */
  .q-item {{
    transition: background 0.1s ease, color 0.1s ease !important;
  }}

  /* ===== MOBILE ===== */

  /* Mobile bottom nav bar */
  .ff-mobile-bottomnav {{
    position: fixed;
    bottom: 0; left: 0; right: 0;
    background: rgba(255,255,255,0.96);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-top: 1px solid rgba(15,23,42,0.07);
    box-shadow: 0 -4px 20px rgba(0,0,0,0.06);
    z-index: 50;
    padding-bottom: env(safe-area-inset-bottom, 0px);
    display: flex;
    align-items: stretch;
  }}
  @media (min-width: 768px) {{
    .ff-mobile-bottomnav {{ display: none !important; }}
  }}

  .ff-mobile-nav-item {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    padding: 8px 4px 6px;
    font-size: 10px;
    font-weight: 600;
    color: #94a3b8;
    transition: color 0.12s ease;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    user-select: none;
  }}
  .ff-mobile-nav-item.ff-nav-active {{
    color: #4f46e5;
  }}
  .ff-mobile-nav-item .ff-nav-dot {{
    width: 34px; height: 28px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.12s ease;
  }}
  .ff-mobile-nav-item.ff-nav-active .ff-nav-dot {{
    background: #eef2ff;
  }}

  /* Mobile: ensure adequate touch targets */
  @media (max-width: 767px) {{
    .q-btn {{ min-height: 44px !important; }}
    .q-field__control {{ min-height: 48px !important; }}
  }}
</style>
"""

# -------------------------
# Design system class tokens
# -------------------------

STYLE_BG = "bg-[#f8fafc] text-slate-900 min-h-screen"
STYLE_CONTAINER = "w-full max-w-6xl mx-auto px-3 md:px-6 py-4 md:py-6 gap-4 md:gap-6"

STYLE_CARD = (
    "bg-white border border-slate-200/80 rounded-lg "
    "shadow-[0_1px_2px_rgba(0,0,0,0.04)] ring-1 ring-slate-900/[0.03]"
)
STYLE_CARD_HOVER = (
    "transition-all duration-150 hover:shadow-sm hover:border-slate-300/80"
)

STYLE_HEADING = "text-base font-semibold tracking-tight text-slate-900"
STYLE_PAGE_TITLE = STYLE_HEADING
STYLE_SECTION_TITLE = "text-xs font-medium text-slate-600 tracking-normal"
STYLE_TEXT_MUTED = "text-xs text-slate-500"
STYLE_TEXT_SUBTLE = "text-xs text-slate-500"
STYLE_TEXT_HINT = "text-xs text-slate-400"
STYLE_TEXT_ERROR = "text-xs text-rose-600"

STYLE_BTN_PRIMARY = (
    "bg-indigo-600 text-white hover:bg-indigo-700 active:bg-indigo-800 active:scale-[0.99] "
    "rounded-md px-2.5 py-1 text-[12.5px] font-medium shadow-sm transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40"
)
STYLE_BTN_SECONDARY = (
    "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 "
    "active:scale-[0.99] rounded-md px-2.5 py-1 text-[12.5px] font-medium shadow-sm transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/30"
)
STYLE_BTN_GHOST = (
    "text-slate-600 hover:text-slate-900 hover:bg-slate-100 active:scale-[0.99] "
    "rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/30"
)
STYLE_BTN_MUTED = STYLE_BTN_GHOST
STYLE_BTN_DANGER = (
    "bg-rose-600 text-white hover:bg-rose-700 active:scale-[0.99] rounded-md px-2.5 py-1 "
    "text-[12.5px] font-medium shadow-sm transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/30"
)
STYLE_BTN_ACCENT = (
    "bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 "
    "active:scale-[0.99] rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/40"
)

STYLE_INPUT = "w-full text-sm"
STYLE_INPUT_ROUNDED = "rounded-full"

STYLE_TAP_TARGET = "min-w-[44px] min-h-[44px] flex items-center justify-center"

# Icon-only row actions / shell affordances (toolbar); merge with ff_icon_button defaults.
STYLE_ICON_TOOLBAR = f"{STYLE_TAP_TARGET} text-slate-500 hover:text-slate-900"

STYLE_LINK_NEUTRAL = "text-sm text-slate-600 hover:text-slate-900 no-underline"
STYLE_LINK_BRAND = "text-sm text-indigo-600 hover:text-indigo-700 no-underline"

STYLE_DROPDOWN_PANEL = f"absolute left-0 right-0 mt-1 z-10 {STYLE_CARD} p-1"
STYLE_DROPDOWN_OPTION = "w-full text-left px-3 py-2 text-sm rounded-md hover:bg-slate-100"
STYLE_DROPDOWN_OPTION_ACTIVE = "bg-slate-100"
STYLE_DROPDOWN_LABEL = "text-left text-slate-900"

STYLE_STEPPER_ACTIVE = "text-slate-900 font-semibold text-sm"
STYLE_STEPPER_INACTIVE = "text-slate-500 text-sm"
STYLE_STEPPER_ARROW = "text-slate-400 text-sm"

STYLE_TABLE_HEADER = (
    "w-full px-3 py-1.5 text-[11px] font-medium tracking-wider "
    "text-slate-400 border-b border-slate-100 bg-slate-50/60"
)
STYLE_TABLE_ROW = (
    "w-full px-3 py-2 text-[13px] text-slate-700 border-b border-slate-100/80 "
    "hover:bg-slate-50/60 transition-colors"
)

STYLE_BADGE_GREEN = "bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded text-xs font-medium text-center"
STYLE_BADGE_BLUE = "bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded text-xs font-medium text-center"
STYLE_BADGE_GRAY = "bg-slate-100 text-slate-700 border border-slate-200 px-2 py-0.5 rounded text-xs font-medium text-center"
STYLE_BADGE_YELLOW = "bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded text-xs font-medium text-center"
STYLE_BADGE_RED = "bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded text-xs font-medium text-center"

STYLE_BADGE_FILE_PDF = "bg-indigo-50 text-indigo-700 border border-indigo-200"
STYLE_BADGE_FILE_IMAGE = "bg-indigo-50 text-indigo-700 border border-indigo-200"
STYLE_BADGE_FILE_OTHER = "bg-slate-100 text-slate-600 border border-slate-200"

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
C_BTN_ORANGE = STYLE_BTN_ACCENT

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
