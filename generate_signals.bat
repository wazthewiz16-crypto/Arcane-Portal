@echo off
REM Arcane Portal V2 - Signal Generator

echo ========================================
echo   Arcane Portal V2
echo   Signal Generation
echo ========================================
echo.

REM Check if tv_state.json exists
if not exist tv_state.json (
    echo [ERROR] tv_state.json not found!
    echo.
    echo The scraper needs TradingView authentication to work.
    echo Please add tv_state.json to the project root.
    echo.
    pause
    exit /b 1
)

echo [INFO] This will:
echo   1. Scrape all 17 assets from TradingView
echo   2. Detect trading signals
echo   3. Save signals to database
echo   4. Send Discord alerts
echo.
echo This may take 2-3 minutes...
echo.

python run_signals.py

echo.
echo ========================================
echo.
pause
