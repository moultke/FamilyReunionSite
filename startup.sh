#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Navigate to the directory containing the script
cd "$(dirname "$0")"

# Detect and use the available Python version (prefer 3.10, then 3.9)
if command -v python3.10 &>/dev/null; then
  PYTHON_CMD=python3.10
elif command -v python3.9 &>/dev/null; then
  PYTHON_CMD=python3.9
else
  echo "Error: Neither Python 3.10 nor 3.9 is installed."
  exit 1
fi

# Ensure the virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
  $PYTHON_CMD -m venv venv
fi

# Activate the virtual environment
if [ -d "venv" ]; then
  source venv/bin/activate
elif [ -d ".venv" ]; then
  source .venv/bin/activate
else
  echo "Error: No virtual environment found."
  exit 1
fi

# Ensure `requirements.txt` exists before installing dependencies
if [ ! -f requirements.txt ]; then
  echo "Error: requirements.txt not found!"
  exit 1
fi

# Install dependencies
pip install --no-cache-dir -r requirements.txt

# Ensure `wheel` is installed to prevent legacy install issues
pip install --no-cache-dir wheel

# Set the Flask app environment variable
export FLASK_APP=app.py
export PORT=${PORT:-8000}  # Set PORT default to 8000 if not set

# Debugging: Print environment variables
echo "FLASK_APP: $FLASK_APP"
echo "Running on PORT: $PORT"

# Check if running on Azure App Service
if [[ -n "$WEBSITES_PORT" ]]; then
  # Running on Azure App Service
  echo "Starting Flask application with Gunicorn on port ${PORT}..."
  exec gunicorn --bind=0.0.0.0:${PORT} --workers=4 --timeout 600 app:app
else
  # Running locally
  echo "Starting Flask application locally on port ${PORT}..."
  exec flask run --host=0.0.0.0 --port=${PORT}
fi