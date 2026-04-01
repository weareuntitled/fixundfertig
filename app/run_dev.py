"""Dev launcher: sets local environment variables before starting the app."""
import os
import runpy

os.environ.setdefault("FF_ENV", "development")
os.environ.setdefault("FF_ALLOW_LOCALHOST", "1")
os.environ.setdefault("FF_ALLOW_BROWSER_INSPECT", "1")

runpy.run_path("main.py", run_name="__main__")
