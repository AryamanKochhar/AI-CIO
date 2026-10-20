"""Validate pure launcher config functions without service startup or real .env."""
from __future__ import annotations
import base64
import json
import os
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(SHELL is None, reason="PowerShell is not installed")
KEYS = ("API_PORT", "WEB_PORT", "API_HOST", "WEB_HOST", "NEXT_PUBLIC_API_BASE_URL")


def validate(tmp_path, values=None, overrides=None):
    env_file = tmp_path / "isolated-test.env"
    env_file.write_text("\n".join(f"{key}={value}" for key, value in (values or {}).items()), encoding="utf-8")
    harness = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:AICIO_LAUNCHER_UNDER_TEST, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Launcher parse error' }
foreach ($name in @('Get-EnvironmentValue', 'Assert-IsolatedConfiguration')) {
    $definition = $ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true) | Select-Object -First 1
    if (-not $definition) { throw "Missing configuration function: $name" }
    . ([scriptblock]::Create($definition.Extent.Text))
}
$EnvironmentFile = $env:AICIO_TEST_CONFIG
try {
    Assert-IsolatedConfiguration | ConvertTo-Json -Compress
} catch {
    @{ error = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 1
}
"""
    child_env = {key: value for key, value in os.environ.items() if key not in KEYS}
    child_env.update(overrides or {})
    child_env["AICIO_LAUNCHER_UNDER_TEST"] = str(ROOT / "scripts" / "dev-local.ps1")
    child_env["AICIO_TEST_CONFIG"] = str(env_file)
    encoded = base64.b64encode(harness.encode("utf-16-le")).decode("ascii")
    result = subprocess.run(
        [SHELL, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        env=child_env, capture_output=True, text=True, timeout=20, check=False,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, f"Configuration harness produced no JSON (exit {result.returncode})"
    return result.returncode, json.loads(lines[-1])


def test_default_ports_are_loopback_and_separate(tmp_path):
    code, config = validate(tmp_path)
    assert code == 0
    assert config["ApiPort"] == 8100
    assert config["WebPort"] == 3100
    assert config["ApiHost"] == config["WebHost"] == "127.0.0.1"
    assert config["PublicApiUrl"] == "http://localhost:8100"


@pytest.mark.parametrize("key", ["API_PORT", "WEB_PORT"])
@pytest.mark.parametrize("reserved", ["3000", "8000", "18000"])
def test_reserved_ports_rejected_without_starting_services(tmp_path, key, reserved):
    code, result = validate(tmp_path, {key: reserved})
    assert code != 0
    assert "reserved ports" in result["error"]


@pytest.mark.parametrize("bad", ["not-a-port", "1023", "65536"])
def test_invalid_ports_rejected(tmp_path, bad):
    code, result = validate(tmp_path, {"API_PORT": bad})
    assert code != 0
    assert "ports" in result["error"] or "numeric" in result["error"]


def test_api_and_web_cannot_share_a_port(tmp_path):
    code, result = validate(tmp_path, {"API_PORT": "8311", "WEB_PORT": "8311"})
    assert code != 0
    assert "must differ" in result["error"]


@pytest.mark.parametrize("url", [
    "http://localhost:8000", "https://localhost:8100", "http://example.com:8100",
    "http://localhost:8100/private", "http://localhost:8100/?redirect=yes",
    "http://localhost:8100/#fragment", "http://user:pass@localhost:8100",
])
def test_public_origin_must_match_selected_api_port(tmp_path, url):
    code, result = validate(tmp_path, {"NEXT_PUBLIC_API_BASE_URL": url})
    assert code != 0
    assert "selected loopback" in result["error"]


@pytest.mark.parametrize("key", ["API_HOST", "WEB_HOST"])
def test_native_services_reject_non_loopback_binding(tmp_path, key):
    code, result = validate(tmp_path, {key: "0.0.0.0"})
    assert code != 0
    assert "loopback" in result["error"]


def test_process_overrides_file_consistently(tmp_path):
    code, config = validate(
        tmp_path,
        {"API_PORT": "8000", "WEB_PORT": "3000", "NEXT_PUBLIC_API_BASE_URL": "http://localhost:8000"},
        {"API_PORT": "8311", "WEB_PORT": "3311", "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8311"},
    )
    assert code == 0
    assert config["ApiPort"] == 8311
    assert config["WebPort"] == 3311
    assert config["PublicApiUrl"] == "http://127.0.0.1:8311"
