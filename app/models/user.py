from __future__ import annotations
from datetime import datetime, date
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import String, Boolean, DateTime, Date, ForeignKey, Integer, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models.enums import Role, Accommodation


def _enum(enum_cls):
    return SAEnum(enum_cls, values_callable=lambda e: [m.value for m in e], native_enum=False)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.STUDENT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    student: Mapped[Optional["Student"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher: Mapped[Optional["Teacher"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT


class Student(db.Model):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    accommodation: Mapped[Accommodation] = mapped_column(_enum(Accommodation), default=Accommodation.STANDARD, nullable=False)
    exam_type: Mapped[Optional[str]] = mapped_column(String(64))
    test_date: Mapped[Optional[date]] = mapped_column(Date)
    current_score: Mapped[Optional[int]] = mapped_column(Integer)
    goal_score: Mapped[Optional[int]] = mapped_column(Integer)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    study_days: Mapped[Optional[dict]] = mapped_column(JSON)
    calendar_synced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pro_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="student")

    @property
    def is_pro(self) -> bool:
        return self.pro_expires_at is not None and self.pro_expires_at > datetime.utcnow()


class Teacher(db.Model):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    org: Mapped[Optional[str]] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="teacher")
