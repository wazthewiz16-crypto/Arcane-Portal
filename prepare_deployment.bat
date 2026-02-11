@echo off
echo ============================================
echo Railway Deployment - Pre-Flight Check
echo ============================================
echo.

echo [1/5] Checking Git status...
git status
echo.

echo [2/5] Testing scraper locally...
echo This will run the scraper once to verify it works.
echo Press Ctrl+C if you want to skip this test.
timeout /t 5
python run_signals.py
echo.

echo [3/5] Checking required files...
if exist "tv_state.json" (
    echo ✓ tv_state.json found
) else (
    echo ✗ tv_state.json NOT FOUND - You need this file!
    echo   Run the scraper locally first to generate it.
)

if exist ".env" (
    echo ✓ .env found
) else (
    echo ✗ .env NOT FOUND - Create from .env.example
)

if exist "requirements.txt" (
    echo ✓ requirements.txt found
) else (
    echo ✗ requirements.txt NOT FOUND
)

if exist "railway.json" (
    echo ✓ railway.json found
) else (
    echo ✗ railway.json NOT FOUND
)

if exist "Procfile" (
    echo ✓ Procfile found
) else (
    echo ✗ Procfile NOT FOUND
)
echo.

echo [4/5] Checking environment variables...
if defined DISCORD_WEBHOOK_URL (
    echo ✓ DISCORD_WEBHOOK_URL is set
) else (
    echo ✗ DISCORD_WEBHOOK_URL not set in .env
)
echo.

echo [5/5] Ready to deploy!
echo.
echo ============================================
echo Next Steps:
echo ============================================
echo 1. Review RAILWAY_DEPLOYMENT.md for full guide
echo 2. Push code to GitHub
echo 3. Create Railway project
echo 4. Set environment variables in Railway
echo 5. Deploy and monitor logs
echo.
echo ============================================
pause
