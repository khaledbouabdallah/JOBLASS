"""
Database initialization and connection management with SQLModel
"""

from .engine import close_engine, get_session, init_db
from .models import (
    Application,
    Company,
    CompanyEvaluations,
    CompanyOverview,
    Job,
    ReviewItem,
    ReviewSummary,
    SalaryEstimate,
    Score,
    ScrapedCompanyFromJobPosting,
    ScrapedCompanyFromProfile,
    ScrapedJobData,
    SearchCriteria,
    SearchSession,
    SkillsList,
)
from .repository import (
    ApplicationRepository,
    CompanyRepository,
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
    "Company",
    "CompanyEvaluations",
    "ScrapedCompanyFromJobPosting",
    "ScrapedCompanyFromProfile",
    # Repositories
    "JobRepository",
    "ApplicationRepository",
    "ScoreRepository",
    "SearchSessionRepository",
    "CompanyRepository",
]
