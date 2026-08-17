from datetime import date

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.exam import Exam
from app.models.attempt import Attempt
from app.models.enums import Accommodation, AttemptStatus

bp = Blueprint("student", __name__, url_prefix="/student")


@bp.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_student:
        return redirect(url_for("main.index"))
    student = current_user.student
    if student and not student.onboarding_completed:
        return redirect(url_for("onboarding.step", n=1))

    recent_attempts = (
        Attempt.query.filter_by(student_id=student.id)
        .order_by(Attempt.started_at.desc())
        .limit(3).all()
    )
    completed = [a for a in recent_attempts if a.status == AttemptStatus.COMPLETED]

    days_until_test = None
    if student.test_date:
        days_until_test = (student.test_date - date.today()).days

    return render_template(
        "student/dashboard.html",
        student=student,
        recent_attempts=recent_attempts,
        completed_count=len([a for a in Attempt.query.filter_by(student_id=student.id).all() if a.status == AttemptStatus.COMPLETED]),
        latest_completed=completed[0] if completed else None,
        days_until_test=days_until_test,
    )


@bp.route("/tests")
@login_required
def tests():
    if not current_user.is_student:
        return redirect(url_for("main.index"))
    all_exams = Exam.query.filter_by(is_published=True).order_by(Exam.created_at.desc()).all()
    predicted = [e for e in all_exams if e.is_predicted_test]
    custom = [e for e in all_exams if not e.is_predicted_test]
    return render_template("student/tests.html", predicted=predicted, custom=custom)


@bp.route("/tests/<int:exam_id>/accommodations", methods=["GET", "POST"])
@login_required
def accommodations(exam_id):
    """§2.3 modal, shown before a timed test begins.
    Standard is always the default; students may pick 1.5x or 2x extra time.
    Persisted on Student.accommodation and re-applied on every subsequent attempt.
    """
    if not current_user.is_student:
        abort(403)
    exam = db.session.get(Exam, exam_id)
    if not exam or not exam.is_published:
        abort(404)

    student = current_user.student
    if request.method == "POST":
        choice = request.form.get("accommodation", Accommodation.STANDARD.value)
        try:
            student.accommodation = Accommodation(choice)
        except ValueError:
            student.accommodation = Accommodation.STANDARD
        db.session.commit()
        return redirect(url_for("student.instructions", exam_id=exam.id))

    return render_template("student/accommodations.html", exam=exam, student=student, Accommodation=Accommodation)


@bp.route("/tests/<int:exam_id>/instructions", methods=["GET"])
@login_required
def instructions(exam_id):
    """§2.4 pre-test info card."""
    exam = db.session.get(Exam, exam_id)
    if not exam or not exam.is_published:
        abort(404)
    return render_template("student/instructions.html", exam=exam)
