@echo off
REM Windows batch script to run the SPY options downloader
REM Make sure Theta Terminal is already running before executing this script

echo ============================================================
echo SPY Options Data Downloader - Windows Runner
echo ============================================================
echo.
echo Checking if Theta Terminal is accessible...
curl -s http://localhost:25503/v3/list/roots >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Cannot connect to Theta Terminal!
    echo.
    echo Please start Theta Terminal first:
    echo   java -jar ThetaTerminalv3.jar wayleemh@gmail.com CCmonster228!
    echo.
    pause
    exit /b 1
)

echo [OK] Theta Terminal is running
echo.
echo Starting download...
echo.

REM Run the Python script
python download_spy_options.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Download script failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Download complete!
echo ============================================================
pause
