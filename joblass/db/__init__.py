"""
Database initialization and connection management
"""

from .connection import close_db, get_db_connection, init_db, migrate_db
from .models import Application, Job, Score
from .repository import ApplicationRepository, JobRepository, ScoreRepository
from .validators import (
    CompanyOverview,
    ReviewSummary,
    SalaryEstimate,
    ScrapedJobData,
    SkillsList,
)

__all__ = [
    "get_db_connection",
    "init_db",
    "migrate_db",
    "close_db",
    "Job",
    "Application",
    "Score",
    "JobRepository",
    "ApplicationRepository",
    "ScoreRepository",
    "ScrapedJobData",
    "SalaryEstimate",
    "CompanyOverview",
    "ReviewSummary",
    "SkillsList",
]
