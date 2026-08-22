import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


def _default_sqlite_url() -> str:
    return f"sqlite:///{INSTANCE_DIR / 'satsimilator.db'}"


def _normalize_db_url(url: str) -> str:
    """Railway (and Heroku) provide DATABASE_URL as postgres://…
    SQLAlchemy 2.x only accepts postgresql://…
    """
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.getenv("DATABASE_URL", _default_sqlite_url()))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = str(INSTANCE_DIR / "uploads")
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB uploads

    # Railway sets REDIS_URL when the Redis plugin is added — prefer it over the split vars.
    _redis = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", _redis)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", _redis)

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    INGEST_PROMPT_VERSION = os.getenv("INGEST_PROMPT_VERSION", "v1")

    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    S3_BUCKET = os.getenv("S3_BUCKET", "")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
    S3_REGION = os.getenv("S3_REGION", "us-east-1")

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

    WTF_CSRF_TIME_LIMIT = None


class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    DEBUG = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


CONFIG_MAP = {
    "development": DevConfig,
    "production": ProdConfig,
    "testing": TestConfig,
}


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return CONFIG_MAP.get(env, DevConfig)
