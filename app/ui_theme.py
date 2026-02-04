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
    ui.colors(primary="#ffc524", secondary="#E0E0E0", accent="#a37200", dark="#0a0b0d")
    _THEME_APPLIED = True
