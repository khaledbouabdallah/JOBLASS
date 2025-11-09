"""
Database initialization and connection management with SQLModel
"""

from .engine import close_engine, get_session, init_db
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
    # Engine functions
    "get_session",
    "init_db",
    "close_engine",
    # Models
    "Job",
    "Application",
    "Score",
    "SearchCriteria",
    "SearchSession",
    "ScrapedJobData",
    "SalaryEstimate",
    "CompanyOverview",
    "ReviewSummary",
    "ReviewItem",
    "SkillsList",
    # Repositories
    "JobRepository",
    "ApplicationRepository",
    "ScoreRepository",
    "SearchSessionRepository",
]
