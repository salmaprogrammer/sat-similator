"""Celery-wrapped ingestion task.

Register in prod by importing this module in celery_worker.py; the sync path
in `app.services.ingest.pipeline.parse_import` remains the default in dev.
"""
from __future__ import annotations

try:
    from celery_worker import celery

    @celery.task(name="ingest.parse_import")
    def parse_import_task(import_id: int) -> None:
        from app.services.ingest.pipeline import parse_import
        parse_import(import_id)
except Exception:  # noqa: BLE001
    # Celery not initialized (e.g. running Flask CLI without broker); ignore.
    def parse_import_task(import_id: int) -> None:  # type: ignore[no-redef]
        from app.services.ingest.pipeline import parse_import
        parse_import(import_id)
