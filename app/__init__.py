import os
from pathlib import Path

from flask import Flask, render_template

from config import get_config
from app.extensions import db, migrate, login_manager, csrf


def create_app(config_class=None):
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        instance_relative_config=False,
    )
    app.config.from_object(config_class or get_config())

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User  # noqa: F401  (registers model)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    _register_blueprints(app)
    _register_cli(app)
    _register_error_handlers(app)

    return app


def _register_blueprints(app: Flask) -> None:
    from app.blueprints.main.routes import bp as main_bp
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.onboarding.routes import bp as onboarding_bp
    from app.blueprints.student.routes import bp as student_bp
    from app.blueprints.teacher.routes import bp as teacher_bp
    from app.blueprints.test_engine.routes import bp as test_engine_bp
    from app.blueprints.api.routes import bp as api_bp
    from app.blueprints.teacher.ingest_routes import bp as teacher_ingest_bp
    from app.blueprints.results.routes import bp as results_bp
    from app.blueprints.integrations.routes import bp as integrations_bp
    from app.blueprints.billing.routes import bp as billing_bp
    from app.blueprints.teacher.classes_routes import bp as teacher_classes_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(test_engine_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(teacher_ingest_bp)
    app.register_blueprint(results_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(teacher_classes_bp)


def _register_cli(app: Flask) -> None:
    from app.cli import register_cli
    register_cli(app)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500
