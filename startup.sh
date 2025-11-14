#!/bin/bash

set -e
cd "$(dirname "$0")"

# Optional: list contents for debugging
ls -la

# Dependencies are already installed by Oryx during deployment
# No need to pip install here - it causes timeouts

# Debugging output
echo "FLASK_APP: $FLASK_APP"
echo "Running on PORT: $PORT"

# Use Gunicorn if on Azure
if [[ -n "$WEBSITES_PORT" ]]; then
  echo "Starting Flask application with Gunicorn on port ${PORT}..."
  exec gunicorn --bind=0.0.0.0:${PORT} --workers=4 --timeout 600 app:app
else
  echo "Starting Flask application locally on port ${PORT}..."
  exec flask run --host=0.0.0.0 --port=${PORT}
fi