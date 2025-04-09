#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Navigate to the directory containing the script
cd "$(dirname "$0")"

ls - la

# Activate the virtual environment (assuming 'venv' is used)


if [ -d "venv" ]; then
  source venv/bin/activate
else
  echo "Error: Virtual environment 'venv' not found."
  exit 1
fi

# Debugging: Print environment variables (optional, for troubleshooting)
echo "FLASK_APP: $FLASK_APP"
echo "Running on PORT: $PORT"

# Check if running on Azure App Service to use Gunicorn, otherwise use Flask dev server
if [[ -n "$WEBSITES_PORT" ]]; then
  # Running on Azure App Service
  echo "Starting Flask application with Gunicorn on port ${PORT}..."
  exec gunicorn --bind=0.0.0.0:${PORT} --workers=4 --timeout 600 app:app
else
  # Running locally
  echo "Starting Flask application locally on port ${PORT}..."
  exec flask run --host=0.0.0.0 --port=${PORT}
fi