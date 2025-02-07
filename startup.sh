#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Navigate to the directory containing the script
cd "$(dirname "$0")"

# Detect and use the available Python version (preferring 3.10, then 3.9)
if command -v python3.10 &>/dev/null; then
  PYTHON_CMD=python3.10
elif command -v python3.9 &>/dev/null; then
  PYTHON_CMD=python3.9
else
  echo "Error: Neither Python 3.10 nor 3.9 is installed."
  exit 1
fi

# Ensure the virtual environment exists
if [ ! -d ".venv" ]; then
  $PYTHON_CMD -m venv .venv
fi

# Activate the virtual environment
source .venv/bin/activate

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

# Set the Flask app environment variable
export FLASK_APP=app.py

# Check if running on Azure App Service
if [[ -n "$WEBSITES_PORT" ]]; then
  # Running on Azure App Service

  # Start the Flask app using Gunicorn
  echo "Starting Flask application with Gunicorn on port ${PORT:-8000}..."
  exec gunicorn --bind=0.0.0.0:${PORT:-8000} --timeout 600 app:app
else
  # Running locally

  # Install system dependencies
  sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-dev

  # Start the Flask app using the built-in server
  echo "Starting Flask application locally on port ${PORT:-8000}..."
  exec flask run --host=0.0.0.0 --port=${PORT:-8000}
fi
