#!/bin/sh
# Production container entrypoint: wait for MySQL, apply migrations, then hand
# off to gunicorn. The dev compose overrides `command:` and never runs this.
set -e

echo "[entrypoint] Waiting for the database to accept connections..."
python - <<'PY'
import os, sys, time
import sqlalchemy

url = os.environ["DATABASE_URL"]
for attempt in range(1, 31):
    try:
        sqlalchemy.create_engine(url).connect().close()
        print("[entrypoint] Database is ready")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint] DB not ready ({attempt}/30): {e}")
        time.sleep(2)
sys.exit("[entrypoint] ERROR: database never became reachable")
PY

echo "[entrypoint] Applying database migrations (flask db upgrade)..."
flask db upgrade

echo "[entrypoint] Starting gunicorn..."
# gthread workers: each analysis request holds a thread for the full multi-minute
# Anthropic stream, so sync workers would cap concurrent analyses at the worker
# count. 2 workers x 8 threads = 16 concurrent requests. Timeout must exceed the
# longest paid-tier generation (see anthropic_service.py timeout handling).
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --worker-class gthread \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-8}" \
    --timeout "${GUNICORN_TIMEOUT:-300}" \
    --access-logfile - \
    --error-logfile - \
    run:app
