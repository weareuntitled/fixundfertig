"""Check the deployment CLI without connecting to a real host."""
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("override, succeeds", [
    ({}, True),
    ({"TEST_CONTAINER": "old"}, False),
    ({"TEST_IMAGE": "old"}, False),
    ({"TEST_PUBLIC": "old"}, False),
    ({"TEST_FRONTEND": "old"}, False),
    ({"TEST_HEALTH": "unhealthy"}, False),
    ({"TEST_STATUS": "error"}, False),
])
def test_deployment_check_compares_all_running_components(tmp_path, override, succeeds):
    ssh = tmp_path / "ssh"
    ssh.write_text('''#!/usr/bin/env python3
import os, sys
command = sys.argv[-1]
key = "TEST_SOURCE" if "git -C" in command else "TEST_CONTAINER" if "printenv" in command else "TEST_IMAGE" if "Config.Labels" in command else "TEST_HEALTH"
print(os.environ[key])
''')
    curl = tmp_path / "curl"
    curl.write_text('''#!/usr/bin/env python3
import json, os, sys
if sys.argv[-1].endswith("/healthz"):
    print(json.dumps({"status": os.environ["TEST_STATUS"], "revision": os.environ["TEST_PUBLIC"]}))
else:
    print('<meta name="app-revision" content="' + os.environ["TEST_FRONTEND"] + '" />')
''')
    ssh.chmod(0o755)
    curl.chmod(0o755)
    env = {
        **os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "TEST_SOURCE": "a" * 40, "TEST_CONTAINER": "a" * 40, "TEST_IMAGE": "a" * 40,
        "TEST_PUBLIC": "a" * 40, "TEST_FRONTEND": "a" * 40,
        "TEST_HEALTH": "healthy", "TEST_STATUS": "ok", **override,
    }
    script = Path(__file__).resolve().parents[1] / "scripts/check-deployment.sh"
    result = subprocess.run(
        ["bash", str(script), "test-host", "https://app.example.test", "a" * 40],
        env=env, text=True, capture_output=True, timeout=10,
    )
    assert (result.returncode == 0) is succeeds, result.stdout + result.stderr
    assert "source=" in result.stdout
    assert "frontend=" in result.stdout
