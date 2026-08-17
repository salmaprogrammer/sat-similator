"""Gunicorn configuration for production.

Run with:  gunicorn -c gunicorn.conf.py flask_app:app
"""
import os

# Railway / Fly.io / Render inject $PORT; fall back to 5000 in dev.
_port = os.getenv("PORT", "5000")
bind = os.getenv("GUNICORN_BIND", f"0.0.0.0:{_port}")

# NEVER use multiprocessing.cpu_count() as a default — on Railway/Fly containers
# it returns the HOST cpu count (32+), which spawns ~65 workers and OOMs a
# 512MB container. Default to 2 workers; override via GUNICORN_WORKERS.
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "sync"
timeout = 60
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# So SQLAlchemy engine + Flask app aren't created before forking:
preload_app = False
