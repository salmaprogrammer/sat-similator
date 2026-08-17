from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.enums import Section, ModuleVariant
from app.models.user import _enum


class Exam(db.Model):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    teacher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teachers.id"))
    is_predicted_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    modules: Mapped[List["ExamModule"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan",
        order_by="(ExamModule.section, ExamModule.module_number)"
    )


class ExamModule(db.Model):
    __tablename__ = "exam_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), nullable=False)
    section: Mapped[Section] = mapped_column(_enum(Section), nullable=False)
    module_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    calculator_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    difficulty_variant: Mapped[ModuleVariant] = mapped_column(
        _enum(ModuleVariant), default=ModuleVariant.FIXED, nullable=False
    )

    exam: Mapped[Exam] = relationship(back_populates="modules")
    module_questions: Mapped[List["ExamModuleQuestion"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", order_by="ExamModuleQuestion.order_index"
    )


class ExamModuleQuestion(db.Model):
    __tablename__ = "exam_module_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("exam_modules.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    module: Mapped[ExamModule] = relationship(back_populates="module_questions")
    question = relationship("Question")
