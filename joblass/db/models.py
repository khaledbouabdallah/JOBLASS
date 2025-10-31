"""
Data models for job search database using Pydantic
"""

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

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

    def to_json(self) -> str:
        """Convert to JSON string for storage"""
        return json.dumps(
            {
                "pros": [{"text": p.text, "count": p.count} for p in self.pros],
                "cons": [{"text": c.text, "count": c.count} for c in self.cons],
            }
        )

    @classmethod
    def from_json(cls, json_str: Optional[str]) -> Optional["ReviewSummary"]:
        """Parse from JSON string"""
        if not json_str:
            return None
        try:
            data = json.loads(json_str)
            return cls(
                pros=[ReviewItem(**p) for p in data.get("pros", [])],
                cons=[ReviewItem(**c) for c in data.get("cons", [])],
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


class CompanyOverview(BaseModel):
    """Company overview information"""

    size: Optional[str] = None
    founded: Optional[str] = None
    type: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    revenue: Optional[str] = None

    def to_json(self) -> str:
        """Convert to JSON string for storage"""
        return json.dumps(self.model_dump(exclude_none=True))

    @classmethod
    def from_json(cls, json_str: Optional[str]) -> Optional["CompanyOverview"]:
        """Parse from JSON string"""
        if not json_str:
            return None
        try:
            data = json.loads(json_str)
            return cls(**data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


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

    def to_json(self) -> str:
        """Convert to JSON string for storage"""
        return json.dumps(self.model_dump(exclude_none=True))

    @classmethod
    def from_json(cls, json_str: Optional[str]) -> Optional["SalaryEstimate"]:
        """Parse from JSON string"""
        if not json_str:
            return None
        try:
            data = json.loads(json_str)
            return cls(**data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None


class SkillsList(BaseModel):
    """List of skills with validation"""

    skills: List[str] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def remove_empty_skills(cls, v: List[str]) -> List[str]:
        """Remove empty or whitespace-only skills"""
        return [skill.strip() for skill in v if skill and skill.strip()]

    def to_json(self) -> str:
        """Convert to JSON string for storage"""
        return json.dumps(self.skills)

    @classmethod
    def from_json(cls, json_str: Optional[str]) -> Optional["SkillsList"]:
        """Parse from JSON string"""
        if not json_str:
            return None
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return cls(skills=data)
            return None
        except (json.JSONDecodeError, TypeError):
            return None


# ============================================================================
# Core Database Models
# ============================================================================


class Job(BaseModel):
    """Represents a job posting"""

    # Required fields
    title: str = Field(min_length=1, description="Job title")
    company: str = Field(min_length=1, description="Company name")
    location: str = Field(min_length=1, description="Job location")
    url: str = Field(description="Job posting URL")
    source: str = Field(description="Source platform (e.g., 'glassdoor', 'linkedin')")

    # Optional fields
    id: Optional[int] = None
    job_hash: Optional[str] = Field(
        None, description="Unique hash for deduplication (auto-generated)"
    )
    description: Optional[str] = None
    tech_stack: Optional[str] = None  # JSON string of all tech/skills
    verified_skills: Optional[str] = None  # JSON string of verified skills
    required_skills: Optional[str] = None  # JSON string of required skills
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    salary_median: Optional[int] = Field(None, ge=0)
    salary_currency: Optional[str] = "EUR"
    posted_date: Optional[datetime] = None
    scraped_date: datetime = Field(default_factory=datetime.now)

    # Additional metadata
    job_type: Optional[str] = None  # 'internship', 'full-time', etc.
    remote_option: Optional[str] = None  # 'remote', 'hybrid', 'onsite'
    is_easy_apply: Optional[bool] = None  # Easy apply flag
    job_external_id: Optional[str] = None  # External job ID from source site

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
    raw_html: Optional[str] = None  # TODO remove

    model_config = {"validate_assignment": True}

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

    def generate_hash(self) -> str:
        """
        Generate unique hash for deduplication

        Hash is based on:
        1. job_external_id (if available) - most reliable
        2. Normalized title + company + location (fallback)

        Returns:
            SHA256 hash string (first 16 chars for readability)
        """

        # Normalize text: lowercase, remove extra whitespace
        def normalize(text: str) -> str:
            return " ".join(text.lower().strip().split())

        # Priority 1: Use external ID if available (most reliable)
        if self.job_external_id:
            hash_input = f"ext:{self.source}:{self.job_external_id}"
        else:
            # Priority 2: Title + Company + Location combination
            # Normalize to handle minor variations (e.g., "ML Engineer" vs "ml engineer")
            normalized_title = normalize(self.title)
            normalized_company = normalize(self.company)
            normalized_location = normalize(self.location)
            hash_input = f"{normalized_title}|{normalized_company}|{normalized_location}|{self.source}"

        # Generate SHA256 hash and take first 16 chars for readability
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    @model_validator(mode="after")
    def auto_generate_hash(self) -> "Job":
        """Auto-generate job_hash if not provided"""
        if not self.job_hash:
            object.__setattr__(self, "job_hash", self.generate_hash())
        return self


class SearchCriteria(BaseModel):
    """Represents search criteria for job search"""

    keywords: str
    location: str
    search_url: str
    only_quick_apply: bool = False
    remote_only: bool = False
    company_min_rating: Optional[int] = Field(None, ge=1, le=5)  # (1,2,3,4,5)
    date_posted_within_period: Optional[str] = None  # (yesterday, last days, etc.)
    location_city_filter: Optional[str] = None  # index based
    job_type: Optional[str] = None  # 'internship', 'full-time', etc.
    company_sector: Optional[str] = None  # 'technology', 'finance', etc.
    experience_level: Optional[str] = None  # 'entry', 'mid', 'senior'
    professional_domain: Optional[str] = None  # 'software', 'data science', etc.
    specific_company: Optional[str] = None
    company_size: Optional[str] = None  # '1-50', '51-200', etc.
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)


class SearchSession(BaseModel):
    """Tracks job search sessions"""

    search_criteria: SearchCriteria
    id: Optional[int] = None
    jobs_found: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Application(BaseModel):
    """Tracks application status for a job"""

    job_id: int = Field(ge=1, description="Foreign key to jobs table")
    status: Literal[
        "pending", "applied", "rejected", "interview", "offer", "declined", "accepted"
    ]
    application_method: Literal[
        "online_portal", "email", "referral", "in_person", "other"
    ]
    id: Optional[int] = None
    applied_date: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.now)

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

    # Keep for backward compatibility - use ClassVar so Pydantic doesn't treat it as a field
    VALID_STATUSES: ClassVar[set] = {
        "pending",
        "applied",
        "rejected",
        "interview",
        "offer",
        "declined",
        "accepted",
    }


class Score(BaseModel):
    """Job scoring and ranking"""

    job_id: int = Field(ge=1, description="Foreign key to jobs table")

    # Score components (0-100 each)
    tech_match: float = Field(default=0.0, ge=0.0, le=100.0)
    learning_opportunity: float = Field(default=0.0, ge=0.0, le=100.0)
    company_quality: float = Field(default=0.0, ge=0.0, le=100.0)
    practical_factors: float = Field(default=0.0, ge=0.0, le=100.0)

    # Total weighted score
    total_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Penalties and bonuses
    penalties: Optional[str] = None  # JSON string of penalty reasons
    bonuses: Optional[str] = None  # JSON string of bonus reasons

    id: Optional[int] = None
    scored_date: datetime = Field(default_factory=datetime.now)

    # LLM analysis results
    llm_analysis: Optional[str] = None  # JSON string of LLM insights
    red_flags: Optional[str] = None  # JSON list of identified red flags

    # Disable validate_assignment to avoid recursion in calculate_total
    model_config = {"validate_assignment": False}

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

    @model_validator(mode="after")
    def auto_calculate_total(self) -> "Score":
        """Calculate total score if component scores are set"""
        if any(
            [
                self.tech_match,
                self.learning_opportunity,
                self.company_quality,
                self.practical_factors,
            ]
        ):
            # Use object.__setattr__ to avoid validation recursion
            object.__setattr__(
                self,
                "total_score",
                round(
                    self.tech_match * 0.30
                    + self.learning_opportunity * 0.25
                    + self.company_quality * 0.20
                    + self.practical_factors * 0.25,
                    2,
                ),
            )
        return self


# ============================================================================
# ScrapedJobData - Validation model for raw scraping data
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
    company_overview: Optional[CompanyOverview] = None
    reviews_summary: Optional[ReviewSummary] = None

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
        """Remove empty or whitespace-only skills"""
        return [skill.strip() for skill in v if skill and skill.strip()]

    @model_validator(mode="after")
    def validate_skills_not_duplicate(self) -> "ScrapedJobData":
        """Ensure no duplicate skills in each list"""
        self.verified_skills = list(dict.fromkeys(self.verified_skills))
        self.required_skills = list(dict.fromkeys(self.required_skills))
        return self

    def get_all_skills(self) -> List[str]:
        """Get combined unique skills from verified and required"""
        return list(dict.fromkeys(self.verified_skills + self.required_skills))

    def to_db_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary suitable for database insertion

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
            "is_easy_apply": self.is_easy_apply,
            "job_external_id": self.job_external_id,
            # JSON-serialized fields
            "verified_skills": (
                json.dumps(self.verified_skills) if self.verified_skills else None
            ),
            "required_skills": (
                json.dumps(self.required_skills) if self.required_skills else None
            ),
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
            "company_size": (
                self.company_overview.size if self.company_overview else None
            ),
            "company_industry": (
                self.company_overview.industry if self.company_overview else None
            ),
            "company_sector": (
                self.company_overview.sector if self.company_overview else None
            ),
            "company_founded": (
                self.company_overview.founded if self.company_overview else None
            ),
            "company_type": (
                self.company_overview.type if self.company_overview else None
            ),
            "company_revenue": (
                self.company_overview.revenue if self.company_overview else None
            ),
            "reviews_data": (
                self.reviews_summary.to_json() if self.reviews_summary else None
            ),
        }

    @classmethod
    def from_glassdoor_extract(cls, data: Dict[str, Any]) -> "ScrapedJobData":
        """
        Create from glassdoor extract_job_details() output

        Args:
            data: Dictionary from extract_job_details()

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

        # Handle company overview
        company_overview = None
        if data.get("company_overview"):
            company_overview = CompanyOverview(**data["company_overview"])

        # Handle reviews summary
        reviews_summary = None
        if data.get("reviews_summary"):
            reviews_data = data["reviews_summary"]
            reviews_summary = ReviewSummary(
                pros=[ReviewItem(**p) for p in reviews_data.get("pros", [])],
                cons=[ReviewItem(**c) for c in reviews_data.get("cons", [])],
            )

        # URL is the Glassdoor job page URL
        return cls(
            job_title=data.get("job_title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            url=data.get("url"),  # Glassdoor page URL
            is_easy_apply=data.get("is_easy_apply", False),
            job_external_id=data.get("job_external_id"),
            posted_date=data.get("posted_date"),
            description=data.get("description"),
            verified_skills=data.get("verified_skills", []),
            required_skills=data.get("required_skills", []),
            salary_estimate=salary_estimate,
            company_overview=company_overview,
            reviews_summary=reviews_summary,
        )
