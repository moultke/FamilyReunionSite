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
if [ ! -d "venv" ]; then
  $PYTHON_CMD -m venv venv
fi

# Activate the virtual environment (handles both `venv` and `.venv` cases)
source $(find . -type d -name "venv" -o -name ".venv")/bin/activate

# Ensure `requirements.txt` exists before installing dependencies
if [ ! -f requirements.txt ]; then
  echo "Error: requirements.txt not found!"
  exit 1
fi

pip install --no-cache-dir -r requirements.txt

# Set the Flask app environment variable
export FLASK_APP=app.py

# Debugging: Print environment variables
echo "FLASK_APP: $FLASK_APP"
echo "Running on PORT: ${PORT:-8000}"

# Check if running on Azure App Service
if [[ -n "$WEBSITES_PORT" ]]; then
  # Running on Azure App Service
  export PORT=${PORT:-8000}
  echo "Starting Flask application with Gunicorn on port ${PORT}..."
  exec gunicorn --bind=0.0.0.0:${PORT} --timeout 600 app:app
else
  # Running locally
  sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-dev
  echo "Starting Flask application locally on port ${PORT}..."
  exec flask run --host=0.0.0.0 --port=${PORT}
fi