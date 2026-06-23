#!/bin/bash
# Lancement en production via uvicorn (si Passenger non disponible)
# Utiliser avec: bash start.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

exec uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8001 \
  --workers 2 \
  --log-level info \
  --access-log
