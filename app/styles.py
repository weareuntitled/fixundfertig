

# -------------------------
# Design system class tokens
# -------------------------

STYLE_BG = "bg-[#f8fafc] text-slate-900 min-h-screen"
STYLE_CONTAINER = "w-full max-w-6xl mx-auto px-3 md:px-6 py-4 md:py-6 gap-4 md:gap-6"

# Card: hairline border > soft shadow. The shadow is "ink from above", not a generic elevation.
STYLE_CARD = (
    "bg-white border border-slate-200 rounded-xl "
    "shadow-[0_1px_0_rgba(15,23,42,0.04),0_1px_3px_rgba(15,23,42,0.04)]"
)
STYLE_CARD_HOVER = (
    "transition-all duration-150 hover:shadow-[0_1px_0_rgba(15,23,42,0.04),0_4px_12px_rgba(15,23,42,0.06)] "
    "hover:border-slate-300"
)

# Page title in Newsreader (display serif). This is the single most distinctive choice in the system.
STYLE_HEADING = "text-base font-semibold tracking-tight text-slate-900"
STYLE_PAGE_TITLE = "ff-display text-[1.75rem] md:text-[2rem] font-medium tracking-[-0.02em] text-slate-900 leading-[1.1]"
STYLE_SECTION_TITLE = "text-[11px] font-semibold text-slate-500 uppercase tracking-[0.08em]"
STYLE_TEXT_MUTED = "text-xs text-slate-500"
STYLE_TEXT_SUBTLE = "text-xs text-slate-500"
STYLE_TEXT_HINT = "text-xs text-slate-400"
STYLE_TEXT_ERROR = "text-xs text-rose-600"

# Display number — large editorial-serif figure (used for hero KPIs, totals).
STYLE_DISPLAY_NUMBER = (
    "ff-display-number text-[2.25rem] md:text-[2.75rem] font-medium leading-none "
    "tracking-[-0.025em] text-slate-900"
)

STYLE_BTN_PRIMARY = (
    # Ink (indigo-700) — deeper, more "decided" than the default SaaS indigo-600.
    "bg-indigo-700 text-white hover:bg-indigo-800 active:bg-indigo-900 active:scale-[0.99] "
    "rounded-md px-3 py-1.5 text-[13px] font-medium shadow-sm transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-700/30"
)
STYLE_BTN_SECONDARY = (
    "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 "
    "active:scale-[0.99] rounded-md px-3 py-1.5 text-[13px] font-medium shadow-sm transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/30"
)
STYLE_BTN_GHOST = (
    "text-slate-600 hover:text-slate-900 hover:bg-slate-100 active:scale-[0.99] "
    "rounded-md px-3 py-1.5 text-[13px] font-medium transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/30"
)
STYLE_BTN_MUTED = STYLE_BTN_GHOST
STYLE_BTN_DANGER = (
    "bg-rose-600 text-white hover:bg-rose-700 active:scale-[0.99] rounded-md px-3 py-1.5 "
    "text-[13px] font-medium shadow-sm transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/30"
)
STYLE_BTN_ACCENT = (
    "bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 "
    "active:scale-[0.99] rounded-md px-3 py-1.5 text-[13px] font-medium transition-all "
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/40"
)

STYLE_INPUT = "w-full text-sm"
STYLE_INPUT_ROUNDED = "rounded-full"

# Hero / Empty-state component classes (used by ui_components.ff_hero / ff_empty_state).
STYLE_HERO = "ff-hero"
STYLE_HERO_EYEBROW = "ff-hero-eyebrow"
STYLE_HERO_VALUE = "ff-hero-value"
STYLE_HERO_META = "ff-hero-meta"
STYLE_EMPTY = "ff-empty"
STYLE_EMPTY_TITLE = "ff-empty-title"
STYLE_EMPTY_BODY = "ff-empty-body"
STYLE_EYEBROW = "ff-eyebrow"
STYLE_EYEBROW_LABEL = "ff-eyebrow-label"
STYLE_EYEBROW_RULE = "ff-eyebrow-rule"
STYLE_EYEBROW_ASIDE = "ff-eyebrow-aside"

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
