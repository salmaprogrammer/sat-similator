FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for pdfplumber, weasyprint, psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev libpango-1.0-0 libpangoft2-1.0-0 \
        libcairo2 libjpeg-dev libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

ENV FLASK_APP=flask_app.py
EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "flask_app:app"]
