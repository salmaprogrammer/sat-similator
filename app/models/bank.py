from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import QuestionType, Difficulty, QuestionSource
from app.models.user import _enum


class QuestionBank(db.Model):
    __tablename__ = "question_banks"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    questions: Mapped[List["Question"]] = relationship(back_populates="bank", cascade="all, delete-orphan")


class Question(db.Model):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("question_banks.id"), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[QuestionType] = mapped_column(_enum(QuestionType), default=QuestionType.MCQ, nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(String(128))
    difficulty: Mapped[Difficulty] = mapped_column(_enum(Difficulty), default=Difficulty.MEDIUM, nullable=False)
    source: Mapped[QuestionSource] = mapped_column(_enum(QuestionSource), default=QuestionSource.AUTHORED, nullable=False)
    # For free-response: JSON-encoded list of acceptable answer strings (numerically compared)
    acceptable_answers: Mapped[Optional[str]] = mapped_column(Text)
    # Optional passage/stimulus rendered in the left pane during the test (RW mainly)
    passage_text: Mapped[Optional[str]] = mapped_column(Text)
    # Optional image (graph, diagram, or scanned passage). Storage handle: file:// or s3://
    image_url: Mapped[Optional[str]] = mapped_column(String(1024))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    bank: Mapped[QuestionBank] = relationship(back_populates="questions")
    choices: Mapped[List["Choice"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="Choice.label"
    )


class Choice(db.Model):
    __tablename__ = "choices"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(2), nullable=False)  # A, B, C, D
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    question: Mapped[Question] = relationship(back_populates="choices")
