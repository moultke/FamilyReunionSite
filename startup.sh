#!/bin/bash

# Exit on any error
set -e

# Ensure script runs from project root
cd "$(dirname "$0")"

# Detect and use the correct Python version (3.10 preferred, fallback to 3.9)
if command -v python3.10 &>/dev/null; then
  PYTHON_CMD=python3.10
elif command -v python3.9 &>/dev/null; then
  PYTHON_CMD=python3.9
else
  echo "Error: Neither Python 3.10 nor 3.9 is installed."
  exit 1
fi

# Ensure virtual environment exists
if [ ! -d ".venv" ]; then
  $PYTHON_CMD -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Check if running on Azure App Service and skip apt-get if so
if [[ -z "$WEBSITES_PORT" ]]; then
  apt-get update && apt-get install -y libgl1 libglib2.0-dev
fi

# Ensure Python dependencies are installed
pip install --no-cache-dir -r requirements.txt

# Ensure Flask is installed
pip install --no-cache-dir flask

# Set Flask app environment variable
export FLASK_APP=app

# Log message for debugging
echo "Starting Flask application on port ${PORT:-8000}..."

# Start Flask app
exec flask run --host=0.0.0.0 --port=${PORT:-8000}

