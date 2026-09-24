#!/bin/bash
set -e

echo "Running database migrations..."
uv run flask db upgrade

echo "Seeding initial data..."
uv run flask seed

echo "Starting application..."
exec uv run gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 "app:create_app()"
