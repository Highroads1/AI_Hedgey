@echo off
title AI Hedge Fund Execution Engine
cd /d "C:\Users\Louis\Desktop\AI_Hedge"

echo ==================================================
echo [STEP 1/3] Verifying Local AI Engine Status...
echo ==================================================
curl -s http://localhost:11434/ >nul
if %errorlevel% neq 0 (
    echo WARNING: Ollama Server is offline! Booting engine...
    start "" "C:\Users\Louis\AppData\Local\Programs\Ollama\ollama app.exe"
    timeout /t 10 /nobreak >nul
)
echo SUCCESS: Ollama Engine Online.

echo.
echo ==================================================
echo [STEP 2/3] Executing Strategy Allocations...
echo ==================================================

:: Run Team 1: Vanilla Strategy
echo [Executing: Vanilla 1%% Strategy Engine...]
copy /y vanilla.env .env >nul
python trading_crew.py

:: Run Team 2: Martingale Strategy
echo [Executing: Martingale Scaling Engine...]
copy /y martingale.env .env >nul
python trading_crew.py

:: Run Team 3: Kelly Strategy
echo [Executing: Kelly Criterion Engine...]
copy /y kelly.env .env >nul
python trading_crew.py

echo.
echo ==================================================
echo [STEP 3/3] Initiating Performance Audit Layer...
echo ==================================================
python audit_portfolio.py

echo.
echo ==================================================
echo Pipeline Execution Complete.
echo ==================================================

echo ==================================================
echo Calling Git Sync Batch File
echo ==================================================
call git_sync.bat
pause