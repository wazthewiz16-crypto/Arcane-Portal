@echo off
REM Analyze signal performance from last 24 hours

echo ========================================
echo  SIGNAL PERFORMANCE ANALYZER
echo ========================================
echo.

python analyze_signals.py --hours 24

echo.
pause
