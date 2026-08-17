"""Test-taking engine per §2.5 of the plan.

Attempt lifecycle:
  student clicks "Start" on a published exam
    -> POST /tests/<exam_id>/start
       creates Attempt (accommodation snapshot from Student.accommodation)
       creates AttemptModule for each module (effective_time_limit_seconds =
                                              module.time_limit_seconds * accommodation.multiplier)
       starts the first module (started_at = now)
       redirect to /attempt/<id>/module/1/question/1
"""
from __future__ import annotations
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, abort, request, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.exam import Exam, ExamModule, ExamModuleQuestion
from app.models.attempt import Attempt, AttemptModule, Response
from app.models.enums import AttemptStatus, Accommodation
from app.services.timer import module_seconds_remaining, module_is_expired

bp = Blueprint("test_engine", __name__)


# ---------------------------------------------------------------------------
# Start / resume
# ---------------------------------------------------------------------------

@bp.route("/tests/<int:exam_id>/start", methods=["POST"])
@login_required
def start(exam_id):
    if not current_user.is_student:
        abort(403)
    exam = db.session.get(Exam, exam_id)
    if not exam or not exam.is_published:
        abort(404)

    student = current_user.student
    accommodation = student.accommodation or Accommodation.STANDARD
    multiplier = accommodation.multiplier

    attempt = Attempt(
        student_id=student.id,
        exam_id=exam.id,
        status=AttemptStatus.IN_PROGRESS,
        accommodation_snapshot=accommodation,
        is_practice=True,
    )
    db.session.add(attempt)
    db.session.flush()

    for i, module in enumerate(exam.modules):
        am = AttemptModule(
            attempt_id=attempt.id,
            module_id=module.id,
            effective_time_limit_seconds=int(module.time_limit_seconds * multiplier),
        )
        if i == 0:
            am.started_at = datetime.utcnow()
        db.session.add(am)

    db.session.commit()
    return redirect(url_for("test_engine.question", attempt_id=attempt.id, module_num=1, q_idx=1))


# ---------------------------------------------------------------------------
# Question view
# ---------------------------------------------------------------------------

@bp.route("/attempt/<int:attempt_id>/module/<int:module_num>/question/<int:q_idx>")
@login_required
def question(attempt_id, module_num, q_idx):
    ctx = _load_context(attempt_id, module_num, q_idx)
    return render_template("test/engine.html", **ctx)


def _load_context(attempt_id: int, module_num: int, q_idx: int):
    attempt = db.session.get(Attempt, attempt_id)
    if not attempt or attempt.student_id != current_user.student.id:
        abort(404)
    if attempt.status == AttemptStatus.COMPLETED:
        # Redirect to results in Phase 10; for now just show a message
        abort(410)

    ordered_ams = attempt.attempt_modules  # ordered by id
    if module_num < 1 or module_num > len(ordered_ams):
        abort(404)
    am = ordered_ams[module_num - 1]
    module = db.session.get(ExamModule, am.module_id)
    module_questions = module.module_questions  # ordered by order_index

    if q_idx < 1 or q_idx > len(module_questions):
        abort(404)
    mq = module_questions[q_idx - 1]
    question = mq.question

    # Load/create response row
    response = _get_or_create_response(attempt.id, question.id)

    remaining = module_seconds_remaining(am)
    if module_is_expired(am):
        remaining = 0

    nav_items = _build_nav_items(attempt.id, module_questions, module_num, current_q_idx=q_idx)

    return {
        "attempt": attempt,
        "attempt_module": am,
        "module": module,
        "module_num": module_num,
        "total_modules": len(ordered_ams),
        "q_idx": q_idx,
        "total_questions": len(module_questions),
        "question": question,
        "response": response,
        "seconds_remaining": remaining,
        "nav_items": nav_items,
        "prev_url": url_for(
            "test_engine.question", attempt_id=attempt.id, module_num=module_num, q_idx=q_idx - 1
        ) if q_idx > 1 else None,
        "next_url": url_for(
            "test_engine.question", attempt_id=attempt.id, module_num=module_num, q_idx=q_idx + 1
        ) if q_idx < len(module_questions) else url_for(
            "test_engine.review", attempt_id=attempt.id, module_num=module_num
        ),
    }


def _build_nav_items(attempt_id: int, module_questions, module_num: int, current_q_idx: int | None = None):
    """Return a list of dicts describing each question's status for the navigator."""
    q_ids = [mq.question_id for mq in module_questions]
    responses_by_qid = {
        r.question_id: r
        for r in Response.query.filter(
            Response.attempt_id == attempt_id, Response.question_id.in_(q_ids)
        ).all()
    }
    items = []
    for idx, mq in enumerate(module_questions, start=1):
        r = responses_by_qid.get(mq.question_id)
        answered = bool(r and (r.choice_id is not None or r.free_response_text))
        items.append({
            "idx": idx,
            "question_id": mq.question_id,
            "answered": answered,
            "marked": bool(r and r.marked_for_review),
            "is_current": current_q_idx == idx,
            "url": url_for("test_engine.question", attempt_id=attempt_id, module_num=module_num, q_idx=idx),
        })
    return items


def _get_or_create_response(attempt_id: int, question_id: int) -> Response:
    r = Response.query.filter_by(attempt_id=attempt_id, question_id=question_id).one_or_none()
    if r is None:
        r = Response(attempt_id=attempt_id, question_id=question_id)
        db.session.add(r)
        db.session.commit()
    return r


# ---------------------------------------------------------------------------
# Check Your Work review page (§2.6) — real submission gate
# ---------------------------------------------------------------------------

@bp.route("/attempt/<int:attempt_id>/module/<int:module_num>/review", methods=["GET"])
@login_required
def review(attempt_id, module_num):
    attempt, am, module, module_questions = _load_module(attempt_id, module_num)
    nav_items = _build_nav_items(attempt.id, module_questions, module_num)
    return render_template(
        "test/review.html",
        attempt=attempt, attempt_module=am, module=module,
        module_num=module_num, total_modules=len(attempt.attempt_modules),
        nav_items=nav_items,
        seconds_remaining=module_seconds_remaining(am),
        submit_url=url_for("test_engine.submit_module", attempt_id=attempt.id, module_num=module_num),
    )


@bp.route("/attempt/<int:attempt_id>/module/<int:module_num>/submit", methods=["POST"])
@login_required
def submit_module(attempt_id, module_num):
    attempt, am, module, _ = _load_module(attempt_id, module_num)
    if am.submitted_at is None:
        am.submitted_at = datetime.utcnow()

    is_last = module_num >= len(attempt.attempt_modules)
    if is_last:
        attempt.status = AttemptStatus.COMPLETED
        attempt.completed_at = datetime.utcnow()
        db.session.commit()
        from app.services.scoring import compute_and_store
        compute_and_store(attempt)
        return redirect(url_for("test_engine.complete", attempt_id=attempt.id))

    # Otherwise, kick over to the between-module break screen (Phase 7 route).
    next_am = attempt.attempt_modules[module_num]  # 0-indexed, module_num is 1-indexed
    if next_am.break_started_at is None:
        next_am.break_started_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("test_engine.break_screen", attempt_id=attempt.id, module_num=module_num + 1))


@bp.route("/attempt/<int:attempt_id>/complete", methods=["GET"])
@login_required
def complete(attempt_id):
    """§2.8 confetti + Congratulations + inline post-test survey."""
    attempt = db.session.get(Attempt, attempt_id)
    if not attempt or attempt.student_id != current_user.student.id:
        abort(404)
    exam = db.session.get(Exam, attempt.exam_id)
    return render_template("test/complete.html", attempt=attempt, exam=exam)


@bp.route("/attempt/<int:attempt_id>/survey", methods=["POST"])
@login_required
def submit_survey(attempt_id):
    attempt = db.session.get(Attempt, attempt_id)
    if not attempt or attempt.student_id != current_user.student.id:
        abort(404)

    nps = request.form.get("nps", type=int)
    difficulty = request.form.get("difficulty", type=int)
    text = (request.form.get("text") or "").strip()

    if nps is not None and 0 <= nps <= 10:
        attempt.feedback_nps = nps
    if difficulty is not None and 0 <= difficulty <= 10:
        attempt.feedback_difficulty = difficulty
    if text:
        attempt.feedback_text = text
    db.session.commit()

    return redirect(url_for("results.show", attempt_id=attempt.id))


BREAK_DURATION_SECONDS = 10 * 60  # SAT's real between-section break


@bp.route("/attempt/<int:attempt_id>/module/<int:module_num>/break", methods=["GET"])
@login_required
def break_screen(attempt_id, module_num):
    """§2.7 dark-themed between-module break.

    Server-authoritative countdown from AttemptModule.break_started_at.
    Practice attempts (is_practice=True) may resume early; proctored ones must wait.
    """
    attempt, am, module, _ = _load_module(attempt_id, module_num)

    if am.break_started_at is None:
        am.break_started_at = datetime.utcnow()
        db.session.commit()

    elapsed = (datetime.utcnow() - am.break_started_at).total_seconds()
    seconds_remaining = max(0, int(BREAK_DURATION_SECONDS - elapsed))
    allow_early_resume = attempt.is_practice

    return render_template(
        "test/break.html",
        attempt=attempt, module=module, module_num=module_num,
        seconds_remaining=seconds_remaining,
        break_duration=BREAK_DURATION_SECONDS,
        allow_early_resume=allow_early_resume,
        resume_url=url_for("test_engine.resume_module", attempt_id=attempt.id, module_num=module_num),
    )


@bp.route("/attempt/<int:attempt_id>/module/<int:module_num>/resume", methods=["POST"])
@login_required
def resume_module(attempt_id, module_num):
    attempt, am, _, _ = _load_module(attempt_id, module_num)
    if am.started_at is None:
        am.started_at = datetime.utcnow()
    if am.break_ended_at is None:
        am.break_ended_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("test_engine.question", attempt_id=attempt.id, module_num=module_num, q_idx=1))


def _load_module(attempt_id: int, module_num: int):
    attempt = db.session.get(Attempt, attempt_id)
    if not attempt or attempt.student_id != current_user.student.id:
        abort(404)
    if module_num < 1 or module_num > len(attempt.attempt_modules):
        abort(404)
    am = attempt.attempt_modules[module_num - 1]
    module = db.session.get(ExamModule, am.module_id)
    return attempt, am, module, module.module_questions
