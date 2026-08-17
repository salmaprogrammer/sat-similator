"""11-step onboarding wizard per §2.2 of the plan.

Steps:
  1. Role gate (skip if teacher)
  2. Exam type
  3. Test date
  4. Current score
  5. Goal score
  6. Proof chart (informational only)
  7. Email opt-in
  8. Study plan start date
  9. Study days
 10. Calendar sync (skippable in v1)
 11. Paywall (skippable in v1)
"""
from __future__ import annotations
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.blueprints.onboarding.forms import (
    Step2ExamType, Step3TestDate, Step4CurrentScore, Step5GoalScore,
    Step7EmailOptIn, Step8StudyStart, Step9StudyDays,
)

bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")

TOTAL_STEPS = 11


def _student_or_redirect():
    if not current_user.is_authenticated:
        return None, redirect(url_for("auth.login"))
    if not current_user.is_student or current_user.student is None:
        return None, redirect(url_for("main.index"))
    return current_user.student, None


@bp.route("/step/<int:n>", methods=["GET", "POST"])
@login_required
def step(n: int):
    if n < 1 or n > TOTAL_STEPS:
        abort(404)

    student, redir = _student_or_redirect()
    if redir:
        return redir

    handler = _HANDLERS.get(n, _informational_step)
    return handler(n, student)


# ---------------------------------------------------------------------------
# Per-step handlers
# ---------------------------------------------------------------------------

def _informational_step(n: int, student):
    """Renders a static informational step (1, 6, 10, 11) with just Continue/Skip."""
    if request.method == "POST":
        return _advance(n, student)
    template = f"onboarding/step_{n}.html"
    return render_template(
        template, n=n, total=TOTAL_STEPS,
        next_url=url_for("onboarding.step", n=n + 1) if n < TOTAL_STEPS else None,
    )


def _step_2(n, student):
    form = Step2ExamType(exam_type=student.exam_type or "sat")
    if form.validate_on_submit():
        student.exam_type = form.exam_type.data
        return _advance(n, student)
    return render_template("onboarding/step_2.html", form=form, n=n, total=TOTAL_STEPS)


def _step_3(n, student):
    form = Step3TestDate(test_date=student.test_date)
    if form.validate_on_submit():
        student.test_date = form.test_date.data
        return _advance(n, student)
    return render_template("onboarding/step_3.html", form=form, n=n, total=TOTAL_STEPS)


def _step_4(n, student):
    form = Step4CurrentScore(current_score=student.current_score)
    if form.validate_on_submit():
        student.current_score = form.current_score.data
        return _advance(n, student)
    return render_template("onboarding/step_4.html", form=form, n=n, total=TOTAL_STEPS)


def _step_5(n, student):
    form = Step5GoalScore(goal_score=student.goal_score)
    if form.validate_on_submit():
        student.goal_score = form.goal_score.data
        return _advance(n, student)
    return render_template("onboarding/step_5.html", form=form, n=n, total=TOTAL_STEPS)


def _step_7(n, student):
    form = Step7EmailOptIn(email_opt_in=student.email_opt_in)
    if form.validate_on_submit():
        student.email_opt_in = form.email_opt_in.data
        return _advance(n, student)
    return render_template("onboarding/step_7.html", form=form, n=n, total=TOTAL_STEPS)


def _step_8(n, student):
    default = student.study_days.get("start") if student.study_days else None
    form = Step8StudyStart(study_start=_parse_date(default))
    if form.validate_on_submit():
        study_days = dict(student.study_days or {})
        study_days["start"] = form.study_start.data.isoformat() if form.study_start.data else None
        student.study_days = study_days
        return _advance(n, student)
    return render_template("onboarding/step_8.html", form=form, n=n, total=TOTAL_STEPS)


def _step_9(n, student):
    existing = (student.study_days or {}).get("days", [])
    form = Step9StudyDays(days=existing)
    if form.validate_on_submit():
        study_days = dict(student.study_days or {})
        study_days["days"] = form.days.data
        student.study_days = study_days
        return _advance(n, student)
    return render_template("onboarding/step_9.html", form=form, n=n, total=TOTAL_STEPS)


_HANDLERS = {
    2: _step_2, 3: _step_3, 4: _step_4, 5: _step_5,
    7: _step_7, 8: _step_8, 9: _step_9,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _advance(n: int, student):
    if n >= TOTAL_STEPS:
        student.onboarding_completed = True
        db.session.commit()
        flash("You're all set. Welcome!", "success")
        return redirect(url_for("student.dashboard"))
    db.session.commit()
    return redirect(url_for("onboarding.step", n=n + 1))


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except (TypeError, ValueError):
        return None
