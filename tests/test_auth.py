def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"SatSimilator" in r.data


def test_signup_creates_student(client, app):
    r = client.post("/auth/signup", data={
        "email": "new@x.com", "password": "password12", "confirm": "password12", "role": "student",
    })
    assert r.status_code == 302
    from app.models.user import User
    from app.models.enums import Role
    with app.app_context():
        u = User.query.filter_by(email="new@x.com").first()
        assert u is not None
        assert u.role == Role.STUDENT
        assert u.student is not None


def test_login_redirects_student_to_onboarding_if_incomplete(client, app):
    from app.models.user import User, Student
    from app.models.enums import Role
    from app.extensions import db
    with app.app_context():
        u = User(email="fresh@x.com", role=Role.STUDENT); u.set_password("password")
        db.session.add_all([u, Student(user=u)])
        db.session.commit()
    r = client.post("/auth/login", data={"email": "fresh@x.com", "password": "password"})
    assert r.status_code == 302
    assert "/onboarding/step/1" in r.headers["Location"]
