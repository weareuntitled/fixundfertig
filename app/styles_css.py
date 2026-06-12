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
# Body: Inter (400/500/600). Display: Newsreader (warme Editorial-Serif) — for page titles
# and large monetary numbers. Costs nothing, immediately reads "intentional, not default SaaS".
C_FONT_STACK = '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
C_DISPLAY_STACK = '"Newsreader", "Iowan Old Style", "Apple Garamond", "Baskerville", "Times New Roman", Georgia, serif'
C_NUMERIC = "tabular-nums"

# WICHTIG: Alle CSS-Klammern {{ }} sind doppelt, damit Python sie nicht als Variablen liest!
APP_FONT_CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap" rel="stylesheet">
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

    /* Brand accent — deepened to "ink" (indigo-900) as the *primary* signal color.
       Indigo-500 stays as secondary highlight. This kills the "default SaaS" look. */
    --brand-primary: #4338ca;     /* indigo-700 — buttons, active states */
    --brand-accent: #312e81;      /* indigo-900 — ink, used sparingly */
    --brand-soft: #6366f1;        /* indigo-500 — secondary, glows, icons */
    --brand-subtle: #eef2ff;      /* indigo-50 */
    --brand-tint: #f5f3ff;        /* violet-50 — hero background hint */

    --ff-ring: rgba(67, 56, 202, 0.18);
  }}

  body, .q-body, .nicegui-content {{
    background-color: var(--ff-bg) !important;
    background-image:
      /* Atmospheric orb (top-right) — soft ink wash, fixes "flat empty background" anti-pattern. */
      radial-gradient(ellipse 60% 40% at 90% -10%, rgba(67, 56, 202, 0.10) 0%, transparent 55%),
      /* Counter-orb (bottom-left) — warm tint, prevents the page from feeling cold. */
      radial-gradient(ellipse 50% 35% at 5% 95%, rgba(244, 114, 182, 0.05) 0%, transparent 55%),
      /* Subtle vertical wash so content reads above the page, not on it. */
      linear-gradient(180deg, #ffffff 0%, #f8fafc 100%) !important;
    background-attachment: fixed !important;
    color: var(--ff-text) !important;
    padding-left: env(safe-area-inset-left, 0px);
    padding-right: env(safe-area-inset-right, 0px);
  }}

  /* Display family — opt-in via .ff-display. Optical-size aware via 'opsz'. */
  .ff-display, .ff-display-number {{
    font-family: {C_DISPLAY_STACK};
    font-feature-settings: "ss01", "ss02", "kern";
    letter-spacing: -0.022em;
  }}
  .ff-display-number {{
    font-variant-numeric: tabular-nums lining-nums;
    font-feature-settings: "ss01", "lnum", "tnum";
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
    border-radius: 0.5rem;
  }}
  .q-field--outlined .q-field__control:before {{
    border-color: var(--ff-border) !important;
    border-width: 1px !important;
  }}
  .q-field--outlined.q-field--focused .q-field__control:after {{
    border-color: var(--brand-primary) !important;
    border-width: 1.5px !important;
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
    border-radius: 0.625rem;
    box-shadow: 0 12px 28px rgba(15,23,42,0.08), 0 2px 6px rgba(15,23,42,0.04) !important;
  }}
  .q-menu .q-item {{ color: var(--ff-text) !important; }}
  .q-menu .q-item__label {{ color: var(--ff-text) !important; }}
  .q-menu .q-item:hover {{ background: var(--ff-surface-2) !important; }}
  .q-menu .q-item--active {{
    background: var(--brand-subtle) !important;
    color: var(--brand-primary) !important;
  }}

  /* Notifications */
  .q-notification {{
    background: var(--ff-surface) !important;
    color: var(--ff-text) !important;
    border: 1px solid var(--ff-border) !important;
    border-left: 3px solid var(--brand-primary) !important;
    border-radius: 0.625rem;
    box-shadow: 0 12px 28px rgba(15,23,42,0.08), 0 2px 6px rgba(15,23,42,0.04) !important;
    animation: ff-slide-up 0.22s cubic-bezier(0.4, 0, 0.2, 1) both;
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

  /* Active nav button — filled ink pill, override Quasar flat */
  .q-btn.ff-nav-btn.ff-nav-active {{
    background: var(--brand-primary) !important;
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
    color: var(--brand-primary);
  }}
  .ff-mobile-nav-item .ff-nav-dot {{
    width: 34px; height: 28px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.12s ease;
  }}
  .ff-mobile-nav-item.ff-nav-active .ff-nav-dot {{
    background: var(--brand-subtle);
  }}

  /* Mobile: ensure adequate touch targets */
  @media (max-width: 767px) {{
    .q-btn {{ min-height: 44px !important; }}
    .q-field__control {{ min-height: 48px !important; }}
  }}

  /* ===== KEY VISUALS ===== */

  /* Hero panel: top-of-page focus area with a large editorial number.
     Hairline-bottom instead of card border. Lives above the content rhythm. */
  .ff-hero {{
    position: relative;
    padding: 1.5rem 1.75rem 1.25rem;
    background:
      radial-gradient(ellipse 70% 100% at 100% 0%, rgba(67,56,202,0.06) 0%, transparent 60%),
      #ffffff;
    border: 1px solid var(--ff-border);
    border-radius: 1rem;
    box-shadow: 0 1px 0 rgba(15,23,42,0.04);
    overflow: hidden;
  }}
  .ff-hero::after {{
    /* hairline baseline */
    content: "";
    position: absolute;
    left: 1.75rem; right: 1.75rem; bottom: 0.5rem;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--ff-border) 20%, var(--ff-border) 80%, transparent);
    opacity: 0.6;
  }}
  .ff-hero-eyebrow {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--brand-primary);
  }}
  .ff-hero-value {{
    font-family: {C_DISPLAY_STACK};
    font-variant-numeric: tabular-nums lining-nums;
    font-size: clamp(2.25rem, 5vw, 3.25rem);
    font-weight: 500;
    letter-spacing: -0.025em;
    line-height: 1;
    color: var(--ff-text);
    margin-top: 0.5rem;
  }}
  .ff-hero-meta {{
    margin-top: 0.5rem;
    font-size: 12px;
    color: var(--ff-muted);
  }}

  /* Empty state — editorial receipt/invoice aesthetic. Mono caption, single quote. */
  .ff-empty {{
    padding: 2.5rem 1.5rem;
    text-align: center;
    background: linear-gradient(180deg, #ffffff 0%, var(--ff-surface-2) 100%);
    border: 1px dashed var(--ff-border-strong);
    border-radius: 1rem;
  }}
  .ff-empty-glyph {{
    display: inline-flex;
    width: 44px; height: 44px;
    align-items: center; justify-content: center;
    border-radius: 9999px;
    background: var(--brand-subtle);
    color: var(--brand-primary);
    margin-bottom: 0.75rem;
  }}
  .ff-empty-title {{
    font-family: {C_DISPLAY_STACK};
    font-size: 1.25rem;
    font-weight: 500;
    letter-spacing: -0.01em;
    color: var(--ff-text);
  }}
  .ff-empty-body {{
    margin-top: 0.35rem;
    font-size: 13px;
    color: var(--ff-muted);
    max-width: 36ch;
    margin-left: auto; margin-right: auto;
  }}

  /* "Section header" — small uppercase eyebrow + thin rule, editorial. Replaces the
     default medium-weight sans title. */
  .ff-eyebrow {{
    display: flex; align-items: baseline; justify-content: space-between; gap: 1rem;
    margin-bottom: 0.75rem;
  }}
  .ff-eyebrow-label {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ff-muted);
  }}
  .ff-eyebrow-rule {{
    flex: 1; height: 1px;
    background: linear-gradient(90deg, var(--ff-border) 0%, transparent 100%);
  }}
  .ff-eyebrow-aside {{
    font-size: 11px; color: var(--ff-muted-2);
  }}
</style>
"""
