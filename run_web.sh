#!/bin/bash

# TeleCLI - Web Server Launcher

set -e

SCRIPT_PATH="${BASH_SOURCE[0]}"
if [[ "$SCRIPT_PATH" != */* ]]; then
    SCRIPT_PATH="./$SCRIPT_PATH"
fi
SCRIPT_DIR="$(cd "${SCRIPT_PATH%/*}" && pwd)"
cd "$SCRIPT_DIR"

parent_dir() {
    local dir="$1"
    dir="${dir%/}"

    if [ -z "$dir" ] || [ "$dir" = "/" ]; then
        printf '/\n'
        return 0
    fi

    dir="${dir%/*}"
    if [ -z "$dir" ]; then
        printf '/\n'
    else
        printf '%s\n' "$dir"
    fi
}

find_env_file() {
    local dir="$SCRIPT_DIR"
    while true; do
        if [ -f "$dir/.env" ]; then
            printf '%s\n' "$dir/.env"
            return 0
        fi
        if [ "$dir" = "/" ]; then
            break
        fi
        dir="$(parent_dir "$dir")"
    done
    return 1
}

# Check if .env exists locally or in a parent checkout directory
ENV_FILE="$(find_env_file || true)"
if [ -z "$ENV_FILE" ]; then
    echo "Error: .env file not found"
    echo "Please create .env from .env.sample:"
    echo "  cp .env.sample .env"
    exit 1
fi

echo "Using environment file: $ENV_FILE"

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

# Run application entrypoint
echo "Starting TeleCLI application..."
exec python -m src.main
