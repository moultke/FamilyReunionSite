FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV FLASK_APP=app.py

CMD ["gunicorn", "--bind=0.0.0.0:8000", "app:app"]

