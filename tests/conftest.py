"""Pytest fixtures.

Uses an in-memory SQLite DB (config.TestConfig) so tests don't touch the dev DB.
"""
import pytest

from app import create_app
from app.extensions import db
from config import TestConfig


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def teacher(app):
    from app.models.user import User, Teacher
    from app.models.enums import Role
    with app.app_context():
        u = User(email="t@x.com", role=Role.TEACHER)
        u.set_password("password")
        t = Teacher(user=u)
        db.session.add_all([u, t])
        db.session.commit()
        return t.id


@pytest.fixture
def student(app):
    from app.models.user import User, Student
    from app.models.enums import Role
    with app.app_context():
        u = User(email="s@x.com", role=Role.STUDENT)
        u.set_password("password")
        s = Student(user=u, onboarding_completed=True)
        db.session.add_all([u, s])
        db.session.commit()
        return s.id
