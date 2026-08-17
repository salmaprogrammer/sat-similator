web: gunicorn -c gunicorn.conf.py flask_app:app
worker: celery -A celery_worker.celery worker --loglevel=info
release: flask db upgrade && flask seed
