"""Shared seed logic used by both the `flask seed` CLI and the /admin/init-db
endpoint. Idempotent — safe to run multiple times.
"""
from __future__ import annotations

from app.extensions import db
from app.models import (
    User, Student, Teacher,
    QuestionBank, Question, Choice,
    Exam, ExamModule, ExamModuleQuestion,
)
from app.models.enums import Role, QuestionType, Difficulty, Section, ModuleVariant


def seed_demo_data() -> dict:
    """Insert demo teacher/student/bank/exam if not already present.
    Returns a summary dict.
    """
    if User.query.filter_by(email="teacher@example.com").first():
        return {"created": False, "reason": "already seeded"}

    teacher_user = User(email="teacher@example.com", role=Role.TEACHER)
    teacher_user.set_password("password")
    teacher = Teacher(user=teacher_user, org="Demo School")

    student_user = User(email="student@example.com", role=Role.STUDENT)
    student_user.set_password("password")
    student = Student(user=student_user, onboarding_completed=True)

    db.session.add_all([teacher_user, teacher, student_user, student])
    db.session.flush()

    bank = QuestionBank(teacher_id=teacher.id, name="Demo Bank")
    db.session.add(bank)
    db.session.flush()

    q1 = Question(
        bank_id=bank.id, stem="If 3x + 5 = 20, what is the value of x?",
        type=QuestionType.MCQ, topic="Algebra", difficulty=Difficulty.EASY,
    )
    q2 = Question(
        bank_id=bank.id, stem="A circle has radius 4. What is its area, in terms of π?",
        type=QuestionType.MCQ, topic="Geometry", difficulty=Difficulty.MEDIUM,
    )
    db.session.add_all([q1, q2])
    db.session.flush()

    for label, text, correct in [("A", "3", False), ("B", "5", True), ("C", "15", False), ("D", "25", False)]:
        db.session.add(Choice(question_id=q1.id, label=label, text=text, is_correct=correct))
    for label, text, correct in [("A", "4π", False), ("B", "8π", False), ("C", "16π", True), ("D", "32π", False)]:
        db.session.add(Choice(question_id=q2.id, label=label, text=text, is_correct=correct))

    exam = Exam(name="Demo Practice Test", teacher_id=teacher.id, is_published=True)
    db.session.add(exam)
    db.session.flush()

    math_m1 = ExamModule(
        exam_id=exam.id, section=Section.MATH, module_number=1,
        time_limit_seconds=35 * 60, calculator_allowed=True, difficulty_variant=ModuleVariant.FIXED,
    )
    db.session.add(math_m1)
    db.session.flush()
    db.session.add_all([
        ExamModuleQuestion(module_id=math_m1.id, question_id=q1.id, order_index=0),
        ExamModuleQuestion(module_id=math_m1.id, question_id=q2.id, order_index=1),
    ])

    db.session.commit()
    return {
        "created": True,
        "teacher": "teacher@example.com",
        "student": "student@example.com",
        "password": "password",
        "bank": bank.name,
        "exam": exam.name,
    }
