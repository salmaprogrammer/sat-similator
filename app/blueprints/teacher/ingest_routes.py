"""Teacher ingestion routes (§2.10). Attached to the existing teacher blueprint
in app/__init__.py.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
    current_app,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.ingest import QuestionImport, QuestionImportItem
from app.models.bank import QuestionBank, Question, Choice
from app.models.enums import (
    ImportStatus, SourceType, AnswerSource, ImportItemStatus,
    QuestionType, Difficulty, QuestionSource,
)
from app.services import storage
from app.services.ingest.pipeline import parse_import

bp = Blueprint("teacher_ingest", __name__, url_prefix="/teacher/imports")


@bp.before_request
def _require_teacher():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if not current_user.is_teacher:
        return redirect(url_for("main.index"))


ACCEPTED_EXTS = {".pdf": SourceType.PDF, ".docx": SourceType.DOCX, ".md": SourceType.MD}


def _own_import(import_id: int) -> QuestionImport:
    imp = db.session.get(QuestionImport, import_id)
    if not imp or imp.teacher_id != current_user.teacher.id:
        abort(404)
    return imp


# ---------------------------------------------------------------------------
# List imports
# ---------------------------------------------------------------------------

@bp.route("/")
def index():
    imports = (
        QuestionImport.query.filter_by(teacher_id=current_user.teacher.id)
        .order_by(QuestionImport.created_at.desc())
        .all()
    )
    banks = QuestionBank.query.filter_by(teacher_id=current_user.teacher.id).all()
    return render_template("teacher/imports.html", imports=imports, banks=banks)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    bank_id = request.form.get("bank_id", type=int)
    if not file or not file.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("teacher_ingest.index"))

    ext = Path(file.filename).suffix.lower()
    if ext not in ACCEPTED_EXTS:
        flash("Unsupported file type. Use .pdf, .docx, or .md.", "error")
        return redirect(url_for("teacher_ingest.index"))

    file_url = storage.save_upload(file.stream, file.filename)

    imp = QuestionImport(
        teacher_id=current_user.teacher.id,
        bank_id=bank_id,
        filename=file.filename,
        source_type=ACCEPTED_EXTS[ext],
        file_url=file_url,
        status=ImportStatus.UPLOADED,
        prompt_version=current_app.config.get("INGEST_PROMPT_VERSION", "v1"),
    )
    db.session.add(imp)
    db.session.commit()

    # Kick off parsing. In dev this runs inline; wrap with Celery in prod.
    try:
        parse_import(imp.id)
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Sync parse failed")

    return redirect(url_for("teacher_ingest.detail", import_id=imp.id))


# ---------------------------------------------------------------------------
# Review screen (matches reference image)
# ---------------------------------------------------------------------------

@bp.route("/<int:import_id>")
def detail(import_id):
    imp = _own_import(import_id)
    banks = QuestionBank.query.filter_by(teacher_id=current_user.teacher.id).all()
    return render_template("teacher/import_detail.html", imp=imp, banks=banks)


# ---------------------------------------------------------------------------
# Per-item edit / approve / reject
# ---------------------------------------------------------------------------

@bp.route("/items/<int:item_id>/edit", methods=["POST"])
def edit_item(item_id):
    item = db.session.get(QuestionImportItem, item_id)
    if not item or item.import_.teacher_id != current_user.teacher.id:
        abort(404)

    item.parsed_stem = request.form.get("stem", item.parsed_stem)
    item.suggested_topic = request.form.get("topic") or item.suggested_topic
    item.suggested_difficulty = request.form.get("difficulty") or item.suggested_difficulty

    # For MCQ, choices arrive as choice_A..choice_D + correct
    if item.parsed_choices is not None:
        labels = ["A", "B", "C", "D"]
        item.parsed_choices = [
            {"label": lbl, "text": request.form.get(f"choice_{lbl}", "").strip()}
            for lbl in labels
            if request.form.get(f"choice_{lbl}", "").strip()
        ]
        answer = request.form.get("correct", "").upper()
        if answer in labels:
            item.parsed_answer = answer
            item.answer_source = AnswerSource.EXTRACTED
    else:
        # Grid-in — comma-separated list of acceptable numeric answers
        raw = request.form.get("acceptable_answers", "").strip()
        if raw:
            answers = [s.strip() for s in raw.split(",") if s.strip()]
            item.parsed_answer = json.dumps(answers)
            item.answer_source = AnswerSource.EXTRACTED

    item.status = ImportItemStatus.EDITED
    db.session.commit()
    return redirect(url_for("teacher_ingest.detail", import_id=item.import_id))


@bp.route("/items/<int:item_id>/approve", methods=["POST"])
def approve_item(item_id):
    item = db.session.get(QuestionImportItem, item_id)
    if not item or item.import_.teacher_id != current_user.teacher.id:
        abort(404)
    _publish_item(item, request.form.get("bank_id", type=int))
    db.session.commit()
    return redirect(url_for("teacher_ingest.detail", import_id=item.import_id))


@bp.route("/items/<int:item_id>/reject", methods=["POST"])
def reject_item(item_id):
    item = db.session.get(QuestionImportItem, item_id)
    if not item or item.import_.teacher_id != current_user.teacher.id:
        abort(404)
    item.status = ImportItemStatus.REJECTED
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("teacher_ingest.detail", import_id=item.import_id))


@bp.route("/<int:import_id>/approve-all", methods=["POST"])
def approve_all(import_id):
    imp = _own_import(import_id)
    bank_id = request.form.get("bank_id", type=int) or imp.bank_id
    if not bank_id:
        flash("Choose a bank to publish into.", "error")
        return redirect(url_for("teacher_ingest.detail", import_id=imp.id))

    approvable = 0
    for item in imp.items:
        if item.status in {ImportItemStatus.PENDING_REVIEW, ImportItemStatus.EDITED}:
            if item.answer_source == AnswerSource.MISSING:
                # Skip items where no answer is set — per §2.10 they need explicit review
                continue
            try:
                _publish_item(item, bank_id)
                approvable += 1
            except Exception:  # noqa: BLE001
                current_app.logger.exception("approve_all: failed to publish item %s", item.id)
    db.session.commit()
    flash(f"Published {approvable} question{'s' if approvable != 1 else ''}.", "success")
    return redirect(url_for("teacher_ingest.detail", import_id=imp.id))


# ---------------------------------------------------------------------------
# Publish helper — writes into questions + choices
# ---------------------------------------------------------------------------

def _publish_item(item: QuestionImportItem, bank_id: int | None) -> None:
    bank_id = bank_id or item.import_.bank_id
    if not bank_id:
        raise ValueError("No target bank specified")

    is_grid_in = item.parsed_choices is None
    q = Question(
        bank_id=bank_id,
        stem=item.parsed_stem or "",
        type=QuestionType.GRID_IN if is_grid_in else QuestionType.MCQ,
        topic=item.suggested_topic,
        difficulty=_map_difficulty(item.suggested_difficulty),
        source=QuestionSource.IMPORTED,
        created_by=current_user.id,
    )
    if is_grid_in:
        # parsed_answer for grid-in is already a JSON-array-encoded string
        q.acceptable_answers = item.parsed_answer or json.dumps([])
    db.session.add(q)
    db.session.flush()

    if not is_grid_in:
        for c in item.parsed_choices or []:
            db.session.add(Choice(
                question_id=q.id,
                label=c["label"],
                text=c.get("text", ""),
                is_correct=(item.parsed_answer == c["label"]),
            ))

    item.status = ImportItemStatus.APPROVED
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.utcnow()
    item.resulting_question_id = q.id


def _map_difficulty(s: str | None) -> Difficulty:
    if not s:
        return Difficulty.MEDIUM
    s = s.lower()
    for d in Difficulty:
        if d.value == s:
            return d
    return Difficulty.MEDIUM
