"""
Data models for job search database
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    """Represents a job posting"""

    # Required fields
    title: str
    company: str
    location: str
    url: str
    source: str  # e.g., 'glassdoor', 'linkedin'

    # Optional fields
    id: Optional[int] = None
    description: Optional[str] = None
    tech_stack: Optional[str] = None  # JSON string of all tech/skills
    verified_skills: Optional[str] = None  # JSON string of verified skills
    required_skills: Optional[str] = None  # JSON string of required skills
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_median: Optional[int] = None
    salary_currency: Optional[str] = "EUR"
    posted_date: Optional[datetime] = None
    scraped_date: datetime = field(default_factory=datetime.now)

    # Additional metadata
    job_type: Optional[str] = None  # 'internship', 'full-time', etc.
    remote_option: Optional[str] = None  # 'remote', 'hybrid', 'onsite'

    # Company information
    company_size: Optional[str] = None
    company_industry: Optional[str] = None
    company_sector: Optional[str] = None
    company_founded: Optional[str] = None
    company_type: Optional[str] = None
    company_revenue: Optional[str] = None

    # Reviews data (JSON string with pros/cons)
    reviews_data: Optional[str] = None

    # Raw data for future processing
    raw_html: Optional[str] = None

    def __post_init__(self):
        """Validate required fields"""
        if not self.url:
            raise ValueError("Job URL is required")
        if not self.title:
            raise ValueError("Job title is required")


@dataclass
class Application:
    """Tracks application status for a job"""

    job_id: int
    status: str  # 'pending', 'applied', 'rejected', 'interview', 'offer'

    id: Optional[int] = None
    applied_date: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

    # Application details
    cover_letter_path: Optional[str] = None
    notes: Optional[str] = None

    # Interview tracking
    interview_date: Optional[datetime] = None
    interview_notes: Optional[str] = None

    # Outcome
    rejection_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    offer_date: Optional[datetime] = None

    VALID_STATUSES = {
        "pending",
        "applied",
        "rejected",
        "interview",
        "offer",
        "declined",
        "accepted",
    }

    def __post_init__(self):
        """Validate status"""
        if self.status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {self.status}. Must be one of {self.VALID_STATUSES}"
            )


@dataclass
class Score:
    """Job scoring and ranking"""

    job_id: int

    # Score components (0-100 each)
    tech_match: float = 0.0
    learning_opportunity: float = 0.0
    company_quality: float = 0.0
    practical_factors: float = 0.0

    # Total weighted score
    total_score: float = 0.0

    # Penalties and bonuses
    penalties: Optional[str] = None  # JSON string of penalty reasons
    bonuses: Optional[str] = None  # JSON string of bonus reasons

    id: Optional[int] = None
    scored_date: datetime = field(default_factory=datetime.now)

    # LLM analysis results
    llm_analysis: Optional[str] = None  # JSON string of LLM insights
    red_flags: Optional[str] = None  # JSON list of identified red flags

    def calculate_total(
        self,
        tech_weight: float = 0.30,
        learning_weight: float = 0.25,
        company_weight: float = 0.20,
        practical_weight: float = 0.25,
    ) -> float:
        """
        Calculate weighted total score

        Args:
            tech_weight: Weight for tech match (default 30%)
            learning_weight: Weight for learning opportunity (default 25%)
            company_weight: Weight for company quality (default 20%)
            practical_weight: Weight for practical factors (default 25%)

        Returns:
            Total weighted score (0-100)
        """
        total = (
            self.tech_match * tech_weight
            + self.learning_opportunity * learning_weight
            + self.company_quality * company_weight
            + self.practical_factors * practical_weight
        )
        self.total_score = round(total, 2)
        return self.total_score

    def __post_init__(self):
        """Calculate total score if component scores are set"""
        if any(
            [
                self.tech_match,
                self.learning_opportunity,
                self.company_quality,
                self.practical_factors,
            ]
        ):
            self.calculate_total()
