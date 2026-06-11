import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

# Database connection details from environment variables (no defaults for credentials)
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "calimara_db")

if not DB_USER or not DB_PASSWORD:
    raise RuntimeError(
        "Database credentials not configured. "
        "Set DB_USER and DB_PASSWORD in your .env file."
    )

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("postgresql"):
    engine_options.update({
        "pool_size": _env_int("DB_POOL_SIZE", 5),
        "max_overflow": _env_int("DB_MAX_OVERFLOW", 5),
        "pool_timeout": _env_int("DB_POOL_TIMEOUT", 10),
        "pool_recycle": _env_int("DB_POOL_RECYCLE", 1800),
    })

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
