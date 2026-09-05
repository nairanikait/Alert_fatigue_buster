#!/usr/bin/env bash
set -e

echo "=================================================="
echo " Starting ALERT FATIGUE BUSTER Full-Stack System "
echo "=================================================="

# Ensure backend venv exists
if [ ! -d "backend/venv" ]; then
    echo "Creating backend virtual environment..."
    python3 -m venv backend/venv
    ./backend/venv/bin/pip install -r backend/requirements.txt
fi

# Ensure frontend dependencies exist
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

echo "Starting Backend API on http://localhost:8000..."
(
    cd backend
    export PYTHONPATH=.
    ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID=$!

echo "Starting Frontend UI on http://localhost:5173..."
(
    cd frontend
    npm run dev
) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT

echo ""
echo "System online:"
echo "-> Frontend: http://localhost:5173"
echo "-> Backend API: http://localhost:8000"
echo "-> Swagger Docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop all services."

wait
