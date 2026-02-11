@echo off
REM Arcane Portal V2 - Dashboard Launcher

echo ========================================
echo   Arcane Portal V2
echo   Mango Dynamic Trading Signals
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo [ERROR] .env file not found!
    echo.
    echo Please create .env file from .env.example:
    echo   1. Copy .env.example to .env
    echo   2. Add your Discord webhook URL
    echo.
    pause
    exit /b 1
)

REM Check if tv_state.json exists
if not exist tv_state.json (
    echo [WARNING] tv_state.json not found!
    echo The scraper will not work without TradingView authentication.
    echo.
)

echo [INFO] Starting Streamlit dashboard...
echo [INFO] Dashboard will open at: http://localhost:8501
echo.
echo Press Ctrl+C to stop the dashboard
echo.

streamlit run dashboard/app.py
