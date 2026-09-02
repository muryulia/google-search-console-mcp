from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "tunnel_acceptance.ps1"
PWSH = shutil.which("pwsh")

FAKE_TUNNEL_CLIENT = r"""
$cliArgs = @($args)

function Get-CliValue {
    param([string] $Name)

    $index = [Array]::IndexOf($cliArgs, $Name)
    if ($index -lt 0 -or $index + 1 -ge $cliArgs.Count) {
        return ''
    }
    return $cliArgs[$index + 1]
}

if ($cliArgs[0] -eq '--version') {
    if ([string]::IsNullOrWhiteSpace($env:FAKE_TUNNEL_VERSION)) {
        '0.0.13+fake-runtime-test (git sha: fake)'
    }
    else {
        $env:FAKE_TUNNEL_VERSION
    }
    exit 0
}

$profileDirectory = Get-CliValue '--profile-dir'
$profilePath = Join-Path $profileDirectory 'gsc-mcp.yaml'

if ($cliArgs[0] -eq 'profiles' -and $cliArgs[1] -eq 'list') {
    if (Test-Path -LiteralPath $profilePath -PathType Leaf) {
        "gsc-mcp`t$profilePath"
    }
    exit 0
}

if ($cliArgs[0] -eq 'init') {
    $null = New-Item -ItemType Directory -Path $profileDirectory -Force
    $profileFixture = @(
        "tunnel_id: $(Get-CliValue '--tunnel-id')",
        "control_plane_api_key: $(Get-CliValue '--control-plane-api-key-ref')",
        "mcp_target: $(Get-CliValue '--mcp-command')",
        "health_listen_addr: $(Get-CliValue '--health-listen-addr')"
    ) -join "`n"
    Set-Content -LiteralPath $profilePath -Value $profileFixture -Encoding utf8
    'created isolated fake profile'
    exit 0
}

if ($cliArgs[0] -eq 'doctor') {
    $checks = @(
        @{ id = 'config_source'; status = 'PASS'; summary = 'profile: gsc-mcp' },
        @{ id = 'profile_load'; status = 'PASS'; summary = $env:FAKE_PROFILE_PATH },
        @{ id = 'tunnel_id'; status = 'PASS'; summary = $env:FAKE_TUNNEL_ID },
        @{ id = 'control_plane_api_key'; status = 'PASS'; summary = 'env:CONTROL_PLANE_API_KEY' },
        @{ id = 'mcp_target'; status = 'PASS'; summary = $env:FAKE_MCP_TARGET },
        @{ id = 'mcp_command_executable'; status = 'PASS'; summary = $env:FAKE_MCP_EXECUTABLE },
        @{
            id = 'health_listener'
            status = 'PASS'
            summary = 'ephemeral bind ok on http://127.0.0.1:54321'
        }
    )
    @{ result = 'ok'; failed_checks = @(); checks = $checks } |
        ConvertTo-Json -Depth 5
    exit 0
}

Write-Error "Unexpected fake tunnel-client arguments: $cliArgs"
exit 2
"""


def _script_text() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_tunnel_gate_never_accepts_or_persists_a_key_value() -> None:
    source = _script_text()

    assert "env:CONTROL_PLANE_API_KEY" in source
    assert "$env:CONTROL_PLANE_API_KEY" in source
    assert "$env:OPENAI_API_KEY" not in source
    assert "--control-plane.api-key" not in source
    assert "--force" not in source


def test_tunnel_gate_is_fixed_to_dedicated_profile_and_ephemeral_loopback() -> None:
    source = _script_text()

    assert "[ValidateSet('gsc-mcp')]" in source
    assert "'127.0.0.1:0'" in source
    assert "ephemeral loopback health listener" in source
    assert "--allow-remote-ui" not in source


def test_tunnel_gate_refuses_implicit_profile_overwrite() -> None:
    source = _script_text()

    assert "$UseExistingProfile" in source
    assert "It will not be overwritten" in source
    assert "--force" not in source


def test_tunnel_gate_validates_authoritative_doctor_json() -> None:
    source = _script_text()

    assert "ConvertFrom-Json" in source
    for check_id in (
        "config_source",
        "profile_load",
        "tunnel_id",
        "control_plane_api_key",
        "mcp_target",
        "mcp_command_executable",
        "health_listener",
    ):
        assert check_id in source
    assert "Get-Content -LiteralPath $profilePath" not in source


def test_tunnel_gate_pins_validated_cli_and_windows_command_encoding() -> None:
    source = _script_text()

    assert "^0\\.0\\.13" in source
    assert "$python.Replace('\\', '/')" in source
    assert "--log.http-raw-unsafe" not in source
    assert "Start-Process" not in source
    assert "RedirectStandard" not in source


@pytest.mark.skipif(PWSH is None, reason="PowerShell 7 is required")
def test_tunnel_gate_runtime_contract(tmp_path: Path) -> None:
    assert PWSH is not None
    fake_client = tmp_path / "fake-tunnel-client.ps1"
    fake_client.write_text(
        textwrap.dedent(FAKE_TUNNEL_CLIENT).lstrip(),
        encoding="utf-8",
    )
    profile_directory = tmp_path / "profiles"
    profile_directory.mkdir()
    profile_path = profile_directory / "gsc-mcp.yaml"
    tunnel_id = "tunnel_0123456789abcdef0123456789abcdef"
    python_path = Path(sys.executable).resolve()
    python_for_command = str(python_path).replace("\\", "/")
    expected_target = f'"{python_for_command}" -m gsc_mcp.server'
    environment = os.environ.copy()
    environment.update(
        {
            "CONTROL_PLANE_API_KEY": "dummy-never-persisted",
            "FAKE_PROFILE_PATH": str(profile_path.resolve()),
            "FAKE_TUNNEL_ID": tunnel_id,
            "FAKE_MCP_TARGET": expected_target,
            "FAKE_MCP_EXECUTABLE": python_for_command,
        }
    )
    command = [
        PWSH,
        "-NoProfile",
        "-File",
        str(SCRIPT_PATH),
        "-TunnelId",
        tunnel_id,
        "-TunnelClientPath",
        str(fake_client),
        "-ProfileDirectory",
        str(profile_directory),
        "-PythonPath",
        str(python_path),
    ]

    first = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=30,
    )
    assert first.returncode == 0, first.stderr
    assert "Doctor" in first.stdout and "passed" in first.stdout
    profile_fixture = profile_path.read_text(encoding="utf-8")
    assert "env:CONTROL_PLANE_API_KEY" in profile_fixture
    assert "dummy-never-persisted" not in profile_fixture
    assert expected_target in profile_fixture
    assert "127.0.0.1:0" in profile_fixture

    before_refusal = profile_fixture
    refused = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=30,
    )
    assert refused.returncode != 0
    assert "It will not be overwritten" in refused.stderr
    assert profile_path.read_text(encoding="utf-8") == before_refusal

    reviewed = subprocess.run(  # noqa: S603
        [*command, "-UseExistingProfile"],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=30,
    )
    assert reviewed.returncode == 0, reviewed.stderr
    assert "Doctor" in reviewed.stdout and "passed" in reviewed.stdout

    incompatible_environment = environment | {"FAKE_TUNNEL_VERSION": "0.0.14"}
    incompatible = subprocess.run(  # noqa: S603
        [*command, "-UseExistingProfile"],
        capture_output=True,
        check=False,
        env=incompatible_environment,
        text=True,
        timeout=30,
    )
    assert incompatible.returncode != 0
    assert "validated only with tunnel-client 0.0.13" in incompatible.stderr
