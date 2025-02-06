#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Ensure the script runs from the project root
cd "$(dirname "$0")"

# Ensure virtual environment exists and is created using Python 3.10
if [ ! -d ".venv" ]; then
  python3.10 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Ensure system dependencies are installed
apt-get update && apt-get install -y libgl1 libglib2.0-dev

# Ensure Python dependencies are installed
pip install --no-cache-dir -r requirements.txt

# Start Gunicorn on the correct Azure Web App port
exec gunicorn --workers 4 --bind 0.0.0.0:${PORT:-8000} app:app
