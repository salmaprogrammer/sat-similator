"""Celery entrypoint. Run with:  celery -A celery_worker.celery worker --loglevel=info"""
from celery import Celery
from app import create_app
from config import get_config

flask_app = create_app()
cfg = get_config()

celery = Celery(
    "satsimilator",
    broker=cfg.CELERY_BROKER_URL,
    backend=cfg.CELERY_RESULT_BACKEND,
)


class FlaskTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)


celery.Task = FlaskTask
