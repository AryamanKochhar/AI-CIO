@echo off
REM Psychometric Assessment - Quick Start Script

echo.
echo ========================================
echo Psychometric Assessment MVP
echo ========================================
echo.

REM Check if Docker is running
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo [1/3] Starting PostgreSQL via Docker...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start Docker containers
    pause
    exit /b 1
)

echo [OK] PostgreSQL started
echo.
echo [2/3] Activating virtual environment...
call .\venv\Scripts\Activate.ps1

echo.
echo [3/3] Environment ready!
echo.
echo ========================================
echo Next Steps:
echo ========================================
echo.
echo Terminal 1 - Run Backend:
echo   cd backend
echo   python main.py
echo.
echo Terminal 2 - Run Frontend:
echo   cd frontend
echo   streamlit run app.py
echo.
echo Backend API:  http://127.0.0.1:8000
echo Streamlit UI: http://localhost:8501
echo.
echo To stop Docker later:
echo   docker-compose down
echo.
echo ========================================
echo.
pause
