from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer, JSON, Float, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import ImportStatus, SourceType, AnswerSource, ImportItemStatus
from app.models.user import _enum


class QuestionImport(db.Model):
    __tablename__ = "question_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    bank_id: Mapped[Optional[int]] = mapped_column(ForeignKey("question_banks.id"))
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(_enum(SourceType), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(_enum(ImportStatus), default=ImportStatus.UPLOADED, nullable=False)
    error_reason: Mapped[Optional[str]] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    items: Mapped[List["QuestionImportItem"]] = relationship(
        back_populates="import_", cascade="all, delete-orphan", order_by="QuestionImportItem.order_index"
    )


class QuestionImportItem(db.Model):
    __tablename__ = "question_import_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("question_imports.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    parsed_stem: Mapped[Optional[str]] = mapped_column(Text)
    parsed_choices: Mapped[Optional[list]] = mapped_column(JSON)  # [{"label":"A","text":"..."}, ...] or null
    parsed_answer: Mapped[Optional[str]] = mapped_column(Text)  # choice label OR JSON-encoded list of accepted strings
    answer_source: Mapped[AnswerSource] = mapped_column(_enum(AnswerSource), default=AnswerSource.MISSING, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    suggested_topic: Mapped[Optional[str]] = mapped_column(String(128))
    suggested_difficulty: Mapped[Optional[str]] = mapped_column(String(32))

    status: Mapped[ImportItemStatus] = mapped_column(
        _enum(ImportItemStatus), default=ImportItemStatus.PENDING_REVIEW, nullable=False
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resulting_question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("questions.id"))

    import_: Mapped[QuestionImport] = relationship(back_populates="items")
