#!/bin/bash

# Exit on any error
set -e

# Ensure script runs from project root
cd "$(dirname "$0")"

# Ensure Python 3.10 is installed
if ! command -v python3.10 &>/dev/null; then
  echo "Error: Python 3.10 is not installed."
  exit 1
fi

# Ensure virtual environment exists
if [ ! -d ".venv" ]; then
  python3.10 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Check if running on Azure App Service and skip apt-get if so
if [[ -z "$WEBSITES_PORT" ]]; then
  apt-get update && apt-get install -y libgl1 libglib2.0-dev
fi

# Ensure Python dependencies are installed
pip install --no-cache-dir -r requirements.txt

# Start Gunicorn on the correct Azure Web App port
exec gunicorn --workers 4 --bind 0.0.0.0:${WEBSITES_PORT:-8000} app:app

