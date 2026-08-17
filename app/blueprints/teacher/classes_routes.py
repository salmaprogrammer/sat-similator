"""Teacher classes ("My Classes") + moderation queue."""
from __future__ import annotations
import secrets
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User, Student
from app.models.classroom import Classroom, ClassroomStudent
from app.models.moderation import QuestionReport
from app.models.bank import Question
from app.models.enums import ReportStatus

bp = Blueprint("teacher_classes", __name__, url_prefix="/teacher")


@bp.before_request
def _require_teacher():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if not current_user.is_teacher:
        return redirect(url_for("main.index"))


def _own_classroom(cid: int) -> Classroom:
    c = db.session.get(Classroom, cid)
    if not c or c.teacher_id != current_user.teacher.id:
        abort(404)
    return c


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@bp.route("/classes")
def classes():
    rows = Classroom.query.filter_by(teacher_id=current_user.teacher.id).order_by(Classroom.created_at.desc()).all()
    return render_template("teacher/classes.html", classrooms=rows)


@bp.route("/classes/new", methods=["POST"])
def class_new():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Give the class a name.", "error")
        return redirect(url_for("teacher_classes.classes"))
    c = Classroom(teacher_id=current_user.teacher.id, name=name, join_code=secrets.token_urlsafe(6))
    db.session.add(c)
    db.session.commit()
    return redirect(url_for("teacher_classes.class_detail", classroom_id=c.id))


@bp.route("/classes/<int:classroom_id>", methods=["GET"])
def class_detail(classroom_id):
    c = _own_classroom(classroom_id)
    return render_template("teacher/class_detail.html", classroom=c)


@bp.route("/classes/<int:classroom_id>/add-student", methods=["POST"])
def class_add_student(classroom_id):
    c = _own_classroom(classroom_id)
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash("Enter a student email.", "error")
        return redirect(url_for("teacher_classes.class_detail", classroom_id=c.id))
    user = User.query.filter_by(email=email).first()
    if not user or not user.is_student or not user.student:
        flash("No student with that email exists. Ask them to sign up first.", "error")
        return redirect(url_for("teacher_classes.class_detail", classroom_id=c.id))
    existing = ClassroomStudent.query.filter_by(classroom_id=c.id, student_id=user.student.id).first()
    if existing:
        flash("Student already in this class.", "info")
    else:
        db.session.add(ClassroomStudent(classroom_id=c.id, student_id=user.student.id))
        db.session.commit()
        flash(f"Added {email}.", "success")
    return redirect(url_for("teacher_classes.class_detail", classroom_id=c.id))


@bp.route("/class-members/<int:member_id>/remove", methods=["POST"])
def class_remove_member(member_id):
    m = db.session.get(ClassroomStudent, member_id)
    if not m or m.classroom.teacher_id != current_user.teacher.id:
        abort(404)
    cid = m.classroom_id
    db.session.delete(m)
    db.session.commit()
    return redirect(url_for("teacher_classes.class_detail", classroom_id=cid))


@bp.route("/classes/<int:classroom_id>/delete", methods=["POST"])
def class_delete(classroom_id):
    c = _own_classroom(classroom_id)
    db.session.delete(c)
    db.session.commit()
    flash("Class deleted.", "success")
    return redirect(url_for("teacher_classes.classes"))


# ---------------------------------------------------------------------------
# Moderation queue for student-reported questions
# ---------------------------------------------------------------------------

@bp.route("/moderation")
def moderation():
    """Reports for questions owned by this teacher (via their banks)."""
    from app.models.bank import QuestionBank
    teacher_bank_ids = [b.id for b in QuestionBank.query.filter_by(teacher_id=current_user.teacher.id).all()]
    reports = []
    if teacher_bank_ids:
        question_ids = [
            q.id for q in Question.query.filter(Question.bank_id.in_(teacher_bank_ids)).all()
        ]
        if question_ids:
            reports = (
                QuestionReport.query
                .filter(QuestionReport.question_id.in_(question_ids),
                        QuestionReport.status == ReportStatus.OPEN)
                .order_by(QuestionReport.created_at.desc())
                .all()
            )
    return render_template("teacher/moderation.html", reports=reports)


@bp.route("/moderation/<int:report_id>/<string:action>", methods=["POST"])
def moderation_action(report_id, action):
    rep = db.session.get(QuestionReport, report_id)
    if not rep:
        abort(404)
    # Verify teacher owns the question
    q = db.session.get(Question, rep.question_id)
    if not q or q.bank.teacher_id != current_user.teacher.id:
        abort(404)
    if action == "resolve":
        rep.status = ReportStatus.RESOLVED
    elif action == "dismiss":
        rep.status = ReportStatus.DISMISSED
    else:
        abort(400)
    rep.resolved_by = current_user.id
    rep.resolved_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("teacher_classes.moderation"))
