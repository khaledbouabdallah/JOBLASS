"""
Database initialization and connection management
"""

from .connection import close_db, get_db_connection, init_db, migrate_db
from .models import (
    Application,
    CompanyOverview,
    Job,
    ReviewItem,
    ReviewSummary,
    SalaryEstimate,
    Score,
    ScrapedJobData,
    SearchCriteria,
    SearchSession,
    SkillsList,
)
from .repository import (
    ApplicationRepository,
    JobRepository,
    ScoreRepository,
    SearchSessionRepository,
)

__all__ = [
    "get_db_connection",
    "init_db",
    "migrate_db",
    "close_db",
    "Job",
    "Application",
    "Score",
    "SearchCriteria",
    "SearchSession",
    "JobRepository",
    "ApplicationRepository",
    "ScoreRepository",
    "SearchSessionRepository",
    "ScrapedJobData",
    "SalaryEstimate",
    "CompanyOverview",
    "ReviewSummary",
    "ReviewItem",
    "SkillsList",
]
