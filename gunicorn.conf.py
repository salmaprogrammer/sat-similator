"""Gunicorn configuration for production.

Run with:  gunicorn -c gunicorn.conf.py flask_app:app
"""
import multiprocessing
import os

# Railway / Fly.io / Render inject $PORT; fall back to 5000 in dev.
_port = os.getenv("PORT", "5000")
bind = os.getenv("GUNICORN_BIND", f"0.0.0.0:{_port}")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
timeout = 60
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# So SQLAlchemy engine + Flask app aren't created before forking:
preload_app = False
