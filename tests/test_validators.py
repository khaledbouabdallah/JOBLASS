"""
Tests for Pydantic validators in joblass.db.validators

Run with: pytest tests/test_validators.py -v
"""

import json

import pytest
from pydantic import ValidationError

from joblass.db.validators import (
    CompanyOverview,
    ReviewItem,
    ReviewSummary,
    SalaryEstimate,
    ScrapedJobData,
    SkillsList,
)


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

    def test_negative_salary(self):
        """Test that negative salaries are rejected"""
        with pytest.raises(ValidationError):
            SalaryEstimate(lower_bound=-10000, upper_bound=50000)

    def test_salary_to_json(self):
        """Test JSON serialization"""
        salary = SalaryEstimate(
            lower_bound=30000, upper_bound=50000, median=40000, currency="EUR"
        )
        json_str = salary.to_json()
        data = json.loads(json_str)
        assert data["lower_bound"] == 30000
        assert data["upper_bound"] == 50000
        assert data["median"] == 40000
        assert data["currency"] == "EUR"

    def test_salary_from_json(self):
        """Test JSON deserialization"""
        json_str = '{"lower_bound": 30000, "upper_bound": 50000, "currency": "EUR"}'
        salary = SalaryEstimate.from_json(json_str)
        assert salary is not None
        assert salary.lower_bound == 30000
        assert salary.upper_bound == 50000
        assert salary.currency == "EUR"

    def test_salary_from_invalid_json(self):
        """Test handling of invalid JSON"""
        assert SalaryEstimate.from_json(None) is None
        assert SalaryEstimate.from_json("") is None
        assert SalaryEstimate.from_json("invalid") is None


class TestCompanyOverview:
    """Test CompanyOverview validation"""

    def test_valid_company_overview(self):
        """Test valid company overview"""
        overview = CompanyOverview(
            size="51 à 200 employés",
            founded="2010",
            type="Start-up",
            industry="AI",
            sector="Technology",
            revenue="10M-50M EUR",
        )
        assert overview.size == "51 à 200 employés"
        assert overview.founded == "2010"
        assert overview.type == "Start-up"

    def test_partial_company_overview(self):
        """Test company overview with some fields"""
        overview = CompanyOverview(size="100-500", industry="Tech")
        assert overview.size == "100-500"
        assert overview.industry == "Tech"
        assert overview.founded is None

    def test_company_overview_to_json(self):
        """Test JSON serialization"""
        overview = CompanyOverview(size="50-100", industry="Software")
        json_str = overview.to_json()
        data = json.loads(json_str)
        assert data["size"] == "50-100"
        assert data["industry"] == "Software"
        assert "founded" not in data  # None values excluded

    def test_company_overview_from_json(self):
        """Test JSON deserialization"""
        json_str = '{"size": "50-100", "industry": "Software", "founded": "2015"}'
        overview = CompanyOverview.from_json(json_str)
        assert overview is not None
        assert overview.size == "50-100"
        assert overview.founded == "2015"


class TestReviewSummary:
    """Test ReviewSummary validation"""

    def test_valid_review_summary(self):
        """Test valid review summary"""
        summary = ReviewSummary(
            pros=[
                ReviewItem(text="Great team", count=15),
                ReviewItem(text="Good tech stack", count=10),
            ],
            cons=[ReviewItem(text="Long hours", count=5)],
        )
        assert len(summary.pros) == 2
        assert len(summary.cons) == 1
        assert summary.pros[0].text == "Great team"
        assert summary.pros[0].count == 15

    def test_empty_review_summary(self):
        """Test empty review summary"""
        summary = ReviewSummary()
        assert len(summary.pros) == 0
        assert len(summary.cons) == 0

    def test_negative_count_rejected(self):
        """Test that negative counts are rejected"""
        with pytest.raises(ValidationError):
            ReviewItem(text="Test", count=-5)

    def test_review_summary_to_json(self):
        """Test JSON serialization"""
        summary = ReviewSummary(
            pros=[ReviewItem(text="Good", count=10)],
            cons=[ReviewItem(text="Bad", count=3)],
        )
        json_str = summary.to_json()
        data = json.loads(json_str)
        assert len(data["pros"]) == 1
        assert data["pros"][0]["text"] == "Good"
        assert data["pros"][0]["count"] == 10

    def test_review_summary_from_json(self):
        """Test JSON deserialization"""
        json_str = '{"pros": [{"text": "Good", "count": 10}], "cons": []}'
        summary = ReviewSummary.from_json(json_str)
        assert summary is not None
        assert len(summary.pros) == 1
        assert summary.pros[0].text == "Good"


class TestSkillsList:
    """Test SkillsList validation"""

    def test_valid_skills_list(self):
        """Test valid skills list"""
        skills = SkillsList(skills=["Python", "JavaScript", "SQL"])
        assert len(skills.skills) == 3
        assert "Python" in skills.skills

    def test_empty_skills_removed(self):
        """Test that empty strings are removed"""
        skills = SkillsList(skills=["Python", "", "  ", "SQL"])
        assert len(skills.skills) == 2
        assert "" not in skills.skills

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed"""
        skills = SkillsList(skills=["  Python  ", "SQL"])
        assert skills.skills[0] == "Python"
        assert skills.skills[1] == "SQL"

    def test_skills_to_json(self):
        """Test JSON serialization"""
        skills = SkillsList(skills=["Python", "JavaScript"])
        json_str = skills.to_json()
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_skills_from_json(self):
        """Test JSON deserialization"""
        json_str = '["Python", "JavaScript", "SQL"]'
        skills = SkillsList.from_json(json_str)
        assert skills is not None
        assert len(skills.skills) == 3


class TestScrapedJobData:
    """Test ScrapedJobData validation"""

    def test_valid_job_data(self):
        """Test valid job data creation"""
        job = ScrapedJobData(
            job_title="ML Engineer",
            company="TechCorp",
            location="Paris",
            url="https://example.com/job/123",
            description="Great job",
        )
        assert job.job_title == "ML Engineer"
        assert job.company == "TechCorp"
        assert job.location == "Paris"
        assert job.source == "glassdoor"

    def test_required_fields_missing(self):
        """Test that missing required fields are rejected"""
        with pytest.raises(ValidationError):
            ScrapedJobData(
                job_title="",  # Empty title
                company="TechCorp",
                location="Paris",
                url="https://example.com/job/123",
            )

    def test_invalid_url(self):
        """Test that invalid URLs are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            ScrapedJobData(
                job_title="Engineer",
                company="Corp",
                location="Paris",
                url="not-a-url",
            )
        assert "URL must start with http" in str(exc_info.value)

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped from text fields"""
        job = ScrapedJobData(
            job_title="  ML Engineer  ",
            company="  TechCorp  ",
            location="  Paris  ",
            url="https://example.com/job/123",
        )
        assert job.job_title == "ML Engineer"
        assert job.company == "TechCorp"
        assert job.location == "Paris"

    def test_duplicate_skills_removed(self):
        """Test that duplicate skills are removed"""
        job = ScrapedJobData(
            job_title="Engineer",
            company="Corp",
            location="Paris",
            url="https://example.com/job/123",
            verified_skills=["Python", "Python", "SQL"],
            required_skills=["Python", "Java", "Java"],
        )
        assert len(job.verified_skills) == 2  # Python, SQL
        assert len(job.required_skills) == 2  # Python, Java

    def test_get_all_skills(self):
        """Test getting combined skills"""
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

    def test_to_db_dict(self):
        """Test conversion to database dictionary"""
        job = ScrapedJobData(
            job_title="ML Engineer",
            company="TechCorp",
            location="Paris",
            url="https://example.com/job/123",
            verified_skills=["Python"],
            required_skills=["ML"],
            salary_estimate=SalaryEstimate(
                lower_bound=40000, upper_bound=60000, currency="EUR"
            ),
        )

        db_dict = job.to_db_dict()

        assert db_dict["title"] == "ML Engineer"
        assert db_dict["company"] == "TechCorp"
        assert db_dict["salary_min"] == 40000
        assert db_dict["salary_max"] == 60000
        assert db_dict["salary_currency"] == "EUR"
        assert isinstance(db_dict["verified_skills"], str)  # JSON string
        assert isinstance(db_dict["tech_stack"], str)  # JSON string

    def test_from_glassdoor_extract(self):
        """Test creating from Glassdoor extraction data"""
        raw_data = {
            "job_title": "Data Scientist",
            "company": "AI Corp",
            "location": "Lyon",
            "url": "https://glassdoor.fr/job/data-scientist-123",
            "description": "Work on ML models",
            "verified_skills": ["Python", "TensorFlow"],
            "required_skills": ["Statistics"],
            "salary_estimate": {
                "lower_bound": 45000,
                "upper_bound": 65000,
                "currency": "EUR",
            },
            "company_overview": {
                "size": "100-500",
                "industry": "AI",
            },
        }

        job = ScrapedJobData.from_glassdoor_extract(raw_data)

        assert job.job_title == "Data Scientist"
        assert job.company == "AI Corp"
        assert len(job.verified_skills) == 2
        assert job.salary_estimate is not None
        assert job.salary_estimate.lower_bound == 45000
        assert job.company_overview is not None
        assert job.company_overview.size == "100-500"

    def test_from_glassdoor_extract_minimal(self):
        """Test creating with minimal data"""
        raw_data = {
            "job_title": "Engineer",
            "company": "Corp",
            "location": "Paris",
            "url": "https://glassdoor.fr/job/engineer-123",
        }

        job = ScrapedJobData.from_glassdoor_extract(raw_data)

        assert job.job_title == "Engineer"
        assert job.salary_estimate is None
        assert job.company_overview is None
        assert len(job.verified_skills) == 0


class TestIntegration:
    """Integration tests for complete workflows"""

    def test_full_workflow_glassdoor_to_db_dict(self):
        """Test complete workflow from scraping to database format"""
        # Simulate Glassdoor extraction
        scraped_data = {
            "job_title": "Senior ML Engineer",
            "company": "DataTech Inc",
            "location": "Paris, Île-de-France",
            "description": "Build ML pipelines...",
            "verified_skills": ["Python", "PyTorch", "AWS"],
            "required_skills": ["Machine Learning", "Deep Learning"],
            "url": "https://www.glassdoor.fr/job/ml-engineer-123456",
            "salary_estimate": {
                "lower_bound": 55000,
                "upper_bound": 75000,
                "median": 65000,
                "currency": "EUR",
            },
            "company_overview": {
                "size": "201 à 500 employés",
                "founded": "2015",
                "type": "Start-up",
                "industry": "Intelligence Artificielle",
                "sector": "Technologie",
            },
            "reviews_summary": {
                "pros": [
                    {"text": "Cutting-edge tech", "count": 25},
                    {"text": "Smart colleagues", "count": 20},
                ],
                "cons": [{"text": "Fast-paced", "count": 10}],
            },
        }

        # Validate
        validated = ScrapedJobData.from_glassdoor_extract(scraped_data)

        # Check validation
        assert validated.job_title == "Senior ML Engineer"
        assert len(validated.get_all_skills()) == 5
        assert validated.salary_estimate.median == 65000
        assert len(validated.reviews_summary.pros) == 2

        # Convert to DB format
        db_dict = validated.to_db_dict()

        # Verify DB format
        assert db_dict["title"] == "Senior ML Engineer"
        assert db_dict["company"] == "DataTech Inc"
        assert db_dict["salary_min"] == 55000
        assert db_dict["salary_max"] == 75000
        assert db_dict["salary_median"] == 65000
        assert db_dict["company_founded"] == "2015"
        assert db_dict["company_type"] == "Start-up"

        # Verify JSON fields
        assert isinstance(db_dict["verified_skills"], str)
        assert isinstance(db_dict["tech_stack"], str)
        assert isinstance(db_dict["reviews_data"], str)

        # Verify JSON content
        tech_stack = json.loads(db_dict["tech_stack"])
        assert len(tech_stack) == 5
        assert "Python" in tech_stack

        reviews = json.loads(db_dict["reviews_data"])
        assert len(reviews["pros"]) == 2

    def test_error_handling_missing_required_data(self):
        """Test error handling when required data is missing"""
        incomplete_data = {
            "company": "SomeCorp",
            "location": "Paris",
            # Missing job_title
        }

        with pytest.raises(ValidationError) as exc_info:
            ScrapedJobData.from_glassdoor_extract(incomplete_data)

        errors = exc_info.value.errors()
        assert any("job_title" in str(error) for error in errors)

    def test_error_handling_invalid_nested_data(self):
        """Test error handling with invalid nested data"""
        bad_data = {
            "job_title": "Engineer",
            "company": "Corp",
            "location": "Paris",
            "salary_estimate": {
                "lower_bound": 60000,
                "upper_bound": 40000,  # Invalid: upper < lower
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            ScrapedJobData.from_glassdoor_extract(bad_data)

        assert "upper_bound must be >= lower_bound" in str(exc_info.value)
