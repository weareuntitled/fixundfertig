# =========================
# APP/STYLES.PY
# =========================

# --- STYLE SYSTEM (Clean admin look) ---
C_BG = "bg-slate-950 text-slate-100 min-h-screen"
C_CONTAINER = "w-full max-w-6xl mx-auto px-5 py-6 gap-5"
C_FONT_STACK = '"Inter", "IBM Plex Sans", "Segoe UI", system-ui, sans-serif'
C_NUMERIC = "tabular-nums"

APP_FONT_CSS = f"""
<style>
  :root, body, .q-body {{
    font-family: {C_FONT_STACK};
    letter-spacing: -0.01em;
    color-scheme: dark;
    --brand-primary: #f59e0b;
    --brand-accent: #fbbf24;
    --surface-0: #020617;
    --surface-1: #0f172a;
    --surface-2: #111827;
    --text-muted: #94a3b8;
  }}
  a {{
    color: var(--brand-primary);
  }}
</style>
"""

# Panels / cards
C_CARD = "bg-slate-900 border border-slate-800/80 rounded-lg shadow-sm"
C_CARD_HOVER = "hover:border-slate-700/80 hover:bg-slate-900/70 transition-all duration-150"
C_GLASS_CARD = "bg-slate-900 border border-slate-800/80 rounded-lg shadow-sm"
C_GLASS_CARD_HOVER = "hover:border-slate-700/80 hover:bg-slate-900/70 transition-all duration-150"

# Buttons
C_BTN_PRIM = "!bg-amber-500 !text-slate-950 hover:bg-amber-400 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-all focus-visible:ring-2 focus-visible:ring-amber-300/40"
C_BTN_SEC = "!bg-slate-900 !text-slate-200 border border-slate-800 hover:border-slate-700 hover:bg-slate-800 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold transition-all focus-visible:ring-2 focus-visible:ring-amber-400/20"

# Inputs
C_INPUT = "border-slate-800 bg-slate-900 text-slate-100 placeholder:text-slate-500 rounded-lg text-sm px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-amber-400/30 focus-visible:border-amber-400/40 w-full transition-all"

# Badges
C_BADGE_GREEN = "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_BLUE = "bg-sky-500/10 text-sky-300 border border-sky-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_GRAY = "bg-slate-800 text-slate-300 border border-slate-700 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_YELLOW = "bg-amber-500/10 text-amber-300 border border-amber-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_RED = "bg-rose-500/10 text-rose-300 border border-rose-500/20 px-2 py-0.5 rounded-full text-xs font-medium text-center"

# Typography
C_PAGE_TITLE = "text-2xl font-semibold text-slate-100 tracking-tight"
C_SECTION_TITLE = "text-sm font-semibold text-slate-400"

# Tables
C_TABLE_HEADER = "w-full bg-slate-900/80 border-b border-slate-800 px-4 py-3 gap-4"
C_TABLE_ROW = "w-full px-4 py-3 border-b border-slate-800 items-center gap-4 hover:bg-slate-900/70 transition-colors"

# Legacy header tokens (kept so other components don’t break)
C_HEADER = "bg-slate-950 border-b border-slate-800 h-16 px-6 flex items-center justify-between sticky top-0 z-50"
C_BRAND_BADGE = "bg-amber-500 text-slate-950 p-2 rounded-lg shadow-sm"
C_NAV_ITEM = "text-slate-400 hover:text-slate-100 px-3 py-2 rounded-lg hover:bg-slate-900 transition-all duration-150"
C_NAV_ITEM_ACTIVE = "text-amber-300 px-3 py-2 rounded-lg bg-slate-900 transition-all duration-150"
