@echo off
setlocal

REM ============================================================
REM  Orion Startup Script (UI + OpenAI API enabled)
REM ============================================================

REM ---- Activate venv ----
call C:\Orion\text-generation-webui\venv-orion\Scripts\activate.bat

REM ---- Move into TGWUI directory ----
cd /d C:\Orion\text-generation-webui

REM ---- Enable OpenAI-compatible API Server ----
REM UI will run on port 7860
REM API will run on port 5001 (default)
set CLI_ARGS=--api

python server.py ^
    --listen ^
    --listen-host 127.0.0.1 ^
    --listen-port 7860 ^
    --api ^
    --api-port 5001 ^
    --model "openhermes-2.5-mistral-7b.Q5_K_M.gguf" ^
    --loader llama.cpp ^
    --extensions orion_ltm

pause
