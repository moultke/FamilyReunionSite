#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Ensure the script runs from the project root
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Ensure system dependencies are installed
apt-get update && apt-get install -y libgl1 libglib2.0-dev

# Start Gunicorn
exec gunicorn --workers 4 --bind 0.0.0.0:8000 app:app