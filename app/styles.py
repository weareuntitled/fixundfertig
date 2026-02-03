# =========================
# APP/STYLES.PY
# =========================

# --- STYLE SYSTEM (Clean admin look) ---
C_BG = "bg-[#F8FAFC] text-slate-900 min-h-screen"
C_CONTAINER = "w-full max-w-6xl mx-auto px-5 py-6 gap-5"
C_FONT_STACK = '"Inter", "IBM Plex Sans", "Segoe UI", system-ui, sans-serif'
C_NUMERIC = "tabular-nums"

APP_FONT_CSS = f"""
<style>
  :root, body, .q-body {{
    font-family: {C_FONT_STACK};
    letter-spacing: -0.01em;
  }}
</style>
"""

# Panels / cards
C_CARD = "bg-white border border-slate-200/80 rounded-lg shadow-sm"
C_CARD_HOVER = "hover:border-slate-300/80 hover:shadow-md transition-all duration-150"
C_GLASS_CARD = "bg-white border border-slate-200/80 rounded-lg shadow-sm"
C_GLASS_CARD_HOVER = "hover:border-slate-300/80 hover:shadow-md transition-all duration-150"

# Buttons
C_BTN_PRIM = "!bg-slate-900 !text-white hover:bg-slate-800 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-all focus-visible:ring-2 focus-visible:ring-slate-900/25"
C_BTN_SEC = "!bg-white !text-slate-700 border border-slate-200 hover:border-slate-300 hover:bg-slate-50 active:scale-[0.98] rounded-lg px-4 py-2 text-sm font-semibold transition-all focus-visible:ring-2 focus-visible:ring-slate-900/10"

# Inputs
C_INPUT = "border-slate-200 bg-white rounded-lg text-sm px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-slate-900/15 focus-visible:border-slate-400 w-full transition-all"

# Badges
C_BADGE_GREEN = "bg-emerald-50 text-emerald-700 border border-emerald-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_BLUE = "bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_GRAY = "bg-slate-100 text-slate-600 border border-slate-200 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_YELLOW = "bg-amber-50 text-amber-700 border border-amber-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"
C_BADGE_RED = "bg-rose-50 text-rose-700 border border-rose-100 px-2 py-0.5 rounded-full text-xs font-medium text-center"

# Typography
C_PAGE_TITLE = "text-2xl font-semibold text-slate-900 tracking-tight"
C_SECTION_TITLE = "text-sm font-semibold text-slate-600"

# Tables
C_TABLE_HEADER = "w-full bg-slate-50/80 border-b border-slate-200 px-4 py-3 gap-4"
C_TABLE_ROW = "w-full px-4 py-3 border-b border-slate-100 items-center gap-4 hover:bg-slate-50/70 transition-colors"

# Legacy header tokens (kept so other components don’t break)
C_HEADER = "bg-white border-b border-slate-200 h-16 px-6 flex items-center justify-between sticky top-0 z-50"
C_BRAND_BADGE = "bg-blue-600 text-white p-2 rounded-lg shadow-sm"
C_NAV_ITEM = "text-slate-600 hover:text-slate-900 px-3 py-2 rounded-lg hover:bg-slate-100 transition-all duration-150"
C_NAV_ITEM_ACTIVE = "text-slate-900 px-3 py-2 rounded-lg bg-slate-100 transition-all duration-150"
