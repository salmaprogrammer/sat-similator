from __future__ import annotations
import json

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import Teacher
from app.models.bank import QuestionBank, Question, Choice
from app.models.exam import Exam, ExamModule, ExamModuleQuestion
from app.models.enums import QuestionType, Difficulty, Section, ModuleVariant
from app.blueprints.teacher.forms import BankForm, QuestionForm, ExamForm, ModuleForm

bp = Blueprint("teacher", __name__, url_prefix="/teacher")


@bp.before_request
def _require_teacher():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if not current_user.is_teacher:
        return redirect(url_for("main.index"))


def _teacher() -> Teacher:
    return current_user.teacher


def _own_bank(bank_id: int) -> QuestionBank:
    bank = db.session.get(QuestionBank, bank_id)
    if not bank or bank.teacher_id != _teacher().id:
        abort(404)
    return bank


def _own_question(question_id: int) -> Question:
    q = db.session.get(Question, question_id)
    if not q:
        abort(404)
    if q.bank.teacher_id != _teacher().id:
        abort(404)
    return q


def _own_exam(exam_id: int) -> Exam:
    exam = db.session.get(Exam, exam_id)
    if not exam or exam.teacher_id != _teacher().id:
        abort(404)
    return exam


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

@bp.route("/")
def home():
    return render_template("teacher/home.html")


# ---------------------------------------------------------------------------
# Banks
# ---------------------------------------------------------------------------

@bp.route("/banks")
def banks():
    my_banks = QuestionBank.query.filter_by(teacher_id=_teacher().id).order_by(QuestionBank.created_at.desc()).all()
    return render_template("teacher/banks.html", banks=my_banks)


@bp.route("/banks/new", methods=["GET", "POST"])
def bank_new():
    form = BankForm()
    if form.validate_on_submit():
        bank = QuestionBank(teacher_id=_teacher().id, name=form.name.data, is_public=form.is_public.data)
        db.session.add(bank)
        db.session.commit()
        flash("Bank created.", "success")
        return redirect(url_for("teacher.bank_detail", bank_id=bank.id))
    return render_template("teacher/bank_form.html", form=form, bank=None)


@bp.route("/banks/<int:bank_id>", methods=["GET", "POST"])
def bank_detail(bank_id):
    bank = _own_bank(bank_id)
    return render_template("teacher/bank_detail.html", bank=bank)


@bp.route("/banks/<int:bank_id>/edit", methods=["GET", "POST"])
def bank_edit(bank_id):
    bank = _own_bank(bank_id)
    form = BankForm(obj=bank)
    if form.validate_on_submit():
        bank.name = form.name.data
        bank.is_public = form.is_public.data
        db.session.commit()
        flash("Bank updated.", "success")
        return redirect(url_for("teacher.bank_detail", bank_id=bank.id))
    return render_template("teacher/bank_form.html", form=form, bank=bank)


@bp.route("/banks/<int:bank_id>/delete", methods=["POST"])
def bank_delete(bank_id):
    bank = _own_bank(bank_id)
    db.session.delete(bank)
    db.session.commit()
    flash("Bank deleted.", "success")
    return redirect(url_for("teacher.banks"))


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------

@bp.route("/banks/<int:bank_id>/questions/new", methods=["GET", "POST"])
def question_new(bank_id):
    bank = _own_bank(bank_id)
    form = QuestionForm()
    if form.validate_on_submit():
        q = _persist_question(form, bank_id=bank.id, question=None)
        flash("Question added.", "success")
        return redirect(url_for("teacher.bank_detail", bank_id=bank.id))
    return render_template("teacher/question_form.html", form=form, bank=bank, question=None)


@bp.route("/questions/<int:question_id>/edit", methods=["GET", "POST"])
def question_edit(question_id):
    q = _own_question(question_id)
    form = QuestionForm(obj=q)
    if request.method == "GET":
        _load_choices_into_form(form, q)
    if form.validate_on_submit():
        _persist_question(form, bank_id=q.bank_id, question=q)
        flash("Question saved.", "success")
        return redirect(url_for("teacher.bank_detail", bank_id=q.bank_id))
    return render_template("teacher/question_form.html", form=form, bank=q.bank, question=q)


@bp.route("/questions/<int:question_id>/delete", methods=["POST"])
def question_delete(question_id):
    q = _own_question(question_id)
    bank_id = q.bank_id
    db.session.delete(q)
    db.session.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("teacher.bank_detail", bank_id=bank_id))


def _load_choices_into_form(form: QuestionForm, q: Question) -> None:
    for c in q.choices:
        getattr(form, f"choice_{c.label.lower()}").data = c.text
        if c.is_correct:
            form.correct.data = c.label
    if q.type == QuestionType.GRID_IN and q.acceptable_answers:
        try:
            values = json.loads(q.acceptable_answers)
            if isinstance(values, list):
                form.acceptable_answers.data = ", ".join(values)
        except json.JSONDecodeError:
            form.acceptable_answers.data = q.acceptable_answers


def _persist_question(form: QuestionForm, *, bank_id: int, question: Question | None) -> Question:
    from app.services import storage

    q = question or Question(bank_id=bank_id, created_by=current_user.id)
    q.stem = form.stem.data
    q.type = QuestionType(form.type.data)
    q.topic = form.topic.data or None
    q.difficulty = Difficulty(form.difficulty.data)
    q.passage_text = (form.passage_text.data or "").strip() or None

    # Image handling: remove-current takes precedence; else if a new file was
    # uploaded, save it and replace the URL.
    if form.remove_image.data:
        q.image_url = None
    uploaded = form.image_file.data
    if uploaded and getattr(uploaded, "filename", ""):
        q.image_url = storage.save_upload(uploaded.stream, uploaded.filename, prefix="questions/")

    if q.id is None:
        db.session.add(q)
        db.session.flush()

    # Wipe and rebuild choices for MCQ; store acceptable_answers for grid-in
    for c in list(q.choices):
        db.session.delete(c)
    q.acceptable_answers = None

    if q.type == QuestionType.MCQ:
        labels = ["A", "B", "C", "D"]
        texts = [form.choice_a.data, form.choice_b.data, form.choice_c.data, form.choice_d.data]
        for label, text in zip(labels, texts):
            if text:
                db.session.add(Choice(
                    question_id=q.id, label=label, text=text,
                    is_correct=(form.correct.data == label),
                ))
    else:
        raw = form.acceptable_answers.data or ""
        answers = [s.strip() for s in raw.split(",") if s.strip()]
        q.acceptable_answers = json.dumps(answers) if answers else None

    db.session.commit()
    return q


# ---------------------------------------------------------------------------
# Exams
# ---------------------------------------------------------------------------

@bp.route("/exams")
def exams():
    my_exams = Exam.query.filter_by(teacher_id=_teacher().id).order_by(Exam.created_at.desc()).all()
    return render_template("teacher/exams.html", exams=my_exams)


@bp.route("/exams/new", methods=["GET", "POST"])
def exam_new():
    form = ExamForm()
    if form.validate_on_submit():
        exam = Exam(
            name=form.name.data, teacher_id=_teacher().id,
            is_predicted_test=form.is_predicted_test.data,
        )
        db.session.add(exam)
        db.session.commit()
        flash("Exam created. Add modules next.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))
    return render_template("teacher/exam_form.html", form=form, exam=None)


@bp.route("/exams/<int:exam_id>", methods=["GET"])
def exam_detail(exam_id):
    exam = _own_exam(exam_id)
    banks = QuestionBank.query.filter_by(teacher_id=_teacher().id).all()
    return render_template("teacher/exam_detail.html", exam=exam, banks=banks)


@bp.route("/exams/<int:exam_id>/edit", methods=["GET", "POST"])
def exam_edit(exam_id):
    exam = _own_exam(exam_id)
    form = ExamForm(obj=exam)
    if form.validate_on_submit():
        exam.name = form.name.data
        exam.is_predicted_test = form.is_predicted_test.data
        db.session.commit()
        flash("Exam updated.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))
    return render_template("teacher/exam_form.html", form=form, exam=exam)


@bp.route("/exams/<int:exam_id>/publish", methods=["POST"])
def exam_publish(exam_id):
    exam = _own_exam(exam_id)
    exam.is_published = not exam.is_published
    db.session.commit()
    flash(f"Exam {'published' if exam.is_published else 'unpublished'}.", "success")
    return redirect(url_for("teacher.exam_detail", exam_id=exam.id))


@bp.route("/exams/<int:exam_id>/delete", methods=["POST"])
def exam_delete(exam_id):
    exam = _own_exam(exam_id)
    db.session.delete(exam)
    db.session.commit()
    flash("Exam deleted.", "success")
    return redirect(url_for("teacher.exams"))


# ---------------------------------------------------------------------------
# Modules within an exam
# ---------------------------------------------------------------------------

@bp.route("/exams/<int:exam_id>/modules/new", methods=["GET", "POST"])
def module_new(exam_id):
    exam = _own_exam(exam_id)
    form = ModuleForm()
    if form.validate_on_submit():
        module = ExamModule(
            exam_id=exam.id,
            section=Section(form.section.data),
            module_number=int(form.module_number.data),
            time_limit_seconds=form.time_limit_seconds.data,
            calculator_allowed=form.calculator_allowed.data,
            difficulty_variant=ModuleVariant(form.difficulty_variant.data),
        )
        db.session.add(module)
        db.session.commit()
        flash("Module added.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))
    return render_template("teacher/module_form.html", form=form, exam=exam, module=None)


@bp.route("/modules/<int:module_id>/delete", methods=["POST"])
def module_delete(module_id):
    module = db.session.get(ExamModule, module_id)
    if not module or module.exam.teacher_id != _teacher().id:
        abort(404)
    exam_id = module.exam_id
    db.session.delete(module)
    db.session.commit()
    flash("Module deleted.", "success")
    return redirect(url_for("teacher.exam_detail", exam_id=exam_id))


@bp.route("/modules/<int:module_id>/add-question", methods=["POST"])
def module_add_question(module_id):
    module = db.session.get(ExamModule, module_id)
    if not module or module.exam.teacher_id != _teacher().id:
        abort(404)
    q_id = request.form.get("question_id", type=int)
    if not q_id:
        abort(400)
    q = _own_question(q_id)
    max_order = db.session.query(db.func.max(ExamModuleQuestion.order_index)).filter_by(module_id=module.id).scalar() or -1
    db.session.add(ExamModuleQuestion(module_id=module.id, question_id=q.id, order_index=max_order + 1))
    db.session.commit()
    return redirect(url_for("teacher.exam_detail", exam_id=module.exam_id))


@bp.route("/module-questions/<int:mq_id>/delete", methods=["POST"])
def module_question_delete(mq_id):
    mq = db.session.get(ExamModuleQuestion, mq_id)
    if not mq or mq.module.exam.teacher_id != _teacher().id:
        abort(404)
    exam_id = mq.module.exam_id
    db.session.delete(mq)
    db.session.commit()
    return redirect(url_for("teacher.exam_detail", exam_id=exam_id))
