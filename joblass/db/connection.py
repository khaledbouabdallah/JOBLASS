"""
SQLite database connection and initialization
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from joblass.config import REPO_ROOT
from joblass.utils.logger import setup_logger

logger = setup_logger(__name__)

# Database file path
DB_DIR = Path(REPO_ROOT) / "data"
DB_PATH = DB_DIR / "joblass.db"

# SQL schema definitions
SCHEMA_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    url TEXT NOT NULL,
    job_hash TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    description TEXT,
    tech_stack TEXT,
    verified_skills TEXT,
    required_skills TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_median INTEGER,
    salary_currency TEXT DEFAULT 'EUR',
    posted_date TIMESTAMP,
    scraped_date TIMESTAMP NOT NULL,
    job_type TEXT,
    remote_option TEXT,
    is_easy_apply BOOLEAN,
    job_external_id TEXT,
    company_size TEXT,
    company_industry TEXT,
    company_sector TEXT,
    company_founded TEXT,
    company_type TEXT,
    company_revenue TEXT,
    reviews_data TEXT,
    session_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES search_sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(job_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_date ON jobs(scraped_date);
CREATE INDEX IF NOT EXISTS idx_jobs_external_id ON jobs(job_external_id);
CREATE INDEX IF NOT EXISTS idx_jobs_session_id ON jobs(session_id);
"""

SCHEMA_APPLICATIONS = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    application_method TEXT NOT NULL,
    applied_date TIMESTAMP,
    last_updated TIMESTAMP NOT NULL,
    cover_letter_path TEXT,
    notes TEXT,
    interview_date TIMESTAMP,
    interview_notes TEXT,
    rejection_date TIMESTAMP,
    rejection_reason TEXT,
    offer_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
"""

SCHEMA_SCORES = """
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL UNIQUE,
    tech_match REAL DEFAULT 0.0,
    learning_opportunity REAL DEFAULT 0.0,
    company_quality REAL DEFAULT 0.0,
    practical_factors REAL DEFAULT 0.0,
    total_score REAL DEFAULT 0.0,
    penalties TEXT,
    bonuses TEXT,
    scored_date TIMESTAMP NOT NULL,
    llm_analysis TEXT,
    red_flags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scores_job_id ON scores(job_id);
CREATE INDEX IF NOT EXISTS idx_scores_total_score ON scores(total_score DESC);
"""

SCHEMA_SEARCH_SESSIONS = """
CREATE TABLE IF NOT EXISTS search_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_criteria TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'glassdoor',
    status TEXT NOT NULL DEFAULT 'in_progress',
    jobs_found INTEGER DEFAULT 0,
    jobs_scraped INTEGER DEFAULT 0,
    jobs_saved INTEGER DEFAULT 0,
    jobs_skipped INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_search_sessions_status ON search_sessions(status);
CREATE INDEX IF NOT EXISTS idx_search_sessions_created_at ON search_sessions(created_at DESC);
"""


def get_db_path() -> Path:
    """Get database file path, create directory if needed"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def get_db_connection() -> sqlite3.Connection:
    """
    Get SQLite database connection

    Returns:
        sqlite3.Connection: Database connection with row factory
    """
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row  # Enable column access by name

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


@contextmanager
def get_db_cursor():
    """
    Context manager for database cursor

    Usage:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM jobs")
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()


def init_db(reset: bool = False) -> None:
    """
    Initialize database with schema

    Args:
        reset: If True, drop all tables and recreate (WARNING: deletes all data)
    """
    db_path = get_db_path()

    if reset and db_path.exists():
        logger.warning("Resetting database - all data will be lost!")
        os.remove(db_path)

    logger.info(f"Initializing database at {db_path}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Create tables (order matters - search_sessions must be created before jobs due to FK)
        cursor.executescript(SCHEMA_SEARCH_SESSIONS)
        cursor.executescript(SCHEMA_JOBS)
        cursor.executescript(SCHEMA_APPLICATIONS)
        cursor.executescript(SCHEMA_SCORES)

        conn.commit()
        logger.info("Database initialized successfully")

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()


def close_db(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Close database connection

    Args:
        conn: Connection to close. If None, does nothing.
    """
    if conn:
        conn.close()
        logger.debug("Database connection closed")


def vacuum_db() -> None:
    """Optimize database (reclaim space, rebuild indexes)"""
    logger.info("Optimizing database...")
    conn = get_db_connection()
    try:
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        logger.info("Database optimized successfully")
    finally:
        conn.close()


def migrate_db() -> None:
    """
    Migrate existing database to add new columns without losing data

    Safe to run multiple times - only adds columns if they don't exist
    """
    logger.info("Running database migration...")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get existing columns
        cursor.execute("PRAGMA table_info(jobs)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Define new columns to add
        new_columns = {
            "verified_skills": "TEXT",
            "required_skills": "TEXT",
            "salary_median": "INTEGER",
            "company_sector": "TEXT",
            "company_founded": "TEXT",
            "company_type": "TEXT",
            "company_revenue": "TEXT",
            "reviews_data": "TEXT",
            "is_easy_apply": "BOOLEAN",
            "job_external_id": "TEXT",
            "job_hash": "TEXT",
        }

        # Add missing columns
        columns_added = 0
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                alter_sql = f"ALTER TABLE jobs ADD COLUMN {column_name} {column_type}"
                cursor.execute(alter_sql)
                logger.info(f"Added column: {column_name} ({column_type})")
                columns_added += 1

        # Create index on job_external_id if it was just added
        if "job_external_id" not in existing_columns and columns_added > 0:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_external_id ON jobs(job_external_id)"
            )
            logger.info("Created index on job_external_id")

        # Create index on job_hash if it was just added
        if "job_hash" not in existing_columns and columns_added > 0:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(job_hash)")
            logger.info("Created index on job_hash")

        # Populate job_hash for existing records
        if "job_hash" not in existing_columns:
            logger.info("Populating job_hash for existing records...")
            cursor.execute(
                "SELECT id, title, company, location, source, job_external_id FROM jobs WHERE job_hash IS NULL"
            )
            rows = cursor.fetchall()

            from joblass.db.models import Job

            for row in rows:
                # Create temporary Job object to generate hash
                temp_job = Job(
                    id=row[0],
                    title=row[1],
                    company=row[2],
                    location=row[3],
                    url="http://temp.com",  # Dummy URL (not used for hash)
                    source=row[4],
                    job_external_id=row[5],
                )
                job_hash = temp_job.generate_hash()
                cursor.execute(
                    "UPDATE jobs SET job_hash = ? WHERE id = ?", (job_hash, row[0])
                )

            logger.info(f"Populated job_hash for {len(rows)} existing records")

        # Remove UNIQUE constraint from URL (if needed - SQLite doesn't support DROP CONSTRAINT)
        # We'll keep URL indexed but not unique, relying on job_hash instead
        # Note: This requires recreating the table in SQLite, which is complex
        # For now, we'll just warn if there's an issue
        logger.info(
            "Note: URL column still has UNIQUE constraint - new schema uses job_hash for uniqueness"
        )

        conn.commit()

        if columns_added > 0:
            logger.info(f"Migration completed: {columns_added} columns added")
        else:
            logger.info("Migration completed: schema already up to date")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        cursor.close()
        conn.close()
