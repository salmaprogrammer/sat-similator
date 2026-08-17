"""Ingestion orchestrator.

parse_import(import_id) runs the full pipeline for a QuestionImport row:
  1. Fetch file from storage
  2. Dispatch by source_type -> raw text
  3. LLM/heuristic extraction -> a list of items
  4. Write one QuestionImportItem per detected question
  5. Flip status to 'parsed' (or 'failed' with error_reason)

Callable synchronously in dev; wrap with Celery task in prod (see app/tasks/ingest.py).
"""
from __future__ import annotations
from datetime import datetime

from flask import current_app

from app.extensions import db
from app.models.ingest import QuestionImport, QuestionImportItem
from app.models.enums import ImportStatus, SourceType, AnswerSource
from app.services import storage
from app.services.ingest import parse_docx, parse_pdf, parse_md, llm_extract


def parse_import(import_id: int) -> None:
    imp = db.session.get(QuestionImport, import_id)
    if imp is None:
        return
    imp.status = ImportStatus.PARSING
    db.session.commit()

    try:
        data = storage.read_file(imp.file_url)
        text = _dispatch(imp.source_type, data)
        items = llm_extract.extract(text)
        _persist_items(imp, items)
        imp.status = ImportStatus.PARSED
        imp.parsed_at = datetime.utcnow()
        imp.prompt_version = current_app.config.get("INGEST_PROMPT_VERSION", "v1")
        db.session.commit()
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("parse_import failed for %s", import_id)
        imp.status = ImportStatus.FAILED
        imp.error_reason = f"{type(e).__name__}: {e}"
        db.session.commit()


def _dispatch(source_type: SourceType, data: bytes) -> str:
    if source_type == SourceType.DOCX:
        return parse_docx.extract_text(data)
    if source_type == SourceType.PDF:
        return parse_pdf.extract_text(data)
    if source_type == SourceType.MD:
        return parse_md.extract_text(data)
    raise ValueError(f"Unknown source_type: {source_type}")


def _persist_items(imp: QuestionImport, items: list) -> None:
    # Clear any prior items (in case of re-parse)
    for it in list(imp.items):
        db.session.delete(it)
    db.session.flush()

    for idx, it in enumerate(items):
        source_str = it.get("answer_source") or "missing"
        try:
            source = AnswerSource(source_str)
        except ValueError:
            source = AnswerSource.MISSING

        row = QuestionImportItem(
            import_id=imp.id,
            order_index=idx,
            raw_text=it.get("raw_text"),
            parsed_stem=it.get("stem"),
            parsed_choices=it.get("choices"),
            parsed_answer=it.get("answer"),
            answer_source=source,
            confidence_score=it.get("confidence"),
            suggested_topic=it.get("topic"),
            suggested_difficulty=it.get("difficulty"),
        )
        db.session.add(row)
    db.session.flush()
