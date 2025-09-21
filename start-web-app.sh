#!/bin/bash

# Unified startup script for Bank Statement Processor Web App

echo "🏦 Starting Bank Statement Processor Web Application..."

# Function to kill background processes on exit
cleanup() {
    echo "Shutting down services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        echo "Backend stopped."
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
        echo "Frontend stopped."
    fi
    exit 0
}

# Trap exit signals
trap cleanup EXIT INT TERM

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Start Backend API
echo "🔧 Starting Backend API..."
cd "$(dirname "$0")"
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
python -m src.api.simple_main &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend is running
if ! curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Backend failed to start"
    exit 1
fi

echo "✅ Backend started successfully at http://localhost:8000"

# Start Frontend (React)
echo "🎨 Starting Frontend..."
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

npm start &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 5

echo ""
echo "🎉 Bank Statement Processor is now running!"
echo ""
echo "📋 Services:"
echo "   Backend API: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo "   Frontend Web App: http://localhost:3000"
echo ""
echo "🔍 Supported Banks:"
echo "   • Union Bank of India"
echo "   • State Bank of India"
echo ""
echo "📝 Usage:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Upload a PDF bank statement"
echo "   3. View extracted transactions"
echo "   4. Download CSV file"
echo ""
echo "⚡ Features:"
echo "   • Direct PDF processing (no WebSocket complexity)"
echo "   • Real-time results"
echo "   • CSV export functionality"
echo "   • Mobile-friendly interface"
echo ""
echo "Press Ctrl+C to stop all services"

# Keep script running and wait for user interruption
while true; do
    sleep 1
done