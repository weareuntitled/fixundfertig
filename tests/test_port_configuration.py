from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_caddy_port(caddyfile: str) -> str:
    match = re.search(r"reverse_proxy\s+app:(\d+)", caddyfile)
    assert match, "Caddyfile missing reverse_proxy app port"
    return match.group(1)


def _extract_dockerfile_port(dockerfile: str) -> str:
    match = re.search(r"^EXPOSE\s+(\d+)\s*$", dockerfile, re.MULTILINE)
    assert match, "Dockerfile missing EXPOSE port"
    return match.group(1)


def _extract_app_port(app_main: str) -> str:
    match = re.search(r"\bport\s*=\s*(\d+)", app_main)
    assert match, "app/main.py missing ui.run port"
    return match.group(1)


def _extract_compose_app_port(compose: str) -> str | None:
    """Return the container-side port from the `app` service only (not Caddy/n8n).

    Many prod stacks do not publish `app` ports (only Caddy exposes 80/443). In that
    case return None and skip the compose assertion.
    """
    lines = compose.splitlines()
    in_app = False
    base_indent: int | None = None
    in_ports = False
    for line in lines:
        m_svc = re.match(r"^(\s*)app:\s*$", line)
        if m_svc:
            in_app = True
            base_indent = len(m_svc.group(1))
            in_ports = False
            continue
        if not in_app or base_indent is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == base_indent and stripped.endswith(":") and not stripped.startswith("app:"):
            in_app = False
            in_ports = False
            continue
        if stripped.startswith("ports:") and indent > base_indent:
            in_ports = True
            continue
        if in_ports:
            match = re.search(r"\"?\d+:(\d+)\"?", stripped)
            if match:
                return match.group(1)
            if stripped.endswith(":") and not stripped.startswith("-"):
                in_ports = False
    return None


def test_app_ports_are_consistent() -> None:
    caddy_port = _extract_caddy_port(_read(ROOT / "Caddyfile"))
    dockerfile_port = _extract_dockerfile_port(_read(ROOT / "Dockerfile"))
    app_port = _extract_app_port(_read(ROOT / "app" / "main.py"))
    compose_app_port = _extract_compose_app_port(_read(ROOT / "docker-compose.prod.yml"))

    expected = {"8000"}
    assert caddy_port in expected, f"Caddyfile expected port 8000, got {caddy_port}"
    assert dockerfile_port in expected, (
        f"Dockerfile expected EXPOSE 8000, got {dockerfile_port}"
    )
    assert app_port in expected, f"app/main.py expected port 8000, got {app_port}"
    if compose_app_port is not None:
        assert compose_app_port in expected, (
            f"docker-compose.prod.yml app service expected container port 8000, got {compose_app_port}"
        )
