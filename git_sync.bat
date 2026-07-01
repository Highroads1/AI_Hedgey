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

:: Step 2: Extract clean date/time variables out of local Windows environment strings
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set current_year=%datetime:~0,4%
set current_month=%datetime:~4,2%
set current_day=%datetime:~6,2%
set current_hour=%datetime:~8,2%
set current_minute=%datetime:~10,2%
set formatted_timestamp=%current_year%-%current_month%-%current_day% %current_hour%:%current_minute%

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