@echo off
title [PRODUCTION] AI Hedge Fund Live Execution Engine
cd /d "C:\Users\Louis\Desktop\AI_Hedge"

echo ==================================================
echo [STEP 1/2] Verifying Local AI Engine Status...
echo ==================================================

:: Ping Ollama's local API port to ensure the model backend is awake
curl -s http://localhost:11434/ >nul

if %errorlevel% equ 0 (
    echo SUCCESS: Ollama Engine is active and responding.
) else (
    echo WARNING: Ollama Engine is offline! 
    echo Attempting to automatically initialize the engine context...
    
    if exist "C:\Users\Louis\AppData\Local\Programs\Ollama\ollama app.exe" (
        start "" "C:\Users\Louis\AppData\Local\Programs\Ollama\ollama app.exe"
        goto wait_block
    )

    echo CRITICAL ERROR: Could not locate your Ollama app installation path.
    echo Please make sure Ollama is running manually before production launch.
    goto end

    :wait_block
    echo Waiting 10 seconds for local model VRAM allocation...
    timeout /t 10 /nobreak >nul
    
    curl -s http://localhost:11434/ >nul
    if %errorlevel% neq 0 (
        echo CRITICAL ERROR: Engine discovered but failed to bind to port 11434.
        goto end
    )
    echo SUCCESS: Ollama Engine recovered cleanly.

    )

echo.
echo ==================================================
echo [STEP 2/2] Launching Live Strategy Execution...
echo ==================================================

:: Point explicitly to your final chosen strategy profile
:: The main python script will pull keys and math rules directly from here
copy /y .env.real_money .env >nul

echo [STATUS] Transmitting live account payload to execution loop...
python trading_crew.py

:end
echo.
echo ==================================================
echo [LIVE PIPELINE COMPLETE] Terminal Session Concluded.
echo ==================================================
pause