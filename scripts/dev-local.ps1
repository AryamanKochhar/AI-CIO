# Local development (no Docker): start or stop API + Next.js web.
# Usage:
#   .\scripts\dev-local.ps1          # start both servers in new terminals
#   .\scripts\dev-local.ps1 -Stop    # stop servers on API/web ports
#   .\scripts\dev-local.ps1 -Setup   # install deps + run migrations, then start

param(
    [switch]$Stop,
    [switch]$Setup
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$DevDir = Join-Path $Root ".dev"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VenvPip = Join-Path $Root ".venv\Scripts\pip.exe"
$ShellExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

function Get-EnvValue {
    param([string]$Name, [string]$Default)
    $line = Get-Content (Join-Path $Root ".env") -ErrorAction SilentlyContinue |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -First 1
    if ($line -match "=\s*(.+)\s*$") {
        return $Matches[1].Trim()
    }
    return $Default
}

function Stop-PortListener {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq "Listen" }
    foreach ($conn in $connections) {
        $procId = $conn.OwningProcess
        if ($procId -and $procId -ne 0) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Stop-DevServers {
    New-Item -ItemType Directory -Force -Path $DevDir | Out-Null
    foreach ($name in @("api", "web")) {
        $pidFile = Join-Path $DevDir "$name.pid"
        if (Test-Path $pidFile) {
            $procId = Get-Content $pidFile -ErrorAction SilentlyContinue
            if ($procId) {
                Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            }
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }
    }

    $apiPort = [int](Get-EnvValue "API_PORT" "8000")
    $webPort = [int](Get-EnvValue "WEB_PORT" "3000")
    Stop-PortListener -Port $apiPort
    Stop-PortListener -Port $webPort
    Remove-Item (Join-Path $DevDir "mode") -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped local dev servers."
}

function Ensure-Setup {
    Set-Location $Root

    if (-not (Test-Path (Join-Path $Root ".env"))) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
        Write-Host "Created .env from .env.example"
    }

    if (-not (Test-Path $VenvPython)) {
        Write-Host "Creating Python virtual environment..."
        python -m venv (Join-Path $Root ".venv")
    }

    Write-Host "Installing Python dependencies..."
    & $VenvPip install -q -r (Join-Path $Root "requirements.txt")

    if (-not (Test-Path (Join-Path $Root "node_modules"))) {
        Write-Host "Installing Node dependencies..."
        pnpm install
    }

    $webEnv = Join-Path $Root "apps\web\.env.local"
    if (-not (Test-Path $webEnv)) {
        $apiBase = Get-EnvValue "NEXT_PUBLIC_API_BASE_URL" "http://localhost:8000"
        Set-Content -Path $webEnv -Value "NEXT_PUBLIC_API_BASE_URL=$apiBase`n"
        Write-Host "Created apps/web/.env.local"
    }

    New-Item -ItemType Directory -Force -Path (Join-Path $Root "data\uploads") | Out-Null

    Write-Host "Running database migrations..."
    $env:PYTHONPATH = "apps/api"
    & (Join-Path $Root ".venv\Scripts\alembic.exe") upgrade head
}

function Start-DevServers {
    Set-Location $Root
    New-Item -ItemType Directory -Force -Path $DevDir | Out-Null

    $apiPort = Get-EnvValue "API_PORT" "8000"
    $webPort = Get-EnvValue "WEB_PORT" "3000"
    $apiHost = Get-EnvValue "API_HOST" "127.0.0.1"

    Stop-DevServers

    $apiCmd = @"
Set-Location '$Root'
& .\.venv\Scripts\Activate.ps1
`$env:PYTHONPATH = 'apps/api'
python -m ai_cio.api
"@

    $webCmd = @"
Set-Location '$Root'
pnpm dev:web
"@

    Write-Host "Starting API  -> http://${apiHost}:$apiPort"
    $apiProc = Start-Process -FilePath $ShellExe -ArgumentList @("-NoExit", "-Command", $apiCmd) -PassThru -WorkingDirectory $Root
    Set-Content -Path (Join-Path $DevDir "api.pid") -Value $apiProc.Id

    Start-Sleep -Seconds 2

    Write-Host "Starting Web  -> http://localhost:$webPort"
    $webProc = Start-Process -FilePath $ShellExe -ArgumentList @("-NoExit", "-Command", $webCmd) -PassThru -WorkingDirectory $Root
    Set-Content -Path (Join-Path $DevDir "web.pid") -Value $webProc.Id

    Set-Content -Path (Join-Path $DevDir "mode") -Value "local"

    Write-Host ""
    Write-Host "Dev servers launched in new terminal windows."
    Write-Host "  App: http://localhost:$webPort"
    Write-Host "  API: http://${apiHost}:$apiPort/health"
    Write-Host ""
    Write-Host "Stop with: .\scripts\dev-local.ps1 -Stop"
}

if ($Stop) {
    Stop-DevServers
    exit 0
}

if ($Setup) {
    Ensure-Setup
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "First run detected - running setup..."
    Ensure-Setup
}

Start-DevServers
