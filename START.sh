#!/bin/bash
# MerakiMind — Startup Script

# Navigate to the script's directory so all relative paths resolve correctly
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "🧹 Cleaning up existing processes on ports 8765 and 5173..."
# Kill process on port 8765 (Backend)
PORT_8765_PID=$(lsof -t -i :8765)
if [ ! -z "$PORT_8765_PID" ]; then
    echo "  Killing existing backend process (PID $PORT_8765_PID)..."
    kill -9 $PORT_8765_PID 2>/dev/null
fi

# Kill process on port 5173 (Frontend)
PORT_5173_PID=$(lsof -t -i :5173)
if [ ! -z "$PORT_5173_PID" ]; then
    echo "  Killing existing frontend process (PID $PORT_5173_PID)..."
    kill -9 $PORT_5173_PID 2>/dev/null
fi
sleep 1

echo "🚀 Starting MerakiMind Multi-Agent Backend..."
python3 server.py &
BACKEND_PID=$!

echo "🚀 Starting React + Vite Frontend Dev Server..."
cd frontend
npm run dev &
FRONTEND_PID=$!

# Trap Ctrl+C (SIGINT) and SIGTERM to clean up both child processes
cleanup() {
    echo -e "\n🛑 Stopping MerakiMind processes..."
    echo "  Stopping backend (PID $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null
    echo "  Stopping frontend (PID $FRONTEND_PID)..."
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

sleep 3
open "http://localhost:5173"
echo "✅ Dashboard launched at http://localhost:5173"
echo "🛑 Press Ctrl+C to stop both servers"

# Wait for background processes
wait
