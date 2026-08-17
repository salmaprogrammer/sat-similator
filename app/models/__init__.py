"""Import every model here so Flask-Migrate can discover them."""
from app.models.user import User, Student, Teacher
from app.models.bank import QuestionBank, Question, Choice
from app.models.exam import Exam, ExamModule, ExamModuleQuestion
from app.models.attempt import Attempt, AttemptModule, Response, AttemptScore
from app.models.ingest import QuestionImport, QuestionImportItem
from app.models.moderation import QuestionReport
from app.models.classroom import Classroom, ClassroomStudent

__all__ = [
    "User", "Student", "Teacher",
    "QuestionBank", "Question", "Choice",
    "Exam", "ExamModule", "ExamModuleQuestion",
    "Attempt", "AttemptModule", "Response", "AttemptScore",
    "QuestionImport", "QuestionImportItem",
    "QuestionReport",
    "Classroom", "ClassroomStudent",
]
