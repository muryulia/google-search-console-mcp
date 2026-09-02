[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^tunnel_[A-Za-z0-9_-]{8,}$')]
    [string] $TunnelId,

    [string] $TunnelClientPath = '',

    [ValidateSet('gsc-mcp')]
    [string] $ProfileName = 'gsc-mcp',

    [string] $PythonPath = '',

    [string] $ProfileDirectory = '',

    [switch] $UseExistingProfile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RequiredFile {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,

        [Parameter(Mandatory = $true)]
        [string] $Label
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label was not found: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-ProfilePath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $TunnelClient,

        [Parameter(Mandatory = $true)]
        [string] $Name,

        [string] $Directory = ''
    )

    $arguments = @('profiles', 'list')
    if (-not [string]::IsNullOrWhiteSpace($Directory)) {
        $arguments += @('--profile-dir', $Directory)
    }

    $profileLines = @(& $TunnelClient @arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to list tunnel-client profiles.'
    }

    $prefix = "$Name`t"
    $profileLine = $profileLines |
        Where-Object { $_.StartsWith($prefix, [System.StringComparison]::Ordinal) } |
        Select-Object -First 1

    if ($null -eq $profileLine) {
        return $null
    }

    return $profileLine.Substring($prefix.Length).Trim()
}

function Assert-DoctorCheck {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $Checks,

        [Parameter(Mandatory = $true)]
        [string] $Id,

        [Parameter(Mandatory = $true)]
        [string] $ExpectedSummary
    )

    if (-not $Checks.ContainsKey($Id)) {
        throw "doctor did not return the required $Id check."
    }

    $check = $Checks[$Id]
    if ($check.status -ne 'PASS') {
        throw "doctor check $Id did not pass."
    }
    if (-not [string]::Equals(
        [string] $check.summary,
        $ExpectedSummary,
        [System.StringComparison]::Ordinal
    )) {
        throw "doctor check $Id did not match the expected active value."
    }
}

if ([string]::IsNullOrWhiteSpace($env:CONTROL_PLANE_API_KEY)) {
    throw 'CONTROL_PLANE_API_KEY must be set in this process. Do not pass or store the key in the repository.'
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

if ([string]::IsNullOrWhiteSpace($TunnelClientPath)) {
    $tunnelCommand = Get-Command tunnel-client -ErrorAction SilentlyContinue
    if ($null -eq $tunnelCommand) {
        throw 'Set -TunnelClientPath or add tunnel-client to PATH.'
    }
    $TunnelClientPath = $tunnelCommand.Source
}
$tunnelClient = Resolve-RequiredFile -Path $TunnelClientPath -Label 'tunnel-client'

$versionOutput = @(& $tunnelClient --version 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to read the tunnel-client version.'
}
$tunnelClientVersion = ($versionOutput -join "`n").Trim()
if ($tunnelClientVersion -notmatch '^0\.0\.13(?:\+|$)') {
    throw "This v0.2 gate is validated only with tunnel-client 0.0.13; found $tunnelClientVersion. Revalidate before upgrading."
}

if (-not [string]::IsNullOrWhiteSpace($ProfileDirectory)) {
    if (-not (Test-Path -LiteralPath $ProfileDirectory -PathType Container)) {
        throw "Profile directory was not found: $ProfileDirectory"
    }
    $ProfileDirectory = (Resolve-Path -LiteralPath $ProfileDirectory).Path
}

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $repoRoot '.venv\Scripts\python.exe'
}
$python = Resolve-RequiredFile -Path $PythonPath -Label 'virtual-environment Python'
$pythonForCommand = $python.Replace('\', '/')
$expectedMcpTarget = '"{0}" -m gsc_mcp.server' -f $pythonForCommand

$existingProfilePath = Get-ProfilePath `
    -TunnelClient $tunnelClient `
    -Name $ProfileName `
    -Directory $ProfileDirectory
if ($null -ne $existingProfilePath -and -not $UseExistingProfile) {
    throw "Profile $ProfileName already exists at $existingProfilePath. Review it, then rerun with -UseExistingProfile. It will not be overwritten."
}

if ($null -eq $existingProfilePath) {
    $initArguments = @(
        'init',
        '--sample', 'sample_mcp_stdio_local',
        '--profile', $ProfileName,
        '--tunnel-id', $TunnelId,
        '--mcp-command', $expectedMcpTarget,
        '--control-plane-api-key-ref', 'env:CONTROL_PLANE_API_KEY',
        '--health-listen-addr', '127.0.0.1:0'
    )
    if (-not [string]::IsNullOrWhiteSpace($ProfileDirectory)) {
        $initArguments += @('--profile-dir', $ProfileDirectory)
    }

    $initOutput = @(& $tunnelClient @initArguments 2>&1)
    $initExit = $LASTEXITCODE
    $initText = ($initOutput -join "`n").Replace(
        $env:CONTROL_PLANE_API_KEY,
        '[REDACTED]',
        [System.StringComparison]::Ordinal
    )
    if ($initExit -ne 0) {
        throw "tunnel-client init failed.`n$initText"
    }

    $existingProfilePath = Get-ProfilePath `
        -TunnelClient $tunnelClient `
        -Name $ProfileName `
        -Directory $ProfileDirectory
    if ($null -eq $existingProfilePath) {
        throw "Profile $ProfileName was not created."
    }
}

$profilePath = Resolve-RequiredFile -Path $existingProfilePath -Label "profile $ProfileName"
$doctorArguments = @('doctor', '--profile', $ProfileName, '--json')
if (-not [string]::IsNullOrWhiteSpace($ProfileDirectory)) {
    $doctorArguments += @('--profile-dir', $ProfileDirectory)
}

Push-Location $repoRoot
try {
    $doctorOutput = @(& $tunnelClient @doctorArguments 2>&1)
    $doctorExit = $LASTEXITCODE
}
finally {
    Pop-Location
}

$doctorText = ($doctorOutput -join "`n").Replace(
    $env:CONTROL_PLANE_API_KEY,
    '[REDACTED]',
    [System.StringComparison]::Ordinal
)
try {
    $doctor = $doctorText | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw 'tunnel-client doctor did not return valid JSON.'
}

if ($doctorExit -ne 0 -or $doctor.result -ne 'ok') {
    $failedIds = @($doctor.failed_checks | Where-Object { $null -ne $_ }) -join ', '
    throw "tunnel-client doctor failed. Failed checks: $failedIds"
}

$checks = @{}
foreach ($check in $doctor.checks) {
    $checks[[string] $check.id] = $check
}

Assert-DoctorCheck -Checks $checks -Id 'config_source' -ExpectedSummary "profile: $ProfileName"
Assert-DoctorCheck -Checks $checks -Id 'profile_load' -ExpectedSummary $profilePath
Assert-DoctorCheck -Checks $checks -Id 'tunnel_id' -ExpectedSummary $TunnelId
Assert-DoctorCheck `
    -Checks $checks `
    -Id 'control_plane_api_key' `
    -ExpectedSummary 'env:CONTROL_PLANE_API_KEY'
Assert-DoctorCheck -Checks $checks -Id 'mcp_target' -ExpectedSummary $expectedMcpTarget
Assert-DoctorCheck `
    -Checks $checks `
    -Id 'mcp_command_executable' `
    -ExpectedSummary $pythonForCommand

if (-not $checks.ContainsKey('health_listener') -or
    $checks['health_listener'].status -ne 'PASS' -or
    $checks['health_listener'].summary -notmatch '^ephemeral bind ok on http://127\.0\.0\.1:\d+$') {
    throw 'doctor did not confirm an ephemeral loopback health listener.'
}

[pscustomobject]@{
    Profile = $ProfileName
    ProfilePath = $profilePath
    TunnelId = $TunnelId
    TunnelClientVersion = $tunnelClientVersion
    Doctor = 'passed'
    ActiveMcpTarget = $expectedMcpTarget
    DoctorHealthProbe = $checks['health_listener'].summary
}
