#!/bin/bash
# Start Celery worker in background
celery -A app.workers.celery_app worker --loglevel=info --concurrency=4 --pool=prefork &

# Start FastAPI (foreground)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
