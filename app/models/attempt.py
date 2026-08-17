from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import AttemptStatus, Accommodation, ModuleVariant
from app.models.user import _enum


class Attempt(db.Model):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(_enum(AttemptStatus), default=AttemptStatus.IN_PROGRESS, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    accommodation_snapshot: Mapped[Accommodation] = mapped_column(_enum(Accommodation), default=Accommodation.STANDARD, nullable=False)
    is_practice: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # controls allow_early_resume on break

    # Post-test survey (§2.8)
    feedback_nps: Mapped[Optional[int]] = mapped_column(Integer)
    feedback_difficulty: Mapped[Optional[int]] = mapped_column(Integer)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)

    attempt_modules: Mapped[List["AttemptModule"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", order_by="AttemptModule.id"
    )
    responses: Mapped[List["Response"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")
    score: Mapped[Optional["AttemptScore"]] = relationship(back_populates="attempt", uselist=False, cascade="all, delete-orphan")


class AttemptModule(db.Model):
    __tablename__ = "attempt_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    module_id: Mapped[int] = mapped_column(ForeignKey("exam_modules.id"), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_difficulty_label: Mapped[Optional[str]] = mapped_column(String(64))  # e.g. "Math – Module 2 (Easy)"
    resolved_variant: Mapped[Optional[ModuleVariant]] = mapped_column(_enum(ModuleVariant))
    effective_time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    break_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    break_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    attempt: Mapped[Attempt] = relationship(back_populates="attempt_modules")


class Response(db.Model):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    choice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("choices.id"))
    free_response_text: Mapped[Optional[str]] = mapped_column(String(255))
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    strikethrough_state: Mapped[Optional[dict]] = mapped_column(JSON)  # {"enabled": bool, "struck": ["A", "C"]}
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    attempt: Mapped[Attempt] = relationship(back_populates="responses")


class AttemptScore(db.Model):
    __tablename__ = "attempt_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), unique=True, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    rw: Mapped[int] = mapped_column(Integer, nullable=False)
    math: Mapped[int] = mapped_column(Integer, nullable=False)
    per_topic: Mapped[Optional[dict]] = mapped_column(JSON)
    per_difficulty_time: Mapped[Optional[dict]] = mapped_column(JSON)  # {"easy": secs, "medium": secs, "hard": secs}

    attempt: Mapped[Attempt] = relationship(back_populates="score")
