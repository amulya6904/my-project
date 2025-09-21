#!/bin/bash

# Start the React frontend development server
echo "Starting Bank Statement Processor Frontend..."

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install
fi

# Start the development server
echo "Starting React development server on http://localhost:3000"
echo "The frontend will automatically connect to the API at http://localhost:8000"
npm start