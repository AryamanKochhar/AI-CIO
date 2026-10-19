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
    if (-not (Test-Path -LiteralPath $EnvironmentFile)) { return $Default }
    foreach ($line in (Get-Content -LiteralPath $EnvironmentFile)) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*?)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $Default
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
if ($Service) {
    # Only the API reads private environment values. The browser receives its public URL.
    $env:AICIO_ENV_FILE = $EnvironmentFile
    if ($Service -eq 'api') {
        $env:PYTHONPATH = 'apps/api'
        & $VenvPython -m ai_cio.api
    } else {
        $env:NEXT_PUBLIC_API_BASE_URL = Get-EnvironmentValue 'NEXT_PUBLIC_API_BASE_URL' 'http://localhost:8000'
        $webPort = Get-EnvironmentValue 'WEB_PORT' '3000'
        $webHost = Get-EnvironmentValue 'WEB_HOST' '127.0.0.1'
        $webMode = if ($Production) { 'start' } else { 'dev' }
        Invoke-ProjectPnpm @('--filter', '@ai-cio/web', 'exec', 'next', $webMode, '--port', $webPort, '--hostname', $webHost)
    }
    exit $LASTEXITCODE
}

if ($Stop) { Stop-OwnedServices; exit 0 }
if ($Setup -or -not (Test-Path -LiteralPath $VenvPython)) { Initialize-Project }
if (-not (Test-Path -LiteralPath $EnvironmentFile)) { throw 'Create a local .env file, or run with -Setup.' }
Stop-OwnedServices
$apiPort = [int](Get-EnvironmentValue 'API_PORT' '8000')
$webPort = [int](Get-EnvironmentValue 'WEB_PORT' '3000')
$apiHost = Get-EnvironmentValue 'API_HOST' '127.0.0.1'
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
