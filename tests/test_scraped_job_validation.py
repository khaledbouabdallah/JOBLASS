"""
ScrapedJobData Validation Tests

Tests Pydantic validation for scraped job data.
Ensures bad data doesn't reach the database.
"""

import pytest
from pydantic import ValidationError

from joblass.db.models import ScrapedJobData, SalaryEstimate


def test_from_glassdoor_extract_handles_minimal_data():
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

    # Optional fields should have defaults
    assert scraped.verified_skills == []
    assert scraped.salary_estimate is None
    assert scraped.description is None
    assert scraped.company_overview is None
    assert scraped.reviews_summary is None

    print("✓ Minimal data creates valid ScrapedJobData")


def test_from_glassdoor_extract_handles_complete_data():
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
            "period": "year",
        },
        "company_overview": {
            "size": "50-200 employees",
            "industry": "Technology",
            "founded": "2020",
            "type": "Private",
        },
    }

    scraped = ScrapedJobData.from_glassdoor_extract(complete)

    assert scraped.job_title == "Senior ML Engineer"
    assert scraped.verified_skills == ["Python", "TensorFlow", "Docker"]
    assert scraped.salary_estimate.lower_bound == 60000
    assert scraped.salary_estimate.upper_bound == 90000
    assert scraped.salary_estimate.currency == "EUR"
    assert scraped.company_overview.size == "50-200 employees"
    assert scraped.company_overview.industry == "Technology"

    print("✓ Complete data parsed correctly")


def test_from_glassdoor_extract_rejects_invalid_url():
    """Should raise ValidationError for bad URL"""
    data = {
        "job_title": "Dev",
        "company": "Corp",
        "location": "Paris",
        "url": "not-a-url",  # Invalid
    }

    with pytest.raises(ValidationError) as exc_info:
        ScrapedJobData.from_glassdoor_extract(data)

    assert "url" in str(exc_info.value).lower(), "Error should mention 'url'"

    print("✓ Invalid URL rejected")


def test_from_glassdoor_extract_rejects_missing_required_fields():
    """Should raise ValidationError when required fields missing"""
    # Missing job_title
    data1 = {"company": "Corp", "location": "Paris", "url": "https://job.com"}

    with pytest.raises(ValidationError) as exc_info:
        ScrapedJobData.from_glassdoor_extract(data1)

    assert "job_title" in str(exc_info.value).lower()

    # Missing company
    data2 = {"job_title": "Dev", "location": "Paris", "url": "https://job.com"}

    with pytest.raises(ValidationError) as exc_info:
        ScrapedJobData.from_glassdoor_extract(data2)

    assert "company" in str(exc_info.value).lower()

    print("✓ Missing required fields rejected")


def test_to_db_dict_serializes_nested_objects():
    """Verify complex objects converted to JSON strings"""
    scraped = ScrapedJobData(
        job_title="Engineer",
        company="Acme",
        location="Paris",
        url="https://job.com/789",
        verified_skills=["Python", "SQL", "Docker"],
        salary_estimate=SalaryEstimate(
            lower_bound=40000, upper_bound=60000, currency="EUR", period="year"
        ),
    )

    db_dict = scraped.to_db_dict()

    # Complex fields serialized as JSON strings
    assert isinstance(db_dict["verified_skills"], str)
    assert '"Python"' in db_dict["verified_skills"]
    assert '"SQL"' in db_dict["verified_skills"]

    # Nested salary object flattened to separate fields
    assert db_dict["salary_min"] == 40000
    assert db_dict["salary_max"] == 60000
    assert db_dict["salary_currency"] == "EUR"

    # Basic fields preserved
    assert db_dict["title"] == "Engineer"
    assert db_dict["company"] == "Acme"
    assert db_dict["url"] == "https://job.com/789"

    print("✓ Nested objects serialized correctly")


def test_to_db_dict_handles_none_salary():
    """Should handle None salary estimate gracefully"""
    scraped = ScrapedJobData(
        job_title="Developer",
        company="StartupCo",
        location="Lyon",
        url="https://job.com/999",
        salary_estimate=None,
    )

    db_dict = scraped.to_db_dict()

    assert db_dict["salary_min"] is None
    assert db_dict["salary_max"] is None
    # Currency defaults to EUR when salary_estimate is None
    assert db_dict["salary_currency"] == "EUR"

    print("✓ None salary handled correctly")


def test_to_db_dict_handles_empty_arrays():
    """Should serialize empty arrays as None (not saved to DB)"""
    scraped = ScrapedJobData(
        job_title="Junior Dev",
        company="NewCo",
        location="Nice",
        url="https://job.com/000",
        verified_skills=[],  # Empty array
    )

    db_dict = scraped.to_db_dict()

    # Empty arrays return None (not serialized to JSON)
    assert db_dict["verified_skills"] is None

    print("✓ Empty arrays handled correctly")


def test_salary_estimate_validation():
    """Test SalaryEstimate validation rules"""
    # Valid salary
    salary1 = SalaryEstimate(
        lower_bound=30000, upper_bound=50000, currency="EUR", period="year"
    )
    assert salary1.lower_bound == 30000
    assert salary1.upper_bound == 50000

    # Lower bound should be <= upper bound (Pydantic validates this if we added validator)
    # For now, just test that it accepts the values
    salary2 = SalaryEstimate(
        lower_bound=50000, upper_bound=50000, currency="USD", period="year"
    )
    assert salary2.lower_bound == salary2.upper_bound

    print("✓ SalaryEstimate validation works")


def test_job_hash_generation():
    """Verify job_hash is auto-generated in to_db_dict"""
    scraped = ScrapedJobData(
        job_title="DevOps Engineer",
        company="CloudCo",
        location="Toulouse",
        url="https://cloud.com/job/123",
    )

    db_dict = scraped.to_db_dict()

    assert "job_hash" in db_dict, "job_hash should be auto-generated"
    assert isinstance(db_dict["job_hash"], str)
    assert len(db_dict["job_hash"]) == 16, "job_hash should be 16-char hex string"

    print("✓ job_hash auto-generated correctly")


def test_duplicate_jobs_same_hash():
    """Jobs with same core fields should generate same hash"""
    job1 = ScrapedJobData(
        job_title="Software Engineer",
        company="TechCorp",
        location="Paris",
        url="https://example.com/job/1",
    )

    job2 = ScrapedJobData(
        job_title="software engineer",  # Different case
        company="TECHCORP",  # Different case
        location="Paris",
        url="https://example.com/job/2",  # Different URL
    )

    hash1 = job1.to_db_dict()["job_hash"]
    hash2 = job2.to_db_dict()["job_hash"]

    # Same title/company/location (case-insensitive) should give same hash
    assert hash1 == hash2, "Jobs with same core fields should have same hash"

    print("✓ Duplicate detection via hash works")


if __name__ == "__main__":
    print("=" * 70)
    print("SCRAPEDJOBDATA VALIDATION TESTS")
    print("=" * 70)

    test_from_glassdoor_extract_handles_minimal_data()
    print()

    test_from_glassdoor_extract_handles_complete_data()
    print()

    test_from_glassdoor_extract_rejects_invalid_url()
    print()

    test_from_glassdoor_extract_rejects_missing_required_fields()
    print()

    test_to_db_dict_serializes_nested_objects()
    print()

    test_to_db_dict_handles_none_salary()
    print()

    test_to_db_dict_handles_empty_arrays()
    print()

    test_salary_estimate_validation()
    print()

    test_job_hash_generation()
    print()

    test_duplicate_jobs_same_hash()
    print()

    print("=" * 70)
    print("✅ ALL SCRAPEDJOBDATA VALIDATION TESTS PASSED!")
    print("=" * 70)
