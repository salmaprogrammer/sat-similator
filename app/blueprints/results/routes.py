"""Results / report page (§2.9)."""
from __future__ import annotations
from flask import Blueprint, render_template, abort, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models.attempt import Attempt, AttemptScore
from app.services.scoring import compute_and_store, question_grid, topics_costing_most
from app.services.paygate import is_pro, gated_slice

bp = Blueprint("results", __name__, url_prefix="/attempt")


@bp.route("/<int:attempt_id>/results")
@login_required
def show(attempt_id):
    attempt, score = _load_scored(attempt_id)
    ctx = _build_context(attempt, score, printable=False)
    return render_template("results/show.html", **ctx)


@bp.route("/<int:attempt_id>/results.pdf")
@login_required
def printable(attempt_id):
    """Print-friendly view of the results page. Use browser Print → Save as PDF.

    In prod, wrap this template in WeasyPrint on the server side; for local dev
    we save on the native-deps install by relying on the browser.
    """
    attempt, score = _load_scored(attempt_id)
    ctx = _build_context(attempt, score, printable=True)
    return render_template("results/printable.html", **ctx)


def _load_scored(attempt_id):
    attempt = db.session.get(Attempt, attempt_id)
    if not attempt or attempt.student_id != current_user.student.id:
        abort(404)
    score = attempt.score or compute_and_store(attempt)
    return attempt, score


def _build_context(attempt, score, *, printable: bool):
    grid = question_grid(attempt)
    total = len(grid)
    correct = sum(1 for g in grid if g["correct"])
    wrong = sum(1 for g in grid if g["wrong"])
    unattempted = sum(1 for g in grid if g["unattempted"])
    accuracy = (correct / (correct + wrong)) if (correct + wrong) else 0

    topics_ranked = topics_costing_most(score)
    topics_visible, topics_hidden = gated_slice(topics_ranked, rows_visible=2)

    per_topic_bars = sorted(
        (
            {
                "topic": t,
                "accuracy": (data.get("correct", 0) / data["total"]) if data.get("total") else 0,
                "total": data.get("total", 0),
            }
            for t, data in (score.per_topic or {}).items()
        ),
        key=lambda r: r["accuracy"],
    )
    bars_visible, bars_hidden = gated_slice(per_topic_bars, rows_visible=2)

    return {
        "attempt": attempt,
        "score": score,
        "grid": grid,
        "stats": {"total": total, "correct": correct, "wrong": wrong, "unattempted": unattempted, "accuracy": accuracy},
        "topics_visible": topics_visible,
        "topics_hidden": topics_hidden,
        "bars_visible": bars_visible,
        "bars_hidden": bars_hidden,
        "is_pro": is_pro(),
        "per_difficulty_time": score.per_difficulty_time or {},
        "printable": printable,
    }
