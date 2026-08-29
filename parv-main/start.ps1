# Psychometric Assessment - Quick Start Script (PowerShell)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Psychometric Assessment MVP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    $dockerRunning = docker ps 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Docker is not running!" -ForegroundColor Red
        Write-Host "Please start Docker Desktop and try again." -ForegroundColor Red
        pause
        exit 1
    }
} catch {
    Write-Host "[ERROR] Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[1/3] Starting PostgreSQL via Docker..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to start Docker containers" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[OK] PostgreSQL started" -ForegroundColor Green
Write-Host ""
Write-Host "[2/3] Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

Write-Host ""
Write-Host "[3/3] Environment ready!" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Terminal 1 - Run Backend:" -ForegroundColor White
Write-Host "  cd backend" -ForegroundColor Gray
Write-Host "  python main.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Terminal 2 - Run Frontend:" -ForegroundColor White
Write-Host "  cd frontend" -ForegroundColor Gray
Write-Host "  streamlit run app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Backend API:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Streamlit UI: http://localhost:8501" -ForegroundColor Green
Write-Host ""
Write-Host "To stop Docker later:" -ForegroundColor White
Write-Host "  docker-compose down" -ForegroundColor Gray
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
