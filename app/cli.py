"""Flask CLI commands: seed, reset-db."""
from __future__ import annotations
import click
from flask import Flask
from flask.cli import with_appcontext

from app.extensions import db


def register_cli(app: Flask) -> None:
    app.cli.add_command(seed_cmd)
    app.cli.add_command(reset_db_cmd)


@click.command("seed")
@with_appcontext
def seed_cmd():
    """Seed the DB with a teacher, a student, a small question bank, and one exam."""
    from app.models import (
        User, Student, Teacher, QuestionBank, Question, Choice,
        Exam, ExamModule, ExamModuleQuestion,
    )
    from app.models.enums import Role, QuestionType, Difficulty, Section, ModuleVariant

    if User.query.filter_by(email="teacher@example.com").first():
        click.echo("Already seeded.")
        return

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
    click.echo("Seeded: teacher@example.com / student@example.com  (password: password)")


@click.command("reset-db")
@with_appcontext
def reset_db_cmd():
    """Drop and recreate all tables. Dev only."""
    click.confirm("This will DROP ALL TABLES. Continue?", abort=True)
    db.drop_all()
    db.create_all()
    click.echo("Database reset.")
