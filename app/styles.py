# =========================
# APP/STYLES.PY
# =========================

# --- STYLE SYSTEM (Clean admin look) ---
C_BG = "bg-neutral-950 text-neutral-100 min-h-screen"
C_CONTAINER = "w-full max-w-6xl mx-auto px-5 py-6 gap-5"
C_FONT_STACK = '"Inter", "IBM Plex Sans", "Segoe UI", system-ui, sans-serif'
C_NUMERIC = "tabular-nums"

APP_FONT_CSS = f"""
<style>
  :root, body, .q-body {{
    font-family: {C_FONT_STACK};
    letter-spacing: -0.01em;
    color-scheme: dark;
    --brand-primary: #ffc524;
    --brand-primary-2: #ffb300;
    --brand-accent: #ff9f0a;
    --surface-0: #0a0b0d;
    --surface-1: #131619;
    --surface-2: #1c2024;
    --text-muted: #9ca3af;
  }}
  a {{
    color: var(--brand-primary);
  }}
  ::selection {{
    background: color-mix(in srgb, var(--brand-primary) 70%, transparent);
    color: #0a0b0d;
  }}
  .q-field__label {{
    color: var(--text-muted);
  }}
  .q-field--focused .q-field__label {{
    color: var(--brand-primary);
  }}
  .q-field__control:before {{
    background: #2f3338;
  }}
  .q-field__control:after {{
    background: var(--brand-primary);
  }}
  .q-field--focused .q-field__control:after {{
    background: var(--brand-primary);
  }}
  .q-field--outlined .q-field__control {{
    background: #0f172a;
  }}
  .q-field--outlined .q-field__control:before {{
    border-color: #2f3338;
  }}
  .q-field--outlined.q-field--focused .q-field__control:before {{
    border-color: var(--brand-primary-2);
  }}
  .q-field__native, .q-field__prefix, .q-field__suffix {{
    color: #e5e7eb;
  }}
  .q-checkbox__inner--truthy .q-checkbox__bg {{
    background: var(--brand-primary);
    border-color: var(--brand-primary);
  }}
  .q-checkbox__inner--falsy .q-checkbox__bg {{
    border-color: #3f454b;
  }}
  .q-menu, .q-menu .q-list {{
    background: #111827;
    color: #e5e7eb;
  }}
  .q-item {{
    color: #e5e7eb;
  }}
  .q-item--active {{
    color: var(--brand-primary);
  }}
  .q-item__section--main {{
    color: inherit;
  }}
  .q-btn .q-focus-helper {{
    background: color-mix(in srgb, var(--brand-primary-2) 25%, transparent);
  }}
  input:-webkit-autofill,
  input:-webkit-autofill:hover,
  input:-webkit-autofill:focus {{
    -webkit-text-fill-color: #e5e7eb;
    transition: background-color 9999s ease-in-out 0s;
    box-shadow: 0 0 0px 1000px #111827 inset;
  }}
</style>
"""

# Panels / cards
C_CARD = "bg-neutral-900/80 border border-neutral-800/80 rounded-lg shadow-sm"
C_CARD_HOVER = "hover:border-neutral-700/80 hover:bg-neutral-900/60 transition-all duration-150"
C_GLASS_CARD = "bg-neutral-900/80 border border-neutral-800/80 rounded-lg shadow-sm"
C_GLASS_CARD_HOVER = "hover:border-neutral-700/80 hover:bg-neutral-900/60 transition-all duration-150"

# Buttons
C_BTN_PRIM = "!bg-[#ffc524] !text-neutral-950 hover:bg-[#ffd35d] active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-all focus-visible:ring-2 focus-visible:ring-[#ffc524]/40"
C_BTN_SEC = "!bg-neutral-900 !text-neutral-200 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-800 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[#ffc524]/20"

# Inputs
C_INPUT = "border-neutral-800 bg-neutral-900 text-neutral-100 placeholder:text-neutral-500 rounded-lg text-sm px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-[#ffc524]/30 focus-visible:border-[#ffc524]/40 w-full transition-all"

# Badges
C_BADGE_GREEN = "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_BLUE = "bg-sky-500/10 text-sky-300 border border-sky-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_GRAY = "bg-neutral-800 text-neutral-300 border border-neutral-700 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_YELLOW = "bg-[#ffc524]/10 text-[#ffd35d] border border-[#ffc524]/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_RED = "bg-rose-500/10 text-rose-300 border border-rose-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"

# Typography
C_PAGE_TITLE = "text-2xl font-semibold text-neutral-100 tracking-tight"
C_SECTION_TITLE = "text-sm font-semibold text-neutral-400"

# Tables
C_TABLE_HEADER = "w-full bg-neutral-900/80 border-b border-neutral-800 px-4 py-3 gap-4"
C_TABLE_ROW = "w-full px-4 py-3 border-b border-neutral-800 items-center gap-4 hover:bg-neutral-900/70 transition-colors"

# Legacy header tokens (kept so other components don’t break)
C_HEADER = "bg-neutral-950 border-b border-neutral-800 h-16 px-6 flex items-center justify-between sticky top-0 z-50"
C_BRAND_BADGE = "bg-[#ffc524] text-neutral-950 p-2 rounded-lg shadow-sm"
C_NAV_ITEM = "text-neutral-400 hover:text-neutral-100 px-3 py-2 rounded-lg hover:bg-neutral-900 transition-all duration-150"
C_NAV_ITEM_ACTIVE = "text-[#ffd35d] px-3 py-2 rounded-lg bg-neutral-900 transition-all duration-150"
