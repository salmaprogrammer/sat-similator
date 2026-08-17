from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse

from app.extensions import db
from app.models.user import User, Student, Teacher
from app.models.enums import Role
from app.blueprints.auth.forms import LoginForm, SignupForm, ForgotForm

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _post_login_redirect(user: User) -> str:
    next_url = request.args.get("next")
    if next_url and urlparse(next_url).netloc == "":
        return next_url
    if user.is_student:
        if user.student and not user.student.onboarding_completed:
            return url_for("onboarding.step", n=1)
        return url_for("student.dashboard")
    if user.is_teacher:
        return url_for("teacher.home")
    return url_for("main.index")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_post_login_redirect(current_user))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(_post_login_redirect(user))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(_post_login_redirect(current_user))
    form = SignupForm()
    if form.validate_on_submit():
        role = Role(form.role.data)
        user = User(email=form.email.data.lower(), role=role)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        if role == Role.STUDENT:
            db.session.add(Student(user_id=user.id))
        else:
            db.session.add(Teacher(user_id=user.id))
        db.session.commit()
        login_user(user)
        flash("Welcome to SatSimilator.", "success")
        return redirect(_post_login_redirect(user))
    return render_template("auth/signup.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    form = ForgotForm()
    if form.validate_on_submit():
        # v1: no actual email sending yet; always show success to avoid enumeration
        flash("If an account exists for that email, a reset link is on its way.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html", form=form)
