"""
SQLModel engine and session management
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from joblass.config import REPO_ROOT
from joblass.utils.logger import setup_logger

logger = setup_logger(__name__)

# Database file path
DB_DIR = Path(REPO_ROOT) / "data"
DB_PATH = DB_DIR / "joblass.db"


def get_db_path() -> Path:
    """Get database file path, create directory if needed"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return DB_PATH


# Create SQLModel engine
# connect_args for SQLite: check_same_thread=False allows multiple threads
# echo=False: disable SQL query logging (set True for debugging)
engine = create_engine(
    f"sqlite:///{get_db_path()}",
    connect_args={"check_same_thread": False},
    echo=False,
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions

    Usage:
        with get_session() as session:
            job = session.get(Job, job_id)
            session.add(new_job)
            session.commit()

    Auto-commits on success, rolls back on exception

    Note: expire_on_commit=False allows accessing attributes after session closes
    """
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}", exc_info=True)
        raise
    finally:
        session.close()


def init_db(reset: bool = False) -> None:
    """
    Initialize database with SQLModel schema

    Args:
        reset: If True, drop all tables and recreate (WARNING: deletes all data)
    """
    db_path = get_db_path()

    if reset and db_path.exists():
        logger.warning("Resetting database - all data will be lost!")
        db_path.unlink()
        # Recreate engine with new file
        global engine
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

    logger.info(f"Initializing database at {db_path}")

    try:
        # Import all models to register them with SQLModel

        # Create all tables from SQLModel metadata
        SQLModel.metadata.create_all(engine)

        logger.info("Database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


def close_engine() -> None:
    """Close database engine (cleanup on shutdown)"""
    engine.dispose()
    logger.debug("Database engine closed")
