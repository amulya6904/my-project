#!/bin/bash

# Start the FastAPI backend server
echo "Starting Bank Statement Processor API..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
export JWT_SECRET_KEY="your-secret-key-change-in-production"

# Start the API server
echo "Starting FastAPI server on http://localhost:8000"
python -m src.api.main
