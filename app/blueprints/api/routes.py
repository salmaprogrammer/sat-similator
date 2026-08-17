"""JSON/HTMX endpoints for the test engine."""
from __future__ import annotations
from datetime import datetime

from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.attempt import Attempt, Response
from app.models.bank import Choice, Question
from app.models.moderation import QuestionReport
from app.services.grading import grade_response

bp = Blueprint("api", __name__, url_prefix="/api")


def _own_attempt(attempt_id: int) -> Attempt:
    a = db.session.get(Attempt, attempt_id)
    if not a or a.student_id != current_user.student.id:
        abort(404)
    return a


def _response_for(attempt_id: int, question_id: int) -> Response:
    r = Response.query.filter_by(attempt_id=attempt_id, question_id=question_id).one_or_none()
    if r is None:
        r = Response(attempt_id=attempt_id, question_id=question_id)
        db.session.add(r)
        db.session.flush()
    return r


# ---------------------------------------------------------------------------
# Answer save (MCQ or grid-in)
# ---------------------------------------------------------------------------

@bp.route("/attempt/<int:attempt_id>/answer", methods=["POST"])
@login_required
def save_answer(attempt_id):
    attempt = _own_attempt(attempt_id)
    question_id = request.form.get("question_id", type=int)
    if not question_id:
        abort(400)
    q = db.session.get(Question, question_id)
    if q is None:
        abort(404)

    r = _response_for(attempt.id, question_id)

    choice_id = request.form.get("choice_id", type=int)
    free_text = request.form.get("free_response_text", type=str)
    time_delta = request.form.get("time_delta_seconds", type=int) or 0

    if choice_id is not None:
        # Validate choice belongs to the question
        choice = db.session.get(Choice, choice_id)
        if not choice or choice.question_id != question_id:
            abort(400)
        r.choice_id = choice_id
        r.free_response_text = None
    if free_text is not None:
        r.free_response_text = free_text.strip() or None
        r.choice_id = None

    if time_delta:
        r.time_spent_seconds = (r.time_spent_seconds or 0) + max(0, time_delta)

    r.is_correct = grade_response(r, q)
    db.session.commit()
    return jsonify({"ok": True, "response_id": r.id, "graded": r.is_correct})


# ---------------------------------------------------------------------------
# Mark for review
# ---------------------------------------------------------------------------

@bp.route("/attempt/<int:attempt_id>/mark", methods=["POST"])
@login_required
def toggle_mark(attempt_id):
    attempt = _own_attempt(attempt_id)
    question_id = request.form.get("question_id", type=int)
    if not question_id:
        abort(400)
    r = _response_for(attempt.id, question_id)
    r.marked_for_review = not r.marked_for_review
    db.session.commit()
    return jsonify({"ok": True, "marked": r.marked_for_review})


# ---------------------------------------------------------------------------
# Strikethrough state (per-question)
# ---------------------------------------------------------------------------

@bp.route("/attempt/<int:attempt_id>/strikethrough", methods=["POST"])
@login_required
def save_strikethrough(attempt_id):
    attempt = _own_attempt(attempt_id)
    question_id = request.form.get("question_id", type=int)
    if not question_id:
        abort(400)
    payload = request.get_json(silent=True) or {}
    enabled = bool(request.form.get("enabled") or payload.get("enabled"))
    struck_raw = request.form.get("struck") or payload.get("struck") or []
    if isinstance(struck_raw, str):
        struck = [s for s in struck_raw.split(",") if s]
    else:
        struck = list(struck_raw)

    r = _response_for(attempt.id, question_id)
    r.strikethrough_state = {"enabled": enabled, "struck": struck}
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Timer sync — server-authoritative
# ---------------------------------------------------------------------------

@bp.route("/attempt/<int:attempt_id>/timer", methods=["GET"])
@login_required
def timer(attempt_id):
    attempt = _own_attempt(attempt_id)
    module_num = request.args.get("module_num", type=int, default=1)
    if module_num < 1 or module_num > len(attempt.attempt_modules):
        abort(404)
    am = attempt.attempt_modules[module_num - 1]
    from app.services.timer import module_seconds_remaining
    remaining = module_seconds_remaining(am)
    return jsonify({
        "server_time_utc": datetime.utcnow().isoformat() + "Z",
        "started_at_utc": am.started_at.isoformat() + "Z" if am.started_at else None,
        "effective_time_limit_seconds": am.effective_time_limit_seconds,
        "seconds_remaining": remaining,
    })


# ---------------------------------------------------------------------------
# Report a bad question
# ---------------------------------------------------------------------------

@bp.route("/attempt/<int:attempt_id>/report", methods=["POST"])
@login_required
def report_question(attempt_id):
    attempt = _own_attempt(attempt_id)
    question_id = request.form.get("question_id", type=int)
    reason = (request.form.get("reason") or "").strip()
    if not question_id:
        abort(400)
    rep = QuestionReport(
        student_id=current_user.student.id,
        question_id=question_id,
        attempt_id=attempt.id,
        reason=reason or None,
    )
    db.session.add(rep)
    db.session.commit()
    return jsonify({"ok": True, "report_id": rep.id})
