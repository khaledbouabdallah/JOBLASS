"""
Unit tests for Pydantic model validation

Tests data validation rules WITHOUT database operations.
Ensures bad data doesn't reach the database layer.

Run with: pytest tests/unit/test_models_validation.py -v
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from joblass.db import Application, Company, Job, Score
from joblass.db.models import SalaryEstimate, ScrapedJobData


# ============================================================================
# DATABASE MODELS (SQLModel with Pydantic validation)
# ============================================================================


class TestJobModel:
    """Test Job dataclass validation"""

    def test_job_creation_minimal(self):
        """Test creating job with minimal required fields"""
        job = Job(
            title="Software Engineer",
            company="TechCorp",
            location="Paris",
            url="https://example.com/job/1",
            source="glassdoor",
        )
        assert job.title == "Software Engineer"
        assert job.company == "TechCorp"
        assert job.id is None
        assert job.salary_currency == "EUR"  # Default value

    def test_job_creation_full(self):
        """Test creating job with all fields"""
        job = Job(
            title="ML Engineer",
            company="AI Corp",
            location="Lyon",
            url="https://example.com/job/2",
            source="glassdoor",
            description="Great ML role",
            tech_stack=["Python", "TensorFlow", "ML"],
            salary_estimate={
                "lower_bound": 40000,
                "upper_bound": 60000,
                "median": 50000,
                "currency": "EUR",
            },
            is_easy_apply=True,
            job_external_id="ext456",
            posted_date=datetime(2025, 10, 20),
        )
        # Access via properties
        assert job.salary_min == 40000
        assert job.salary_max == 60000
        assert job.tech_stack == ["Python", "TensorFlow", "ML"]
        assert job.is_easy_apply is True
        assert job.job_external_id == "ext456"
        assert job.posted_date == datetime(2025, 10, 20)


class TestApplicationModel:
    """Test Application dataclass validation"""

    def test_application_creation(self):
        """Test creating application"""
        app = Application(
            job_id=1, status="applied", application_method="online_portal"
        )
        assert app.job_id == 1
        assert app.status == "applied"
        assert app.application_method == "online_portal"
        assert app.id is None

    def test_application_invalid_status(self):
        """Test that invalid status raises ValidationError"""
        with pytest.raises(ValidationError, match="Value error"):
            Application(job_id=1, status="invalid_status", application_method="online")

    def test_application_valid_statuses(self):
        """Test all valid statuses"""
        valid_statuses = [
            "pending",
            "applied",
            "rejected",
            "interview",
            "offer",
            "declined",
            "accepted",
        ]
        for status in valid_statuses:
            app = Application(
                job_id=1, status=status, application_method="online_portal"
            )
            assert app.status == status


class TestCompanyModel:
    """Test Company dataclass validation"""

    def test_company_creation_minimal(self):
        """Test creating company with required fields only"""
        company = Company(
            name="TechStartup Inc",
            page_source="job_posting",
            source="glassdoor",
        )
        assert company.name == "TechStartup Inc"
        assert company.page_source == "job_posting"
        assert company.source == "glassdoor"
        assert company.profile_url is None
        assert company.overview is None
        assert company.reviews_summary is None
        assert company.evaluations is None

    def test_company_creation_full(self):
        """Test creating company with all fields"""
        company = Company(
            name="AI Corporation",
            page_source="company_profile",
            source="glassdoor",
            profile_url="https://glassdoor.com/Overview/Working-at-AI-Corp.htm",
            overview={
                "size": "500-1000 employees",
                "industry": "Artificial Intelligence",
                "founded": "2015",
            },
            evaluations={
                "global_rating": 4.2,
                "reviews_count": 150,
                "culture_and_values": 4.0,
            },
            reviews_summary={
                "pros": [{"text": "Great work-life balance", "count": 50}],
                "cons": [{"text": "Low salary", "count": 30}],
            },
        )
        assert company.name == "AI Corporation"
        assert company.overview["size"] == "500-1000 employees"
        assert company.evaluations["global_rating"] == 4.2
        assert len(company.reviews_summary["pros"]) == 1


class TestScoreModel:
    """Test Score dataclass validation"""

    def test_score_creation(self):
        """Test creating score"""
        score = Score(job_id=1)
        assert score.job_id == 1
        assert score.total_score == 0.0

    def test_score_calculate_total_default_weights(self):
        """Test score calculation with default weights"""
        score = Score(
            job_id=1,
            tech_match=80.0,
            learning_opportunity=70.0,
            company_quality=60.0,
            practical_factors=90.0,
        )
        # Should auto-calculate in __post_init__
        assert score.total_score > 0

        # Recalculate to verify
        total = score.calculate_total()
        expected = (80 * 0.30) + (70 * 0.25) + (60 * 0.20) + (90 * 0.25)
        assert total == pytest.approx(expected, rel=0.01)

    def test_score_calculate_total_custom_weights(self):
        """Test score calculation with custom weights"""
        score = Score(
            job_id=1,
            tech_match=100.0,
            learning_opportunity=80.0,
            company_quality=60.0,
            practical_factors=40.0,
        )
        total = score.calculate_total(
            tech_weight=0.5,
            learning_weight=0.3,
            company_weight=0.1,
            practical_weight=0.1,
        )
        expected = (100 * 0.5) + (80 * 0.3) + (60 * 0.1) + (40 * 0.1)
        assert total == pytest.approx(expected, rel=0.01)


# ============================================================================
# SCRAPED DATA MODELS (Pure Pydantic)
# ============================================================================


class TestScrapedJobData:
    """Test ScrapedJobData validation"""

    def test_minimal_data_creates_valid_object(self):
        """Should create valid object with required fields only"""
        minimal = {
            "job_title": "Developer",
            "company": "TechCorp",
            "location": "Paris",
            "url": "https://job.com/123",
        }

        scraped = ScrapedJobData.from_glassdoor_extract(minimal)

        assert scraped.job_title == "Developer"
        assert scraped.company == "TechCorp"
        assert scraped.location == "Paris"
        assert scraped.url == "https://job.com/123"
        assert scraped.verified_skills == []
        assert scraped.salary_estimate is None

    def test_complete_data_parsed_correctly(self):
        """Should parse all fields when provided"""
        complete = {
            "job_title": "Senior ML Engineer",
            "company": "AI Startup",
            "location": "Paris, France",
            "url": "https://glassdoor.com/job/456",
            "description": "Build ML models for production",
            "verified_skills": ["Python", "TensorFlow", "Docker"],
            "salary_estimate": {
                "lower_bound": 60000,
                "upper_bound": 90000,
                "currency": "EUR",
            },
        }

        scraped = ScrapedJobData.from_glassdoor_extract(complete)

        assert scraped.job_title == "Senior ML Engineer"
        assert scraped.verified_skills == ["Python", "TensorFlow", "Docker"]
        assert scraped.salary_estimate.lower_bound == 60000
        assert scraped.salary_estimate.upper_bound == 90000
        assert scraped.salary_estimate.currency == "EUR"

    def test_invalid_url_rejected(self):
        """Should raise ValidationError for bad URL"""
        data = {
            "job_title": "Dev",
            "company": "Corp",
            "location": "Paris",
            "url": "not-a-url",  # Invalid
        }

        with pytest.raises(ValidationError) as exc_info:
            ScrapedJobData.from_glassdoor_extract(data)

        assert "url" in str(exc_info.value).lower()

    def test_missing_required_fields_rejected(self):
        """Should raise ValidationError when required fields missing"""
        # Missing job_title
        data1 = {"company": "Corp", "location": "Paris", "url": "https://job.com"}

        with pytest.raises(ValidationError) as exc_info:
            ScrapedJobData.from_glassdoor_extract(data1)

        assert "job_title" in str(exc_info.value).lower()

    def test_to_job_model_conversion(self):
        """Verify conversion to Job model"""
        scraped = ScrapedJobData(
            job_title="Engineer",
            company="Acme",
            location="Paris",
            url="https://job.com/789",
            verified_skills=["Python", "SQL", "Docker"],
            salary_estimate=SalaryEstimate(
                lower_bound=40000, upper_bound=60000, currency="EUR"
            ),
        )

        job = scraped.to_job_model(session_id=123)

        assert job.title == "Engineer"
        assert job.company == "Acme"
        assert job.url == "https://job.com/789"
        assert job.session_id == 123
        assert job.salary_min == 40000
        assert job.salary_max == 60000
        assert "Python" in job.tech_stack

    def test_get_all_skills_deduplicates(self):
        """Test getting combined skills without duplicates"""
        job = ScrapedJobData(
            job_title="Engineer",
            company="Corp",
            location="Paris",
            url="https://example.com/job/123",
            verified_skills=["Python", "SQL"],
            required_skills=["Java", "Python"],  # Python is duplicate
        )
        all_skills = job.get_all_skills()
        assert len(all_skills) == 3  # Python, SQL, Java (deduplicated)
        assert "Python" in all_skills
        assert "SQL" in all_skills
        assert "Java" in all_skills


class TestSalaryEstimate:
    """Test SalaryEstimate validation"""

    def test_valid_salary(self):
        """Test valid salary creation"""
        salary = SalaryEstimate(
            lower_bound=30000, upper_bound=50000, median=40000, currency="EUR"
        )
        assert salary.lower_bound == 30000
        assert salary.upper_bound == 50000
        assert salary.median == 40000
        assert salary.currency == "EUR"

    def test_salary_with_only_bounds(self):
        """Test salary with only min/max"""
        salary = SalaryEstimate(lower_bound=35000, upper_bound=45000)
        assert salary.lower_bound == 35000
        assert salary.upper_bound == 45000
        assert salary.median is None
        assert salary.currency is None

    def test_invalid_upper_less_than_lower(self):
        """Test that upper bound must be >= lower bound"""
        with pytest.raises(ValidationError) as exc_info:
            SalaryEstimate(lower_bound=50000, upper_bound=30000)
        assert "upper_bound must be >= lower_bound" in str(exc_info.value)

    def test_negative_salary_rejected(self):
        """Test that negative salaries are rejected"""
        with pytest.raises(ValidationError):
            SalaryEstimate(lower_bound=-10000, upper_bound=50000)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
