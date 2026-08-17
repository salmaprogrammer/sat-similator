from app.models.enums import Accommodation


def test_multiplier_standard():
    assert Accommodation.STANDARD.multiplier == 1.0


def test_multiplier_time_and_a_half():
    assert Accommodation.TIME_AND_A_HALF.multiplier == 1.5


def test_multiplier_double():
    assert Accommodation.DOUBLE_TIME.multiplier == 2.0


def test_start_attempt_applies_multiplier(app):
    from app.extensions import db
    from app.models.user import User, Student, Teacher
    from app.models.bank import QuestionBank, Question
    from app.models.exam import Exam, ExamModule
    from app.models.enums import Role, Section, ModuleVariant

    with app.app_context():
        u_t = User(email="t@x.com", role=Role.TEACHER); u_t.set_password("password")
        t = Teacher(user=u_t)
        u_s = User(email="s@x.com", role=Role.STUDENT); u_s.set_password("password")
        s = Student(user=u_s, onboarding_completed=True, accommodation=Accommodation.DOUBLE_TIME)
        db.session.add_all([u_t, t, u_s, s]); db.session.flush()

        bank = QuestionBank(teacher_id=t.id, name="B"); db.session.add(bank); db.session.flush()
        q = Question(bank_id=bank.id, stem="?"); db.session.add(q); db.session.flush()

        exam = Exam(name="X", is_published=True); db.session.add(exam); db.session.flush()
        m = ExamModule(exam_id=exam.id, section=Section.MATH, module_number=1,
                       time_limit_seconds=1000, difficulty_variant=ModuleVariant.FIXED)
        db.session.add(m); db.session.commit()

        client = app.test_client()
        client.post("/auth/login", data={"email": "s@x.com", "password": "password"})
        r = client.post(f"/tests/{exam.id}/start")
        assert r.status_code == 302

        from app.models.attempt import AttemptModule
        am = AttemptModule.query.order_by(AttemptModule.id.desc()).first()
        assert am.effective_time_limit_seconds == 2000  # 1000 * 2.0
