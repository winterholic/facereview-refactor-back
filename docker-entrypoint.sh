#!/bin/bash
set -e

# PORT 환경변수가 설정되지 않은 경우 기본값 사용
PORT=${PORT:-5000}

echo "Starting Gunicorn on port $PORT..."

# Gunicorn 실행
exec gunicorn \
    --bind "0.0.0.0:$PORT" \
    --workers 4 \
    --worker-class eventlet \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile /app/logs/access.log \
    --error-logfile /app/logs/error.log \
    --log-level info \
    "run:app"
