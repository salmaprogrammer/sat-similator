from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField, BooleanField, SubmitField,
    FieldList, FormField, HiddenField,
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length

from app.models.enums import QuestionType, Difficulty, Section, ModuleVariant


class BankForm(FlaskForm):
    name = StringField("Bank name", validators=[DataRequired(), Length(max=255)])
    is_public = BooleanField("Publicly visible to other teachers")
    submit = SubmitField("Save bank")


class ChoiceEntryForm(FlaskForm):
    class Meta:
        csrf = False
    label = HiddenField()
    text = StringField("Choice text")


class QuestionForm(FlaskForm):
    stem = TextAreaField("Question stem", validators=[DataRequired()])
    type = SelectField(
        "Type",
        choices=[(QuestionType.MCQ.value, "Multiple choice"), (QuestionType.GRID_IN.value, "Grid-in (free response)")],
        default=QuestionType.MCQ.value,
    )
    topic = StringField("Topic", validators=[Optional(), Length(max=128)])
    difficulty = SelectField(
        "Difficulty",
        choices=[(d.value, d.value.title()) for d in Difficulty],
        default=Difficulty.MEDIUM.value,
    )
    # MCQ fields
    choice_a = StringField("A")
    choice_b = StringField("B")
    choice_c = StringField("C")
    choice_d = StringField("D")
    correct = SelectField(
        "Correct choice",
        choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        validators=[Optional()],
    )
    # Grid-in fields (comma-separated list of acceptable numeric answers)
    acceptable_answers = StringField(
        "Accepted answers (comma-separated, numerically equivalent)",
        validators=[Optional()],
    )
    submit = SubmitField("Save question")


class ExamForm(FlaskForm):
    name = StringField("Exam name", validators=[DataRequired(), Length(max=255)])
    is_predicted_test = BooleanField("Predicted-paper test")
    submit = SubmitField("Save exam")


class ModuleForm(FlaskForm):
    section = SelectField(
        "Section",
        choices=[(Section.RW.value, "Reading & Writing"), (Section.MATH.value, "Math")],
        validators=[DataRequired()],
    )
    module_number = SelectField(
        "Module",
        choices=[("1", "1"), ("2", "2")],
        default="1",
    )
    time_limit_seconds = IntegerField(
        "Time limit (seconds)",
        default=32 * 60,
        validators=[DataRequired(), NumberRange(min=60, max=180 * 60)],
    )
    calculator_allowed = BooleanField("Calculator allowed")
    difficulty_variant = SelectField(
        "Difficulty variant",
        choices=[(v.value, v.value.title()) for v in ModuleVariant],
        default=ModuleVariant.FIXED.value,
    )
    submit = SubmitField("Save module")
