#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting SafeHarbor API..."
exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
