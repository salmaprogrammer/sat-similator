"""Central enum definitions used across models and forms."""
import enum


class Role(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class Accommodation(str, enum.Enum):
    STANDARD = "standard"
    TIME_AND_A_HALF = "time_and_a_half"
    DOUBLE_TIME = "double_time"

    @property
    def multiplier(self) -> float:
        return {
            Accommodation.STANDARD: 1.0,
            Accommodation.TIME_AND_A_HALF: 1.5,
            Accommodation.DOUBLE_TIME: 2.0,
        }[self]


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    GRID_IN = "grid_in"


class Difficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionSource(str, enum.Enum):
    AUTHORED = "authored"
    IMPORTED = "imported"


class Section(str, enum.Enum):
    RW = "rw"
    MATH = "math"


class ModuleVariant(str, enum.Enum):
    EASY = "easy"
    HARD = "hard"
    FIXED = "fixed"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ImportStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class SourceType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    MD = "md"


class AnswerSource(str, enum.Enum):
    EXTRACTED = "extracted"
    AI_GENERATED = "ai_generated"
    MISSING = "missing"


class ImportItemStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
