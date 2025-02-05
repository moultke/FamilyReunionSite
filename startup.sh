#!/bin/bash
# Activate virtual environment
source venv/bin/activate

# Install missing dependencies
apt-get update && apt-get install -y libgl1

# Start Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app