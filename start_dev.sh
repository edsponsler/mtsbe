#!/bin/bash

# start_dev.sh
# Script to spin up the MTSBE local development environment

echo "Starting MTSBE development environment..."

# Start Cloud SQL Proxy in the background
echo "Starting cloud-sql-proxy..."
cloud-sql-proxy mtsbe-1208613:us-central1:mtsbe-db &
PROXY_PID=$!

# Wait for the proxy to initialize
sleep 3

# Start the FastAPI backend
echo "Starting Uvicorn backend..."
source .venv/bin/activate
uvicorn src.api.main:app --port 8000 --reload &
BACKEND_PID=$!

# Start the Next.js frontend
echo "Starting Next.js frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "==========================================================="
echo "✅ MTSBE Environment is running!"
echo ""
echo "🔗 Backend API Docs: http://127.0.0.1:8000/docs"
echo "🔗 Frontend UI:      http://localhost:3000"
echo "==========================================================="
echo ""
echo "Press Ctrl+C to stop all services."

# Trap Ctrl+C to gracefully kill background processes
trap "echo 'Stopping services...'; kill $PROXY_PID $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM

# Wait indefinitely to keep the script running
wait
