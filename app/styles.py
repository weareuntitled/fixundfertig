# =========================
# APP/STYLES.PY
# =========================

# --- STYLE SYSTEM (Clean admin look) ---
# Layout + typography
C_BG = "bg-neutral-950 text-neutral-100 min-h-screen"
C_CONTAINER = "w-full max-w-6xl mx-auto px-[50px] py-6 gap-5 bg-neutral-950 border border-black rounded-[50px]"
C_FONT_STACK = '"Inter", "IBM Plex Sans", "Segoe UI", system-ui, sans-serif'
C_NUMERIC = "tabular-nums"

# WICHTIG: Alle CSS-Klammern {{ }} sind doppelt, damit Python sie nicht als Variablen liest!
APP_FONT_CSS = f"""
<style>
  /* Base tokens */
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
    --color-neutral-100: #f5f5f5;
    --color-neutral-200: #e5e5e5;
    --color-neutral-300: #d4d4d4;
    --color-neutral-400: #a3a3a3;
    --color-neutral-500: #737373;
    --color-neutral-600: #525252;
    --color-neutral-700: #404040;
    --color-neutral-800: #262626;
    --color-neutral-900: #171717;
    --color-neutral-950: #0a0b0d;
  }}

  a {{ color: var(--brand-primary); }}
  a.q-link {{ color: inherit; }}
  ::selection {{ background: color-mix(in srgb, var(--brand-primary) 70%, transparent); color: #0a0b0d; }}

  /* NiceGUI content container */
  .nicegui-content {{
    background-color: var(--color-neutral-950) !important;
  }}

  /* --- QUASAR OVERRIDES FOR DARK MODE --- */
  /* Fields & Inputs */
  .q-field__label {{
    color: #94a3b8 !important;
    font-weight: 400;
    font-size: 12px !important;
    top: 5px !important;
  }}
  .q-field--focused .q-field__label {{ color: var(--brand-primary) !important; font-weight: 600; }}

  /* Header search (top bar) */
  .ff-header-search {{
    box-shadow: none !important;
    border-width: 0px !important;
    border-color: rgba(0, 0, 0, 0) !important;
    border-image: none !important;
    background: unset !important;
    background-color: unset !important;
  }}
  .ff-header-search .q-field__label {{ color: rgba(255, 255, 255, 1) !important; }}
  .ff-header-search.q-field--focused .q-field__label {{ color: rgba(255, 255, 255, 1) !important; }}
  .ff-header-search .q-field__inner {{
    background: unset !important;
    background-color: unset !important;
  }}
  .ff-header-search .q-field__control {{
    color: rgba(240, 240, 240, 1) !important;
    background: unset !important;
    background-color: unset !important;
  }}

  .q-field__control {{ transition: box-shadow 0.2s ease, border-color 0.2s ease !important; }}
  .q-field--outlined .q-field__control {{ background: #1f2937 !important; border-radius: 0.375rem; }}
  .q-field--outlined .q-field__control:before {{ border-color: #334155 !important; border-width: 1px !important; }}
  .q-field--outlined.q-field--focused .q-field__control:after {{ border-color: var(--brand-primary) !important; border-width: 1.5px !important; opacity: 1; }}

  .ff-stroke-input .q-field__control {{
    background: transparent !important;
    border-radius: 9999px !important;
  }}
  .ff-stroke-input .q-field__native {{
    color: var(--brand-primary) !important;
  }}
  .ff-stroke-input .q-field__control:before {{
    border-color: #475569 !important;
  }}
  .ff-stroke-input.q-field--focused .q-field__control:after {{
    border-color: var(--brand-primary) !important;
  }}

  .ff-select-fill .q-field__control {{
    background: #171717 !important;
    border-radius: 9999px !important;
    padding-left: 20px !important;
    padding-right: 20px !important;
    justify-content: center !important;
    align-items: center !important;
  }}
  .ff-select-fill .q-field__native {{
    color: inherit !important;
  }}
  .ff-select-fill .q-field__control-container {{
    color: var(--color-neutral-300) !important;
  }}
  .ff-select-fill .q-field__append {{
    color: rgba(255, 255, 255, 0.54) !important;
  }}
  .ff-select-fill .q-select__dropdown-icon {{
    padding-left: 7px !important;
    padding-right: 7px !important;
    align-items: flex-end !important;
  }}

  /* Input text colors */
  .q-field__native,
  .q-field__prefix,
  .q-field__suffix,
  .q-field__input {{
    color: #ffffff !important;
  }}
  .q-field__native::placeholder {{ color: #64748b !important; }}

  /* Dropdown menus */
  .q-menu {{
    background: #171717 !important; /* neutral-900 */
    border: 1px solid #262626 !important; /* neutral-800 */
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5) !important;
  }}
  .q-menu .q-item {{ color: #e5e7eb !important; }}
  .q-menu .q-item__label {{ color: #e5e7eb !important; }}
  .q-menu .q-item--active {{ color: var(--brand-primary) !important; background: rgba(255, 197, 36, 0.1); }}
  .q-menu .q-item:hover {{ background: #262626 !important; }}

  /* Buttons & focus */
  .q-btn.text-primary, .q-btn .text-primary {{ color: #e5e7eb !important; }}
  .q-btn {{ color: inherit; }}
  .q-focus-helper {{
    background: unset !important;
    background-color: unset !important;
    border-radius: 0px !important;
    border-top-left-radius: 0px !important;
    border-top-right-radius: 0px !important;
    border-bottom-right-radius: 0px !important;
    border-bottom-left-radius: 0px !important;
    color: var(--color-neutral-100) !important;
    border-color: var(--color-neutral-400) !important;
    border-image: none !important;
    border-style: solid !important;
    border-width: 1px !important;
    padding-left: 0px !important;
    padding-right: 0px !important;
  }}

  .q-btn.ff-btn-finalize-invoice {{
    padding-left: 19px !important;
    padding-right: 19px !important;
    padding-top: 14px !important;
    padding-bottom: 14px !important;
    border-radius: 19px !important;
    border-top-left-radius: 19px !important;
    border-top-right-radius: 19px !important;
    border-bottom-right-radius: 19px !important;
    border-bottom-left-radius: 19px !important;
    border-style: solid !important;
  }}

  /* Header actions */
  .q-btn.ff-btn-new-invoice {{
    background: unset !important;
    background-color: unset !important;
    background-image: none !important;
    background-clip: unset !important;
    -webkit-background-clip: unset !important;
    color: var(--brand-accent) !important;
    border-color: var(--brand-accent) !important;
    border-image: none !important;
    box-shadow: none !important;
  }}
  .q-btn.ff-btn-new-invoice .q-btn__content span.block {{ color: var(--brand-primary) !important; }}
  .q-btn.ff-user-chip {{
    background: unset !important;
    background-color: unset !important;
    background-image: none !important;
    color: rgba(255, 255, 255, 1) !important;
    border-image: none !important;
  }}
  .q-btn.ff-user-chip .q-btn__content {{
    color: rgba(255, 255, 255, 1) !important;
  }}
  .ff-sidebar-logo,
  .ff-sidebar-logo .q-img__container {{
    border-radius: 0px !important;
  }}

  /* Notifications */
  .q-notification {{
    background: #0f172a !important;
    color: #f1f5f9 !important;
    border: 1px solid #1e293b !important;
    border-radius: 12px;
  }}

  /* Checkboxes */
  .q-checkbox__inner--truthy .q-checkbox__bg {{ background: var(--brand-primary); border-color: var(--brand-primary); }}
  .q-checkbox__inner--falsy .q-checkbox__bg {{ border-color: #4b5563; }}
  .q-checkbox__label {{ color: #e5e7eb; }}

  /* Utilities */
  input:-webkit-autofill {{
    -webkit-text-fill-color: #ffffff !important;
    box-shadow: 0 0 0px 1000px #1f2937 inset !important;
  }}
</style>
"""

# Panels / cards
C_CARD = "bg-neutral-900/80 border border-neutral-800/80 rounded-lg shadow-sm"
C_CARD_HOVER = "transition-colors hover:bg-neutral-900/90 hover:border-neutral-700/80"

# Glass cards reuse the base card styles to avoid drift.
C_GLASS_CARD = C_CARD
C_GLASS_CARD_HOVER = C_CARD_HOVER

# Buttons
C_BTN_PRIM = "!bg-neutral-800 !text-white hover:bg-neutral-700 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-all focus-visible:ring-2 focus-visible:ring-[#ffc524]/40"
C_BTN_SEC = "!bg-neutral-900 !text-neutral-200 border border-neutral-800 hover:border-neutral-700 hover:bg-neutral-800 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[#ffc524]/20"
C_BTN_ORANGE = "ff-btn-new-invoice rounded-full justify-center items-center !bg-transparent hover:!bg-transparent shadow-none border border-[var(--brand-accent)] !text-[var(--brand-accent)] active:scale-[0.98] px-4 py-2 text-sm font-semibold transition-all focus-visible:ring-2 focus-visible:ring-[#ffc524]/40"

# Inputs
C_INPUT = "w-full text-sm transition-all"
C_INPUT_ROUNDED = "rounded-full border border-neutral-700 bg-neutral-900/80"

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
