#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "============================"
echo " MARKETING JARVIS — STARTING"
echo "============================"

python3 backend/main.py &
BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null" EXIT
echo "[backend] PID $BACKEND_PID"

sleep 3
npm run dev
