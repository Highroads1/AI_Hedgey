@echo off
title AI Hedge Fund Git Synchronization Engine
cd /d "C:\Users\Louis\Desktop\AI_Hedge"

echo ==================================================
echo [GIT ENGINE] Initiating Workspace Archive...
echo ==================================================
echo Archiving daily operational logs to Git...
echo.

:: Step 1: Stage target operational tracking files and codebase files
echo [STATUS] Staging modified workspace logs...
git add trading_crew.py audit_portfolio.py *.bat *.md .gitignore
if %errorlevel% neq 0 (
    echo CRITICAL ERROR: Failed to stage local assets.
    goto end
)

:: Step 2: Use native PowerShell to safely generate a clean, normalized timestamp
echo [STATUS] Querying system clock...
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm'"') do set formatted_timestamp=%%i

:: Step 3: Commit staged assets using the standardized custom message formatting
echo [STATUS] Generating snapshot commit token...
git commit -m "Daily upload: [%formatted_timestamp%]"
if %errorlevel% neq 0 (
    echo INFO: Workspace already perfectly synchronized. No new mutations found.
    goto push_block
)

:push_block
:: Step 4: Transmit the local trunk up to your online secure backend repository
echo.
echo [STATUS] Pushing delta updates to GitHub repository branch: [main]...
echo --------------------------------------------------
git push origin main
echo --------------------------------------------------

:end
echo.
echo ==================================================
echo [GIT INTEGRATION COMPLETE] Archive Operations Concluded.
echo ==================================================
pause