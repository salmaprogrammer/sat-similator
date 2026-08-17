"""Gunicorn configuration for production.

Run with:  gunicorn -c gunicorn.conf.py flask_app:app
"""
import os

# Railway / Fly.io / Render inject $PORT; fall back to 5000 in dev.
_port = os.getenv("PORT", "5000")
bind = os.getenv("GUNICORN_BIND", f"0.0.0.0:{_port}")

# Container memory on Railway free/hobby is tight (512MB). One worker fits
# comfortably; bump via GUNICORN_WORKERS after upgrading the plan.
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
worker_class = "sync"
# Concurrency without per-worker RAM cost:
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = 120
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Preload the app before forking so workers share read-only memory pages
# (copy-on-write). Safe here because Flask-SQLAlchemy creates its engine
# lazily on first request per worker.
preload_app = True
