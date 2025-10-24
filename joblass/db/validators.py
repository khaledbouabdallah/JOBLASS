"""
Pydantic validators for scraped job data
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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
    url: str = Field(min_length=1, description="Job posting URL")

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
    def validate_url(cls, v: str) -> str:
        """Basic URL validation"""
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
    def from_glassdoor_extract(cls, data: Dict[str, Any], url: str) -> "ScrapedJobData":
        """
        Create from glassdoor extract_job_details() output

        Args:
            data: Dictionary from extract_job_details()
            url: Job posting URL

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

        return cls(
            job_title=data.get("job_title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            url=url,
            description=data.get("description"),
            verified_skills=data.get("verified_skills", []),
            required_skills=data.get("required_skills", []),
            salary_estimate=salary_estimate,
            company_overview=company_overview,
            reviews_summary=reviews_summary,
        )
