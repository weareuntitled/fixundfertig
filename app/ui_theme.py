import os

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
    # Force browser to revalidate / no cache when FF_NO_CACHE=1 (e.g. after design changes)
    if (os.getenv("FF_NO_CACHE") or "").strip() == "1":
        ui.add_head_html(
            '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">'
            '<meta http-equiv="Pragma" content="no-cache">'
            '<meta http-equiv="Expires" content="0">',
            shared=True,
        )
    ui.add_head_html(APP_FONT_CSS, shared=True)
    # Quasar token colors (our real look is driven via Tailwind + CSS in APP_FONT_CSS)
    ui.colors(primary="#0f172a", secondary="#64748b", accent="#f59e0b", dark="#0f172a")
    # Allow browser DevTools / right-click Inspect when requested (e.g. local dev)
    if (os.getenv("FF_ALLOW_BROWSER_INSPECT") or "").strip() == "1":
        ui.add_head_html(
            """
            <script>
            (function() {
              function allowContextMenu() {
                try { document.oncontextmenu = null; } catch (e) {}
                try { if (document.body) document.body.oncontextmenu = null; } catch (e) {}
              }
              if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', allowContextMenu);
              } else {
                allowContextMenu();
              }
              document.addEventListener('contextmenu', allowContextMenu, true);
            })();
            </script>
            """,
            shared=True,
        )
    _THEME_APPLIED = True
