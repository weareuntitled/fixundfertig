from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from datetime import datetime


SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".next", ".pytest_cache"
}


@dataclass
class FuncBlock:
    name: str
    kind: str  # route | render | block
    start: int  # 1-indexed inclusive
    end: int    # 1-indexed inclusive
    src: str


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def find_pages_py(root: Path) -> Path:
    cands: List[Path] = []
    for p in root.rglob("pages.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        cands.append(p)

    if not cands:
        raise SystemExit("Kein pages.py gefunden. Starte im Projektroot oder gib den Pfad als Argument an.")

    def score(p: Path) -> int:
        s = _read(p)
        sc = 0
        if "def render_" in s:
            sc += 10
        if "@ui.page" in s or "ui.page(" in s:
            sc += 10
        if "nicegui" in s or "from nicegui import ui" in s:
            sc += 5
        if "src" in p.parts or "app" in p.parts:
            sc += 2
        sc += max(0, 10 - len(p.parts))
        return sc

    cands.sort(key=lambda p: score(p), reverse=True)
    return cands[0]


def is_ui_page_decorated(fn: ast.AST) -> bool:
    decs = getattr(fn, "decorator_list", []) or []
    for dec in decs:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute) and target.attr == "page":
            if isinstance(target.value, ast.Name) and target.value.id == "ui":
                return True
    return False


def get_block_range(fn: ast.AST) -> Tuple[int, int]:
    lineno = getattr(fn, "lineno", None)
    end_lineno = getattr(fn, "end_lineno", None)
    if lineno is None or end_lineno is None:
        raise SystemExit("end_lineno fehlt. Bitte Python 3.8 oder neuer verwenden.")
    start = lineno
    decs = getattr(fn, "decorator_list", []) or []
    for dec in decs:
        dline = getattr(dec, "lineno", None)
        if dline is not None:
            start = min(start, dline)
    return start, end_lineno


def slice_lines(lines: List[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_safe_destination(pkg_dir: Path) -> None:
    # Avoid overwriting existing pages package unless FORCE_SPLIT_PAGES=1
    if pkg_dir.exists():
        force = (Path.cwd() / ".").exists() and (Path.cwd() / ".")  # dummy to keep type checkers quiet
        force_env = __import__("os").environ.get("FORCE_SPLIT_PAGES", "").strip()
        if force_env != "1":
            raise SystemExit(
                f"Zielordner existiert bereits: {pkg_dir}\n"
                f"Abbruch, um nichts zu überschreiben.\n"
                f"Wenn du überschreiben willst, setze FORCE_SPLIT_PAGES=1 und starte erneut."
            )


def main() -> None:
    import sys
    import os

    root = Path(".").resolve()

    if len(sys.argv) > 1:
        pages_py = Path(sys.argv[1]).expanduser().resolve()
        if not pages_py.exists():
            raise SystemExit(f"Pfad existiert nicht: {pages_py}")
    else:
        pages_py = find_pages_py(root)

    src = _read(pages_py)
    lines = src.splitlines(keepends=True)

    mod = ast.parse(src)

    extracted: List[FuncBlock] = []
    for node in mod.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name

        kind: Optional[str] = None
        if is_ui_page_decorated(node):
            kind = "route"
        elif name.startswith("render_"):
            kind = "render"
        elif name.endswith("_block"):
            kind = "block"

        if kind is None:
            continue

        start, end = get_block_range(node)
        extracted.append(FuncBlock(
            name=name,
            kind=kind,
            start=start,
            end=end,
            src=slice_lines(lines, start, end),
        ))

    if not extracted:
        raise SystemExit("Keine @ui.page Funktionen, render_* oder *_block Funktionen gefunden.")

    base_dir = pages_py.parent
    pkg_dir = base_dir / "pages"
    comp_dir = pkg_dir / "components"

    ensure_safe_destination(pkg_dir)

    # Rename original pages.py so it does not shadow the new package
    legacy_base = base_dir / "pages_legacy_full.py"
    legacy_path = legacy_base
    if legacy_path.exists():
        legacy_path = base_dir / f"pages_legacy_full_{_timestamp()}.py"
    pages_py.rename(legacy_path)

    # Build shared by removing extracted blocks
    ranges = sorted([(b.start, b.end) for b in extracted], key=lambda t: (t[0], t[1]))
    keep: List[str] = []
    cur = 1
    for start, end in ranges:
        if cur < start:
            keep.extend(lines[cur - 1 : start - 1])
        cur = end + 1
    if cur <= len(lines):
        keep.extend(lines[cur - 1 :])

    shared_header = (
        "# Auto generated by scripts/split_pages.py\n"
        "# Shared imports, constants and helpers from the former pages.py\n\n"
    )
    shared_content = shared_header + "".join(keep).lstrip("\n")
    write_file(pkg_dir / "_shared.py", shared_content)

    # Blocks module
    blocks = [b for b in extracted if b.kind == "block"]
    if blocks:
        blocks_content = (
            "from __future__ import annotations\n"
            "from .._shared import *\n\n"
            "# Auto generated blocks\n\n"
        )
        blocks_content += "\n\n".join([b.src.strip("\n") for b in blocks]) + "\n"
        write_file(comp_dir / "blocks.py", blocks_content)
        write_file(comp_dir / "__init__.py", "from .blocks import *\n")

    # Render modules, one file per render_*
    renders = [b for b in extracted if b.kind == "render"]
    render_modules: Dict[str, str] = {}
    for b in renders:
        suffix = b.name[len("render_"):] or b.name
        modname = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in suffix).lower()
        render_modules[b.name] = modname
        mod_content = (
            "from __future__ import annotations\n"
            "from ._shared import *\n"
        )
        if blocks:
            mod_content += "from .components.blocks import *\n"
        mod_content += "\n# Auto generated page renderer\n\n"
        mod_content += b.src.strip("\n") + "\n"
        write_file(pkg_dir / f"{modname}.py", mod_content)

    # Routes module
    routes = [b for b in extracted if b.kind == "route"]
    if routes:
        imports = []
        for fn_name, modname in sorted(render_modules.items()):
            imports.append(f"from .{modname} import {fn_name}")
        routes_content = (
            "from __future__ import annotations\n"
            "from ._shared import *\n"
        )
        if blocks:
            routes_content += "from .components.blocks import *\n"
        if imports:
            routes_content += "\n" + "\n".join(imports) + "\n"
        routes_content += "\n# Auto generated routes\n\n"
        routes_content += "\n\n".join([b.src.strip("\n") for b in routes]) + "\n"
        write_file(pkg_dir / "routes.py", routes_content)

    # Package __init__.py
    exports = []
    for fn_name, modname in sorted(render_modules.items()):
        exports.append(f"from .{modname} import {fn_name}")
    init = (
        "from __future__ import annotations\n"
        "from ._shared import *\n"
    )
    if blocks:
        init += "from .components.blocks import *\n"
    if exports:
        init += "\n" + "\n".join(exports) + "\n"
    init += "\n# Import routes for side effects. Registers @ui.page decorators\n"
    if routes:
        init += "from . import routes as _routes\n"
    init += "\n"
    write_file(pkg_dir / "__init__.py", init)

    print("Fertig.")
    print(f"Backup: {legacy_path}")
    print(f"Neues Package: {pkg_dir}")
    print("Wichtig: Stelle sicher, dass dein Entry Point das Package importiert, zB: import pages")
    print("Wenn du das alte pages.py importiert hast, ersetze es durch import pages oder from pages import ...")


if __name__ == "__main__":
    main()
