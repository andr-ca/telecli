#!/bin/bash

# TeleCLI - Web Server Launcher

set -e

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please create .env from .env.sample:"
    echo "  cp .env.sample .env"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Run web app
echo "Starting TeleCLI web server..."
uvicorn src.web_app:app --host 0.0.0.0 --port 8000 --reload
