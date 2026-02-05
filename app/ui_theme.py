from nicegui import ui

from styles import APP_FONT_CSS

_THEME_APPLIED = False


def apply_global_ui_theme() -> None:
    global _THEME_APPLIED
    if _THEME_APPLIED:
        return
    ui.add_head_html(
        "<script>window.False=false;window.True=true;window.None=null;</script>",
        shared=True,
    )
    ui.add_head_html(APP_FONT_CSS, shared=True)
    # Quasar token colors (our real look is driven via Tailwind + CSS in APP_FONT_CSS)
    ui.colors(primary="#0f172a", secondary="#64748b", accent="#f59e0b", dark="#0f172a")
    _THEME_APPLIED = True
