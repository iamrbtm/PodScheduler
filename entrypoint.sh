#!/bin/bash
set -e

echo "Running database migrations..."
flask db upgrade

echo "Seeding initial data..."
flask seed

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 "app:create_app()"
