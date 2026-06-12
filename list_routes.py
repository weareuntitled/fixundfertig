from nicegui import app, ui
for r in app.routes:
    p = getattr(r, "path", getattr(r, "paths", None))
    if p:
        print(p)
