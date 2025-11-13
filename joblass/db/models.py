"""
Data models for job search database using SQLModel
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field as SQLField
from sqlmodel import Relationship, SQLModel

# ============================================================================
# Nested/Helper Models (formerly in validators.py)
# ============================================================================


class CompanyTab(Enum):
    """Available tabs on Glassdoor company profile"""

    OVERVIEW = "overview"
    REVIEWS = "reviews"
    JOBS = "jobs"
    SALARIES = "salaries"
    INTERVIEWS = "interviews"
    BENEFITS = "benefits"
    PHOTOS = "photos"
    DIVERSITY = "diversity"


class ReviewItem(BaseModel):
    """Individual review pro/con item"""

    text: str
    count: int = Field(ge=0, description="Number of mentions")


class ReviewSummary(BaseModel):
    """Review pros and cons summary"""

    pros: List[ReviewItem] = Field(default_factory=list)
    cons: List[ReviewItem] = Field(default_factory=list)


class CompanyEvaluations(BaseModel):
    """Company evaluations and ratings from Glassdoor"""

    global_rating: Optional[float] = Field(
        None, ge=0.0, le=5.0, description="Overall rating (0-5)"
    )
    reviews_count: Optional[int] = Field(
        None, ge=0, description="Total number of reviews"
    )
    recommend_to_friend: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="% who recommend to friend"
    )

    # Detailed ratings (0-5 scale)
    culture_and_values: Optional[float] = Field(None, ge=0.0, le=5.0)
    diversity_equity_inclusion: Optional[float] = Field(None, ge=0.0, le=5.0)
    work_life_balance: Optional[float] = Field(None, ge=0.0, le=5.0)
    senior_management: Optional[float] = Field(None, ge=0.0, le=5.0)
    compensation_and_benefits: Optional[float] = Field(None, ge=0.0, le=5.0)
    career_opportunities: Optional[float] = Field(None, ge=0.0, le=5.0)


class CompanyOverview(BaseModel):
    """Company overview information"""

    size: Optional[str] = None
    founded: Optional[str] = None
    type: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    revenue: Optional[str] = None
    headquarters: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None


class SalaryEstimate(BaseModel):
    """Salary estimation information"""

    lower_bound: Optional[int] = Field(None, ge=0, description="Minimum salary")
    upper_bound: Optional[int] = Field(None, ge=0, description="Maximum salary")
    median: Optional[int] = Field(None, ge=0, description="Median salary")
    currency: Optional[str] = Field(None, pattern=r"^[€$£¥]?[A-Z]{0,3}$")

    @field_validator("upper_bound")
    @classmethod
    def upper_must_exceed_lower(cls, v: Optional[int], info) -> Optional[int]:
        """Validate upper bound is greater than lower bound"""
        if v is not None and info.data.get("lower_bound") is not None:
            if v < info.data["lower_bound"]:
                raise ValueError("upper_bound must be >= lower_bound")
        return v


class SkillsList(BaseModel):
    """List of skills with validation"""

    skills: List[str] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def remove_empty_skills(cls, v: List[str]) -> List[str]:
        """Remove empty or whitespace-only skills"""
        return [skill.strip() for skill in v if skill and skill.strip()]


class SearchCriteria(BaseModel):
    """Search criteria for job search (basic + advanced filters)"""

    # --- Basic search fields (required) ---
    job_title: str = Field(..., description="Job title/keyword")
    location: str = Field(..., description="Job location")
    preferred_location: Optional[str] = Field(
        None, description="Specific location from suggestions"
    )

    # --- Toggles ---
    is_easy_apply: bool = Field(False, description="Easy Apply only")
    is_remote: bool = Field(False, description="Remote jobs only")

    # --- Salary range ---
    salary_min: Optional[int] = Field(None, ge=0, description="Minimum salary")
    salary_max: Optional[int] = Field(None, ge=0, description="Maximum salary")

    # --- Advanced filters (dynamic options) ---
    company_rating: Optional[str] = Field(
        None, description="Minimum company rating (e.g., '+3')"
    )
    date_posted: Optional[str] = Field(None, description="Date posted filter")
    job_type: Optional[str] = Field(None, description="Job type (e.g., 'Stage')")
    city: Optional[str] = Field(None, description="City filter")
    industry: Optional[str] = Field(None, description="Industry")
    professional_domain: Optional[str] = Field(None, description="Professional domain")
    experience_level: Optional[str] = Field(None, description="Experience level")
    company: Optional[str] = Field(None, description="Specific company")
    company_size: Optional[str] = Field(None, description="Company size")

    def to_filters_dict(self) -> dict:
        """
        Convert to filters dict for ExtraFilters.apply_filters()

        Returns:
            dict: Only advanced filters with non-None values (excludes basic search fields)
        """
        filters: dict[str, bool | tuple[int, int] | str] = {}

        # Toggles (only include if True)
        if self.is_easy_apply:
            filters["is_easy_apply"] = True
        if self.is_remote:
            filters["is_remote"] = True

        # Salary range - only include if BOTH min and max are provided
        if self.salary_min is not None and self.salary_max is not None:
            filters["salary_range"] = (self.salary_min, self.salary_max)

        # Advanced filters (only include non-None values)
        advanced_fields = [
            "company_rating",
            "date_posted",
            "job_type",
            "city",
            "industry",
            "professional_domain",
            "experience_level",
            "company",
            "company_size",
        ]

        for field in advanced_fields:
            value = getattr(self, field)
            if value is not None:
                filters[field] = value

        return filters


# ============================================================================
# Core Database Models
# ============================================================================


class Job(SQLModel, table=True):  # type: ignore[call-arg]
    """Job posting with SQLModel and JSON columns"""

    __tablename__ = "jobs"

    # Primary key
    id: Optional[int] = SQLField(default=None, primary_key=True)

    # Required fields with indexes
    title: str = SQLField(index=True, min_length=1)
    company: str = SQLField(
        index=True, min_length=1
    )  # Kept for display/search (denormalized)
    location: str = SQLField(min_length=1)
    url: str = SQLField(unique=True, index=True)
    source: str = SQLField(index=True)
    scraped_date: datetime = SQLField(default_factory=datetime.now, index=True)

    # Job metadata
    job_age: int = SQLField(default=0, ge=0)
    posted_date: Optional[datetime] = None
    job_type: Optional[str] = None
    remote_option: Optional[str] = None
    is_easy_apply: Optional[bool] = None
    job_external_id: Optional[str] = SQLField(default=None, index=True)

    # Optional text fields
    description: Optional[str] = None

    # JSON columns for structured data
    tech_stack: Optional[List[str]] = SQLField(default=None, sa_column=Column(JSON))
    salary_estimate: Optional[Dict[str, Any]] = SQLField(
        default=None, sa_column=Column(JSON)
    )

    # Foreign keys
    company_id: Optional[int] = SQLField(
        default=None, foreign_key="companies.id", index=True
    )
    session_id: Optional[int] = SQLField(
        default=None, foreign_key="search_sessions.id", index=True
    )

    # Timestamps
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)

    # Relationships
    company_rel: Optional["Company"] = Relationship(back_populates="jobs")
    session: Optional["SearchSession"] = Relationship(back_populates="jobs")
    scores: Optional["Score"] = Relationship(
        back_populates="job", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    applications: List["Application"] = Relationship(
        back_populates="job", sa_relationship_kwargs={"cascade": "all, delete"}
    )

    @field_validator("title", "company", "location")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace"""
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Basic URL validation"""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    # Helper properties for legacy compatibility
    @property
    def salary_min(self) -> Optional[int]:
        if self.salary_estimate:
            return self.salary_estimate.get("lower_bound") or self.salary_estimate.get(
                "min"
            )
        return None

    @property
    def salary_max(self) -> Optional[int]:
        if self.salary_estimate:
            return self.salary_estimate.get("upper_bound") or self.salary_estimate.get(
                "max"
            )
        return None

    @property
    def salary_median(self) -> Optional[int]:
        if self.salary_estimate:
            return self.salary_estimate.get("median")
        return None

    @property
    def salary_currency(self) -> str:
        if self.salary_estimate:
            return self.salary_estimate.get("currency", "EUR")
        return "EUR"

    def to_filters_dict(self) -> dict:
        """
        Convert to filters dict for ExtraFilters.apply_filters()

        Returns:
            dict: Only advanced filters with non-None values
        """
        filters: dict[str, bool | tuple[int, int] | str] = {}

        # Toggles
        if self.is_easy_apply:
            filters["is_easy_apply"] = True
        if self.is_remote:
            filters["is_remote"] = True

        # Salary range - only include if BOTH min and max are provided
        if self.salary_min is not None and self.salary_max is not None:
            filters["salary_range"] = (self.salary_min, self.salary_max)

        # Advanced filters
        advanced_fields = [
            "company_rating",
            "date_posted",
            "job_type",
            "city",
            "industry",
            "professional_domain",
            "experience_level",
            "company",
            "company_size",
        ]

        for field in advanced_fields:
            value = getattr(self, field)
            if value is not None:
                filters[field] = value

        return filters


class SearchSession(SQLModel, table=True):  # type: ignore[call-arg]
    """Tracks job search sessions with results and status"""

    __tablename__ = "search_sessions"

    # Primary key
    id: Optional[int] = SQLField(default=None, primary_key=True)

    # Search criteria (stored as JSON dict)
    search_criteria: Dict[str, Any] = SQLField(sa_column=Column(JSON))

    # Source and status
    source: str = SQLField(default="glassdoor", index=True)
    status: str = SQLField(default="in_progress", index=True)

    # Search results
    jobs_found: int = SQLField(default=0, ge=0)
    jobs_scraped: int = SQLField(default=0, ge=0)
    jobs_saved: int = SQLField(default=0, ge=0)
    jobs_skipped: int = SQLField(default=0, ge=0)

    # Error tracking
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime = SQLField(default_factory=datetime.now, index=True)
    updated_at: datetime = SQLField(default_factory=datetime.now)

    # Relationships
    jobs: List[Job] = Relationship(back_populates="session")

    def __init__(self, search_criteria: SearchCriteria | Dict[str, Any], **kwargs):
        """
        Initialize SearchSession with SearchCriteria or dict

        Args:
            search_criteria: SearchCriteria model or dict
            **kwargs: Other fields
        """
        # Convert SearchCriteria to dict if needed
        if isinstance(search_criteria, SearchCriteria):
            search_criteria = search_criteria.model_dump(exclude_none=True)

        super().__init__(search_criteria=search_criteria, **kwargs)

    def get_search_criteria(self) -> SearchCriteria:
        """
        Get search criteria as SearchCriteria model

        Returns:
            SearchCriteria instance
        """
        return SearchCriteria(**self.search_criteria)

    def update_search_criteria(self, criteria: SearchCriteria) -> None:
        """
        Update search criteria from SearchCriteria model

        Args:
            criteria: SearchCriteria instance
        """
        self.search_criteria = criteria.model_dump(exclude_none=True)
        self.updated_at = datetime.now()

    def mark_completed(
        self, jobs_scraped: int, jobs_saved: int, jobs_skipped: int
    ) -> None:
        """Mark session as completed with final stats"""
        self.status = "completed"
        self.jobs_scraped = jobs_scraped
        self.jobs_saved = jobs_saved
        self.jobs_skipped = jobs_skipped
        self.updated_at = datetime.now()

    def mark_failed(self, error_message: str) -> None:
        """Mark session as failed with error message"""
        self.status = "failed"
        self.error_message = error_message
        self.updated_at = datetime.now()


# TODO: its just a prototype for now, needs more work
class Application(SQLModel, table=True):  # type: ignore[call-arg]
    """Tracks application status for a job"""

    __tablename__ = "applications"

    # Primary key
    id: Optional[int] = SQLField(default=None, primary_key=True)

    # Foreign key to jobs
    job_id: int = SQLField(foreign_key="jobs.id", index=True)

    # Application status
    status: str = SQLField(description="Application status")
    application_method: str

    # Dates
    applied_date: Optional[datetime] = None
    last_updated: datetime = SQLField(default_factory=datetime.now)

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

    # Timestamps
    created_at: datetime = SQLField(default_factory=datetime.now)

    # Relationships
    job: Optional[Job] = Relationship(back_populates="applications")

    # Keep for backward compatibility - use ClassVar so SQLModel doesn't treat it as a field
    VALID_STATUSES: ClassVar[set] = {
        "pending",
        "applied",
        "rejected",
        "interview",
        "offer",
        "declined",
        "accepted",
    }

    model_config = {"validate_assignment": True}

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in cls.VALID_STATUSES:
            raise ValueError(f"Status must be one of {cls.VALID_STATUSES}, got '{v}'")
        return v


# TODO: its just a prototype for now, needs more work
class Score(SQLModel, table=True):  # type: ignore[call-arg]
    """Job scoring and ranking with JSON columns"""

    __tablename__ = "scores"

    # Primary key
    id: Optional[int] = SQLField(default=None, primary_key=True)

    # Foreign key to jobs (unique - one score per job)
    job_id: int = SQLField(foreign_key="jobs.id", unique=True, index=True)

    # Score components (0-100 each)
    tech_match: float = SQLField(default=0.0, ge=0.0, le=100.0)
    learning_opportunity: float = SQLField(default=0.0, ge=0.0, le=100.0)
    company_quality: float = SQLField(default=0.0, ge=0.0, le=100.0)
    practical_factors: float = SQLField(default=0.0, ge=0.0, le=100.0)

    # Total weighted score (indexed for sorting)
    total_score: float = SQLField(default=0.0, ge=0.0, le=100.0, index=True)

    # JSON columns for lists/dicts
    penalties: Optional[List[str]] = SQLField(default=None, sa_column=Column(JSON))
    bonuses: Optional[List[str]] = SQLField(default=None, sa_column=Column(JSON))
    llm_analysis: Optional[Dict[str, Any]] = SQLField(
        default=None, sa_column=Column(JSON)
    )
    red_flags: Optional[List[str]] = SQLField(default=None, sa_column=Column(JSON))

    # Timestamps
    scored_date: datetime = SQLField(default_factory=datetime.now)
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)

    # Relationships
    job: Optional[Job] = Relationship(back_populates="scores")

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-calculate total score if component scores are provided
        if any(
            [
                data.get("tech_match", 0) > 0,
                data.get("learning_opportunity", 0) > 0,
                data.get("company_quality", 0) > 0,
                data.get("practical_factors", 0) > 0,
            ]
        ):
            total = round(
                self.tech_match * 0.30
                + self.learning_opportunity * 0.25
                + self.company_quality * 0.20
                + self.practical_factors * 0.25,
                2,
            )
            object.__setattr__(self, "total_score", total)

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
        # Use object.__setattr__ to avoid validation
        object.__setattr__(self, "total_score", round(total, 2))
        return self.total_score


class Company(SQLModel, table=True):  # type: ignore[call-arg]
    """Company profile with basic info and JSON columns"""

    __tablename__ = "companies"

    # Primary key
    id: Optional[int] = SQLField(default=None, primary_key=True)

    # Company name (unique)
    name: str = SQLField(unique=True, index=True, min_length=1)

    # Source and page source tracking
    source: str = SQLField(index=True, default="glassdoor")
    page_source: str = SQLField(
        index=True,
        description="Where data was scraped from: 'job_posting', 'company_profile', or 'merged'",
    )

    # Profile URL
    profile_url: Optional[str] = SQLField(default=None, unique=True, index=True)

    # JSON columns for structured data
    overview: Optional[Dict[str, str]] = SQLField(default=None, sa_column=Column(JSON))
    reviews_summary: Optional[Dict[str, List[Dict[str, Any]]]] = SQLField(
        default=None, sa_column=Column(JSON), description="Pros/cons from reviews"
    )
    evaluations: Optional[Dict[str, Any]] = SQLField(
        default=None, sa_column=Column(JSON), description="Numeric ratings and metrics"
    )
    salary_estimates: Optional[List[Dict[str, Any]]] = SQLField(
        default=None, sa_column=Column(JSON)
    )

    # Timestamps
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now)

    # Relationships
    jobs: List["Job"] = Relationship(back_populates="company_rel")

    @field_validator("name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace"""
        return v.strip()


# ============================================================================
# Validation model for raw scraping data
# ============================================================================


class ScrapedJobData(BaseModel):
    """
    Complete scraped job data with validation

    This model validates all data scraped from job posting pages
    before it's saved to the database.
    """

    # Required fields
    job_title: str = Field(min_length=1, description="Job title")
    company: str = Field(min_length=1, description="Company name")
    location: str = Field(min_length=1, description="Job location")
    job_age: int = Field(default=0, ge=0, description="Job age in days since posted")

    # URL field - Glassdoor page URL (skip saving easy apply jobs without external URL)
    url: Optional[str] = Field(None, description="Job posting URL (Glassdoor page)")

    # Job metadata from listing page
    is_easy_apply: bool = Field(default=False, description="Is Easy Apply job")
    job_external_id: Optional[str] = Field(
        None, description="External job ID (data-jobid)"
    )
    posted_date: Optional[datetime] = Field(None, description="Calculated posted date")

    # Optional text fields
    description: Optional[str] = None

    # Structured data
    verified_skills: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    salary_estimate: Optional[SalaryEstimate] = None

    # Metadata
    source: str = "glassdoor"
    scraped_date: datetime = Field(default_factory=datetime.now)

    @field_validator("job_title", "company", "location")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace"""
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Basic URL validation"""
        if v is None:
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("verified_skills", "required_skills")
    @classmethod
    def remove_empty_skills(cls, v: List[str]) -> List[str]:
        """Remove empty or whitespace-only skills and duplicates"""
        cleaned = [skill.strip() for skill in v if skill and skill.strip()]
        # Remove duplicates while preserving order
        return list(dict.fromkeys(cleaned))

    def get_all_skills(self) -> List[str]:
        """Get combined unique skills from verified and required"""
        return list(dict.fromkeys(self.verified_skills + self.required_skills))

    def to_job_model(
        self, session_id: Optional[int] = None, company_id: Optional[int] = None
    ) -> Job:
        """
        Convert to Job model for database insertion

        Args:
            session_id: Optional search session ID to associate with
            company_id: Optional company ID to link to

        Returns:
            Job model instance ready for database insertion
        """
        return Job(
            title=self.job_title,
            company=self.company,
            location=self.location,
            url=self.url,
            description=self.description,
            source=self.source,
            scraped_date=self.scraped_date,
            posted_date=self.posted_date,
            job_age=self.job_age,
            is_easy_apply=self.is_easy_apply,
            job_external_id=self.job_external_id,
            # JSON columns with proper structure - use model_dump()
            tech_stack=self.get_all_skills() if self.get_all_skills() else None,
            salary_estimate=(
                self.salary_estimate.model_dump(exclude_none=True)
                if self.salary_estimate
                else None
            ),
            company_id=company_id,
            session_id=session_id,
        )

    def to_db_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for database insertion (DEPRECATED)

        DEPRECATED: Use to_job_model() instead for SQLModel compatibility

        Returns:
            Dictionary with JSON-serialized complex fields
        """
        return {
            "title": self.job_title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "description": self.description,
            "source": self.source,
            "scraped_date": self.scraped_date,
            "posted_date": self.posted_date,
            "job_age": self.job_age,
            "is_easy_apply": self.is_easy_apply,
            "job_external_id": self.job_external_id,
            # JSON-serialized fields - combine verified + required into tech_stack
            "tech_stack": (
                json.dumps(self.get_all_skills()) if self.get_all_skills() else None
            ),
            "salary_min": (
                self.salary_estimate.lower_bound if self.salary_estimate else None
            ),
            "salary_max": (
                self.salary_estimate.upper_bound if self.salary_estimate else None
            ),
            "salary_median": (
                self.salary_estimate.median if self.salary_estimate else None
            ),
            "salary_currency": (
                self.salary_estimate.currency if self.salary_estimate else "EUR"
            ),
        }

    @classmethod
    def from_glassdoor_extract(cls, data: Dict[str, Any]) -> "ScrapedJobData":
        """
        Create from glassdoor extract_job_details() output

        Args:
            data: Dictionary from extract_job_details() - job data only

        Returns:
            Validated ScrapedJobData instance
        """
        # Handle salary estimate
        salary_estimate = None
        if data.get("salary_estimate"):
            salary_data = data["salary_estimate"]
            salary_estimate = SalaryEstimate(
                lower_bound=salary_data.get("lower_bound"),
                upper_bound=salary_data.get("upper_bound"),
                median=salary_data.get("median"),
                currency=salary_data.get("currency"),
            )

        # URL is the Glassdoor job page URL
        return cls(
            job_title=data.get("job_title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            job_age=data.get("job_age", 0),  # Default to 0 if not provided
            url=data.get("url"),  # Glassdoor page URL
            is_easy_apply=data.get("is_easy_apply", False),
            job_external_id=data.get("job_external_id"),
            posted_date=data.get("posted_date"),
            description=data.get("description"),
            verified_skills=data.get("verified_skills", []),
            required_skills=data.get("required_skills", []),
            salary_estimate=salary_estimate,
        )


class ScrapedCompanyFromJobPosting(BaseModel):
    """
    Company data scraped from job posting pages (partial data)

    This is extracted alongside job details from job posting pages.
    Provides basic company overview and reviews summary.
    """

    # Required fields
    company_name: str = Field(min_length=1, description="Company name")
    profile_url: Optional[str] = Field(
        None, description="Glassdoor company profile URL"
    )

    # Metadata
    source: str = Field(default="glassdoor")
    scraped_date: datetime = Field(default_factory=datetime.now)

    # Partial company data from job posting
    overview: Optional[CompanyOverview] = Field(
        None,
        description="Company overview (size, founded, type, industry, sector, revenue)",
    )
    reviews_summary: Optional[ReviewSummary] = Field(
        None, description="Review pros/cons summary from job posting"
    )
    salary_estimates: List[SalaryEstimate] = Field(
        default_factory=list, description="Salary estimates shown on job posting"
    )

    @field_validator("company_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace"""
        return v.strip()

    @field_validator("profile_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Basic URL validation"""
        if v is None:
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    def to_company_model(self) -> Company:
        """
        Convert to Company model for database insertion

        Returns:
            Company model instance with page_source='job_posting'
        """
        return Company(
            name=self.company_name,
            source=self.source,
            page_source="job_posting",
            profile_url=self.profile_url,
            overview=(
                self.overview.model_dump(exclude_none=True) if self.overview else None
            ),
            reviews_summary=(
                self.reviews_summary.model_dump() if self.reviews_summary else None
            ),
            salary_estimates=(
                [s.model_dump(exclude_none=True) for s in self.salary_estimates]
                if self.salary_estimates
                else None
            ),
            evaluations=None,  # Not available from job posting
        )


class ScrapedCompanyFromProfile(BaseModel):
    """
    Company data scraped from dedicated company profile pages (full data)

    This is extracted from the company's Glassdoor profile page.
    Provides complete company information including evaluations.
    """

    # Required fields
    company_name: str = Field(min_length=1, description="Company name")
    profile_url: str = Field(min_length=1, description="Glassdoor company profile URL")

    # Metadata
    source: str = Field(default="glassdoor")
    scraped_date: datetime = Field(default_factory=datetime.now)

    # Full company overview from profile
    overview: Optional[CompanyOverview] = Field(
        None,
        description="Complete company overview (size, founded, type, industry, sector, revenue, headquarters, website, description)",
    )

    # Evaluations from profile (numeric ratings)
    evaluations: Optional[CompanyEvaluations] = Field(
        None, description="Company evaluations and ratings from reviews"
    )

    # Note: salary_estimates and reviews_summary should be scraped separately
    # from dedicated tabs if needed (not part of overview extraction)

    @field_validator("company_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace"""
        return v.strip()

    @field_validator("profile_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Basic URL validation"""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    def to_company_model(self) -> Company:
        """
        Convert to Company model for database insertion

        Returns:
            Company model instance with page_source='company_profile'
        """
        return Company(
            name=self.company_name,
            source=self.source,
            page_source="company_profile",
            profile_url=self.profile_url,
            overview=(
                self.overview.model_dump(exclude_none=True) if self.overview else None
            ),
            evaluations=(
                self.evaluations.model_dump(exclude_none=True)
                if self.evaluations
                else None
            ),
            reviews_summary=None,  # Should be fetched separately from reviews tab
            salary_estimates=None,  # Should be fetched separately from salaries tab
        )

    @classmethod
    def from_glassdoor_extract(
        cls,
        company_info: Dict[str, Any],
        company_evaluations: Optional[Dict[str, Any]] = None,
    ) -> "ScrapedCompanyFromProfile":
        """
        Create from glassdoor extract_company_info() and extract_company_evaluations() output

        Args:
            company_info: Dictionary from extract_company_info()
            company_evaluations: Optional dictionary from extract_company_evaluations()

        Returns:
            Validated ScrapedCompanyFromProfile instance
        """
        # Build CompanyOverview from company_info
        overview = CompanyOverview(
            size=company_info.get("size"),
            founded=company_info.get("founded"),
            type=company_info.get("type"),
            industry=company_info.get("industry"),
            sector=None,  # Not in extract output
            revenue=company_info.get("revenue"),
            headquarters=company_info.get("headquarters"),
            website=company_info.get("website"),
            description=company_info.get("description"),
        )

        # Build CompanyEvaluations from company_evaluations
        evaluations = None
        if company_evaluations:
            evaluations = CompanyEvaluations(
                global_rating=company_evaluations.get("global"),
                reviews_count=company_evaluations.get("reviews_count"),
                recommend_to_friend=company_evaluations.get("recommend_to_friend"),
                culture_and_values=company_evaluations.get("culture_and_values"),
                diversity_equity_inclusion=company_evaluations.get(
                    "diversity_equity_inclusion"
                ),
                work_life_balance=company_evaluations.get("work_life_balance"),
                senior_management=company_evaluations.get("senior_management"),
                compensation_and_benefits=company_evaluations.get(
                    "compensation_and_benefits"
                ),
                career_opportunities=company_evaluations.get("career_opportunities"),
            )

        return cls(
            company_name=company_info.get("company_name", ""),
            profile_url=company_info.get("url", ""),
            overview=overview,
            evaluations=evaluations,
        )
