@echo off
title Marketing Jarvis
echo ============================
echo  MARKETING JARVIS — STARTING
echo ============================
cd /d "%~dp0"

echo [1/2] Starting Python backend on port 8000...
start "Jarvis Backend" cmd /k "python backend\main.py"

echo [2/2] Waiting 3s then launching Electron...
timeout /t 3 /nobreak > nul

call npm run dev
