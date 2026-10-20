# Local API + web launcher. Child services run hidden and write logs to .dev/.
# .\scripts\dev-local.ps1 -Setup
# .\scripts\dev-local.ps1 -Stop
# .\scripts\dev-local.ps1 -EnvFile .env.preview -SkipMigrations
[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Setup,
    [switch]$SkipMigrations,
    [switch]$Production,
    [string]$EnvFile = '.env',
    [ValidateSet('api', 'web')][string]$Service
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$DevDirectory = Join-Path $ProjectRoot '.dev'
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$ShellBinary = (Get-Process -Id $PID).Path
if (-not [System.IO.Path]::IsPathRooted($EnvFile)) { $EnvFile = Join-Path $ProjectRoot $EnvFile }
$EnvironmentFile = [System.IO.Path]::GetFullPath($EnvFile)
New-Item -ItemType Directory -Force -Path $DevDirectory | Out-Null

function Get-EnvironmentValue([string]$Name, [string]$Default) {
    $processValue = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if (-not [string]::IsNullOrEmpty($processValue)) { return $processValue }
    if (-not (Test-Path -LiteralPath $EnvironmentFile)) { return $Default }
    foreach ($line in (Get-Content -LiteralPath $EnvironmentFile)) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*?)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $Default
}

function Assert-IsolatedConfiguration {
    $apiPortText = Get-EnvironmentValue 'API_PORT' '8100'
    $webPortText = Get-EnvironmentValue 'WEB_PORT' '3100'
    $apiPortNumber = 0
    $webPortNumber = 0
    if (-not [int]::TryParse($apiPortText, [ref]$apiPortNumber) -or
        -not [int]::TryParse($webPortText, [ref]$webPortNumber)) {
        throw 'AI-CIO requires numeric API_PORT and WEB_PORT values.'
    }
    foreach ($portNumber in @($apiPortNumber, $webPortNumber)) {
        if ($portNumber -in @(3000, 8000, 18000)) {
            throw 'AI-CIO cannot use Orbix reserved ports 3000, 8000 or 18000. Use web 3100 and API 8100.'
        }
        if ($portNumber -lt 1024 -or $portNumber -gt 65535) {
            throw 'AI-CIO requires unprivileged ports between 1024 and 65535.'
        }
    }
    if ($apiPortNumber -eq $webPortNumber) { throw 'AI-CIO API and web ports must differ.' }
    $apiHostName = Get-EnvironmentValue 'API_HOST' '127.0.0.1'
    $webHostName = Get-EnvironmentValue 'WEB_HOST' '127.0.0.1'
    if ($apiHostName -notin @('127.0.0.1', 'localhost') -or $webHostName -notin @('127.0.0.1', 'localhost')) {
        throw 'AI-CIO native services must bind to loopback.'
    }
    $publicApiUrl = Get-EnvironmentValue 'NEXT_PUBLIC_API_BASE_URL' "http://localhost:$apiPortNumber"
    $apiUri = $null
    if (-not [Uri]::TryCreate($publicApiUrl, [UriKind]::Absolute, [ref]$apiUri) -or
        $apiUri.Scheme -ne 'http' -or $apiUri.Host -notin @('localhost', '127.0.0.1') -or
        $apiUri.Port -ne $apiPortNumber -or $apiUri.AbsolutePath -ne '/' -or
        $apiUri.UserInfo -or $apiUri.Query -or $apiUri.Fragment) {
        throw 'NEXT_PUBLIC_API_BASE_URL must use the selected loopback AI-CIO API port.'
    }
    return [PSCustomObject]@{
        ApiPort = $apiPortNumber; WebPort = $webPortNumber
        ApiHost = $apiHostName; WebHost = $webHostName; PublicApiUrl = $publicApiUrl
    }
}

function Invoke-ProjectPnpm([string[]]$PnpmArguments) {
    $pnpmTool = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    if ($pnpmTool) { & $pnpmTool.Source @PnpmArguments }
    else { & npx.cmd --yes pnpm@9.15.0 @PnpmArguments }
    if ($LASTEXITCODE -ne 0) { throw 'pnpm command failed; inspect the output above.' }
}

function Stop-OwnedServices {
    foreach ($serviceName in @('api', 'web')) {
        $recordFile = Join-Path $DevDirectory "$serviceName.process.json"
        if (-not (Test-Path -LiteralPath $recordFile)) { continue }
        $record = Get-Content -Raw -LiteralPath $recordFile | ConvertFrom-Json
        $ownedProcess = Get-Process -Id $record.id -ErrorAction SilentlyContinue
        if ($ownedProcess -and $ownedProcess.StartTime.ToUniversalTime().Ticks.ToString() -eq $record.started) {
            # A child can exit while taskkill walks the tree. Capture native
            # stderr without turning that harmless race into a PowerShell error.
            $stopJob = Start-Process -FilePath 'taskkill.exe' -ArgumentList @('/PID', $record.id, '/T', '/F') -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $DevDirectory 'stop.out.log') -RedirectStandardError (Join-Path $DevDirectory 'stop.err.log')
            if ($stopJob.ExitCode -ne 0 -and (Get-Process -Id $record.id -ErrorAction SilentlyContinue)) {
                throw "Could not stop the managed $serviceName process. Read .dev/stop.err.log."
            }
        }
        Remove-Item -LiteralPath $recordFile -Force
    }
    Remove-Item -LiteralPath (Join-Path $DevDirectory 'mode') -Force -ErrorAction SilentlyContinue
    Write-Host 'Stopped services started by this checkout.'
}

function Initialize-Project {
    Set-Location -LiteralPath $ProjectRoot
    if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot '.env.example') -Destination $EnvironmentFile
        Write-Host 'Created local environment file from the example.'
    }
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        & python -m venv (Join-Path $ProjectRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    & $VenvPython -m pip install -q -r (Join-Path $ProjectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Invoke-ProjectPnpm @('install', '--frozen-lockfile')
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot 'data\uploads') | Out-Null
    if (-not $SkipMigrations) {
        $env:AICIO_ENV_FILE = $EnvironmentFile
        $env:PYTHONPATH = 'apps/api'
        & $VenvPython -c "from alembic.config import main; main(['upgrade', 'head'])"
        if ($LASTEXITCODE -ne 0) { throw 'Database migrations failed. Check database access; no services were started.' }
    }
}

function Wait-Healthy([string]$Url, [string]$ServiceName) {
    $deadline = [DateTime]::UtcNow.AddSeconds(100)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Milliseconds 750
    }
    throw "$ServiceName did not become healthy. Read .dev/$ServiceName.out.log and .dev/$ServiceName.err.log."
}

Set-Location -LiteralPath $ProjectRoot
# Explicit cleanup remains available even if a previous configuration is invalid.
if ($Stop) { Stop-OwnedServices; exit 0 }
# Validate before setup, normal restart, or direct child-service execution.
$localConfig = Assert-IsolatedConfiguration
if ($Service) {
    # Only the API reads private environment values. The browser receives its public URL.
    $env:AICIO_ENV_FILE = $EnvironmentFile
    if ($Service -eq 'api') {
        $env:PYTHONPATH = 'apps/api'
        $env:API_PORT = [string]$localConfig.ApiPort
        $env:API_HOST = $localConfig.ApiHost
        & $VenvPython -m ai_cio.api
    } else {
        $env:NEXT_PUBLIC_API_BASE_URL = $localConfig.PublicApiUrl
        $webPort = $localConfig.WebPort
        $webHost = $localConfig.WebHost
        $webMode = if ($Production) { 'start' } else { 'dev' }
        Invoke-ProjectPnpm @('--filter', '@ai-cio/web', 'exec', 'next', $webMode, '--port', $webPort, '--hostname', $webHost)
    }
    exit $LASTEXITCODE
}

if ($Setup -or -not (Test-Path -LiteralPath $VenvPython)) { Initialize-Project }
if (-not (Test-Path -LiteralPath $EnvironmentFile)) { throw 'Create a local .env file, or run with -Setup.' }
$localConfig = Assert-IsolatedConfiguration
Stop-OwnedServices
$apiPort = $localConfig.ApiPort
$webPort = $localConfig.WebPort
$apiHost = $localConfig.ApiHost
foreach ($portNumber in @($apiPort, $webPort)) {
    if (Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $portNumber is already in use. Stop its existing service or choose another port."
    }
}

try {
    foreach ($serviceName in @('api', 'web')) {
        $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-Service', $serviceName, '-EnvFile', "`"$EnvironmentFile`"")
        if ($Production) { $arguments += '-Production' }
        $process = Start-Process -FilePath $ShellBinary -ArgumentList $arguments -WindowStyle Hidden -PassThru -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $DevDirectory "$serviceName.out.log") -RedirectStandardError (Join-Path $DevDirectory "$serviceName.err.log")
        @{ id = $process.Id; started = $process.StartTime.ToUniversalTime().Ticks.ToString() } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $DevDirectory "$serviceName.process.json")
    }
    Wait-Healthy "http://${apiHost}:$apiPort/health" 'api'
    Wait-Healthy "http://localhost:$webPort" 'web'
    Set-Content -LiteralPath (Join-Path $DevDirectory 'mode') -Value 'local'
    Write-Host "App: http://localhost:$webPort"
    Write-Host "API: http://${apiHost}:$apiPort/health"
    Write-Host 'Both services are healthy. Logs: .dev/. Stop with .\scripts\dev-local.ps1 -Stop'
} catch {
    Stop-OwnedServices
    throw
}
