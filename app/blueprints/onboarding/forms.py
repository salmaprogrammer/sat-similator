from flask_wtf import FlaskForm
from wtforms import (
    SelectField, DateField, IntegerField, BooleanField, SubmitField, SelectMultipleField,
    widgets,
)
from wtforms.validators import DataRequired, NumberRange, Optional


EXAM_TYPES = [("sat", "Digital SAT"), ("psat", "PSAT/NMSQT")]

DAYS = [("mon", "Mon"), ("tue", "Tue"), ("wed", "Wed"),
        ("thu", "Thu"), ("fri", "Fri"), ("sat", "Sat"), ("sun", "Sun")]


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class Step2ExamType(FlaskForm):
    exam_type = SelectField("Which exam?", choices=EXAM_TYPES, validators=[DataRequired()])
    submit = SubmitField("Continue")


class Step3TestDate(FlaskForm):
    test_date = DateField("Your test date", validators=[Optional()])
    submit = SubmitField("Continue")


class Step4CurrentScore(FlaskForm):
    current_score = IntegerField(
        "Your most recent score (leave blank if none)",
        validators=[Optional(), NumberRange(min=400, max=1600)],
    )
    submit = SubmitField("Continue")


class Step5GoalScore(FlaskForm):
    goal_score = IntegerField(
        "Your goal score",
        validators=[DataRequired(), NumberRange(min=400, max=1600)],
    )
    submit = SubmitField("Continue")


class Step7EmailOptIn(FlaskForm):
    email_opt_in = BooleanField("Send me study reminders and product updates", default=True)
    submit = SubmitField("Continue")


class Step8StudyStart(FlaskForm):
    study_start = DateField("When do you want to start?", validators=[Optional()])
    submit = SubmitField("Continue")


class Step9StudyDays(FlaskForm):
    days = MultiCheckboxField("Which days will you study?", choices=DAYS)
    submit = SubmitField("Continue")
