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


def _extract_compose_port(compose: str) -> str:
    lines = compose.splitlines()
    in_app = False
    in_ports = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("app:"):
            in_app = True
            in_ports = False
            continue
        if in_app and stripped and not line.startswith(" "):
            in_app = False
            in_ports = False
        if in_app and stripped.startswith("ports:"):
            in_ports = True
            continue
        if in_ports:
            match = re.search(r"\"?\d+:(\d+)\"?", stripped)
            if match:
                return match.group(1)
    raise AssertionError("docker-compose.prod.yml missing app port mapping")


def test_app_ports_are_consistent() -> None:
    caddy_port = _extract_caddy_port(_read(ROOT / "Caddyfile"))
    dockerfile_port = _extract_dockerfile_port(_read(ROOT / "Dockerfile"))
    app_port = _extract_app_port(_read(ROOT / "app" / "main.py"))
    compose_port = _extract_compose_port(_read(ROOT / "docker-compose.prod.yml"))

    expected = {"8000"}
    assert caddy_port in expected, f"Caddyfile expected port 8000, got {caddy_port}"
    assert dockerfile_port in expected, (
        f"Dockerfile expected EXPOSE 8000, got {dockerfile_port}"
    )
    assert app_port in expected, f"app/main.py expected port 8000, got {app_port}"
    assert compose_port in expected, (
        f"docker-compose.prod.yml expected container port 8000, got {compose_port}"
    )
