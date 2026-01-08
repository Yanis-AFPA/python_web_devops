#!/bin/bash

# Wait for database
echo "Attente de la base de données..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "Base de données prête !"

# Run database initialization logic (we will implement this in Python in main.py or a pre-start script)
# For now, we rely on the app startup event to create tables if they don't exist

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
