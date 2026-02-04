# =========================
# APP/STYLES.PY
# =========================

# --- STYLE SYSTEM (Clean admin look) ---
C_BG = "bg-neutral-950 text-neutral-100 min-h-screen"
C_CONTAINER = "w-full max-w-6xl mx-auto px-5 py-6 gap-5"
C_FONT_STACK = '"Inter", "IBM Plex Sans", "Segoe UI", system-ui, sans-serif'
C_NUMERIC = "tabular-nums"

# WICHTIG: Alle CSS-Klammern {{ }} sind doppelt, damit Python sie nicht als Variablen liest!
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
    --text-muted: #94a3b8;
  }}
  a {{ color: var(--brand-primary); }}
  a.q-link {{ color: inherit; }}
  ::selection {{ background: color-mix(in srgb, var(--brand-primary) 70%, transparent); color: #0a0b0d; }}

  /* --- QUASAR OVERRIDES FOR DARK MODE --- */
  
  /* Fields & Inputs */
  .q-field__label {{ color: #94a3b8 !important; font-weight: 400; }}
  .q-field--focused .q-field__label {{ color: var(--brand-primary) !important; font-weight: 600; }}
  
  .q-field__control {{ transition: box-shadow 0.2s ease, border-color 0.2s ease !important; }}
  .q-field--outlined .q-field__control {{ background: #1f2937 !important; border-radius: 0.375rem; }}
  .q-field--outlined .q-field__control:before {{ border-color: #334155 !important; border-width: 1px !important; }}
  .q-field--outlined.q-field--focused .q-field__control:after {{ border-color: var(--brand-primary) !important; border-width: 1.5px !important; opacity: 1; }}

  .ff-stroke-input .q-field__control {{
    background: transparent !important;
    border-radius: 9999px !important;
  }}
  .ff-stroke-input .q-field__control:before {{
    border-color: #475569 !important;
  }}
  .ff-stroke-input.q-field--focused .q-field__control:after {{
    border-color: var(--brand-primary) !important;
  }}
  
  /* Input Text Colors */
  .q-field__native, .q-field__prefix, .q-field__suffix, .q-field__input {{ color: #ffffff !important; }}
  .q-field__native::placeholder {{ color: #64748b !important; }}
  
  /* DROPDOWN MENUS (Fixes invisible text) */
  .q-menu {{
    background: #171717 !important; /* neutral-900 */
    border: 1px solid #262626 !important; /* neutral-800 */
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5) !important;
  }}
  .q-menu .q-item {{ color: #e5e7eb !important; }}
  .q-menu .q-item__label {{ color: #e5e7eb !important; }}
  .q-menu .q-item--active {{ color: var(--brand-primary) !important; background: rgba(255, 197, 36, 0.1); }}
  .q-menu .q-item:hover {{ background: #262626 !important; }}
  
  /* Notifications */
  .q-notification {{ background: #0f172a !important; color: #f1f5f9 !important; border: 1px solid #1e293b !important; border-radius: 12px; }}
  
  /* Checkboxes */
  .q-checkbox__inner--truthy .q-checkbox__bg {{ background: var(--brand-primary); border-color: var(--brand-primary); }}
  .q-checkbox__inner--falsy .q-checkbox__bg {{ border-color: #4b5563; }}
  .q-checkbox__label {{ color: #e5e7eb; }}

  /* Buttons */
  .q-focus-helper {{ background: #0a0b0d !important; opacity: 1 !important; }}
  
  /* Utilities */
  .q-btn {{ color: inherit; }}
  input:-webkit-autofill {{
    -webkit-text-fill-color: #ffffff !important;
    box-shadow: 0 0 0px 1000px #1f2937 inset !important;
  }}
</style>
"""

# Panels / cards
C_CARD = "bg-neutral-900/80 border border-neutral-800/80 rounded-lg shadow-sm"
C_GLASS_CARD = "bg-neutral-900/80 border border-neutral-800/80 rounded-lg shadow-sm"
C_CARD_HOVER = "transition-colors hover:bg-neutral-900/90 hover:border-neutral-700/80"
C_GLASS_CARD_HOVER = "transition-colors hover:bg-neutral-900/70 hover:border-neutral-700/70"

# Buttons
C_BTN_PRIM = "!bg-neutral-800 !text-white hover:bg-neutral-700 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-all focus-visible:ring-2 focus-visible:ring-[#ffc524]/40"
C_BTN_SEC = "!bg-neutral-900 !text-neutral-200 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-800 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[#ffc524]/20"

# Inputs
C_INPUT = "w-full text-sm transition-all"

# Badges
C_BADGE_GREEN = "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_BLUE = "bg-sky-500/10 text-sky-300 border border-sky-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_GRAY = "bg-neutral-800 text-neutral-300 border border-neutral-700 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_YELLOW = "bg-[#ffc524]/10 text-[#ffd35d] border border-[#ffc524]/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_RED = "bg-rose-500/10 text-rose-300 border border-rose-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"

# Typography
C_PAGE_TITLE = "text-xl font-semibold text-neutral-100"
C_SECTION_TITLE = "text-sm font-semibold text-neutral-300"

# Tables
C_TABLE_HEADER = "w-full px-3 py-2 text-xs font-semibold uppercase tracking-wider text-neutral-400 border-b border-neutral-800"
C_TABLE_ROW = "w-full px-3 py-2 text-sm text-neutral-200 border-b border-neutral-800/60"
