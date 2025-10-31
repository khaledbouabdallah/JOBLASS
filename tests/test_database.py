"""
Tests for database models and repository

Run with: pytest tests/test_database.py -v
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from joblass.db import (
    Application,
    Job,
    Score,
    ApplicationRepository,
    JobRepository,
    ScoreRepository,
)
from joblass.db.connection import get_db_connection, init_db


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Monkey patch the DB_PATH
        import joblass.db.connection as conn_module

        original_path = conn_module.DB_PATH
        conn_module.DB_PATH = db_path

        # Initialize database
        init_db()

        yield db_path

        # Restore original path
        conn_module.DB_PATH = original_path


class TestJobModel:
    """Test Job dataclass"""

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
            tech_stack='["Python", "TensorFlow"]',
            verified_skills='["Python"]',
            required_skills='["ML"]',
            salary_min=40000,
            salary_max=60000,
            salary_median=50000,
            company_size="50-100",
            company_sector="AI",
            is_easy_apply=True,
            job_external_id="ext456",
            posted_date=datetime(2025, 10, 20),
        )
        assert job.salary_min == 40000
        assert job.verified_skills == '["Python"]'
        assert job.company_sector == "AI"
        assert job.is_easy_apply is True
        assert job.job_external_id == "ext456"
        assert job.posted_date == datetime(2025, 10, 20)

    def test_job_missing_title_raises_error(self):
        """Test that missing title raises ValidationError"""
        with pytest.raises(
            ValidationError, match="String should have at least 1 characters"
        ):
            Job(
                title="",  # Empty title
                company="Corp",
                location="Paris",
                url="https://example.com/job/3",
                source="glassdoor",
            )


class TestApplicationModel:
    """Test Application dataclass"""

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
        with pytest.raises(ValidationError, match="Input should be"):
            Application(job_id=1, status="invalid_status")

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


class TestScoreModel:
    """Test Score dataclass"""

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


class TestJobRepository:
    """Test JobRepository operations"""

    def test_insert_job(self, temp_db):
        """Test inserting a job"""
        job = Job(
            title="Backend Developer",
            company="StartupCo",
            location="Marseille",
            url="https://example.com/job/backend-1",
            source="glassdoor",
            description="Build APIs",
        )

        job_id = JobRepository.insert(job)
        assert job_id is not None
        assert job_id > 0

    def test_insert_duplicate_url_fails(self, temp_db):
        """Test that inserting duplicate job_hash fails (not URL)"""
        # Create two jobs with SAME title/company/location (same hash)
        # but DIFFERENT URLs - should still be detected as duplicate
        job1 = Job(
            title="Developer",
            company="Corp1",
            location="Paris",
            url="https://example.com/job/url-1",
            source="glassdoor",
        )

        job2 = Job(
            title="Developer",  # Same title
            company="Corp1",  # Same company
            location="Paris",  # Same location
            url="https://example.com/job/url-2",  # Different URL (shouldn't matter)
            source="glassdoor",  # Same source
        )

        job_id_1 = JobRepository.insert(job1)
        job_id_2 = JobRepository.insert(job2)

        assert job_id_1 is not None
        assert job_id_2 is None  # Should fail due to duplicate hash

        # Verify both have the same hash
        assert job1.job_hash == job2.job_hash

    def test_get_by_id(self, temp_db):
        """Test getting job by ID"""
        job = Job(
            title="Frontend Dev",
            company="WebCorp",
            location="Nice",
            url="https://example.com/job/frontend-1",
            source="glassdoor",
        )

        job_id = JobRepository.insert(job)
        retrieved = JobRepository.get_by_id(job_id)

        assert retrieved is not None
        assert retrieved.id == job_id
        assert retrieved.title == "Frontend Dev"
        assert retrieved.company == "WebCorp"

    def test_get_by_url(self, temp_db):
        """Test getting job by URL"""
        url = "https://example.com/job/unique-url"
        job = Job(
            title="DevOps Engineer",
            company="CloudCo",
            location="Toulouse",
            url=url,
            source="glassdoor",
        )

        JobRepository.insert(job)
        retrieved = JobRepository.get_by_url(url)

        assert retrieved is not None
        assert retrieved.url == url
        assert retrieved.title == "DevOps Engineer"

    def test_exists(self, temp_db):
        """Test checking if job exists"""
        url = "https://example.com/job/exists-check"
        job = Job(
            title="Data Engineer",
            company="DataCo",
            location="Bordeaux",
            url=url,
            source="glassdoor",
        )

        assert not JobRepository.exists(url)
        JobRepository.insert(job)
        assert JobRepository.exists(url)

    def test_get_all(self, temp_db):
        """Test getting all jobs"""
        jobs = [
            Job(
                title=f"Job {i}",
                company=f"Company {i}",
                location="Paris",
                url=f"https://example.com/job/{i}",
                source="glassdoor",
            )
            for i in range(5)
        ]

        for job in jobs:
            JobRepository.insert(job)

        all_jobs = JobRepository.get_all()
        assert len(all_jobs) == 5

    def test_get_all_with_limit(self, temp_db):
        """Test getting jobs with limit"""
        for i in range(10):
            JobRepository.insert(
                Job(
                    title=f"Job {i}",
                    company="Corp",
                    location="Paris",
                    url=f"https://example.com/job/{i}",
                    source="glassdoor",
                )
            )

        limited = JobRepository.get_all(limit=5)
        assert len(limited) == 5

    def test_search_by_keyword(self, temp_db):
        """Test searching jobs by keyword"""
        jobs = [
            Job(
                title="Python Developer",
                company="Corp1",
                location="Paris",
                url="https://example.com/job/python-1",
                source="glassdoor",
                description="Python and Django",
            ),
            Job(
                title="Java Developer",
                company="Corp2",
                location="Paris",
                url="https://example.com/job/java-1",
                source="glassdoor",
                description="Java and Spring",
            ),
        ]

        for job in jobs:
            JobRepository.insert(job)

        results = JobRepository.search(keyword="Python")
        assert len(results) == 1
        assert results[0].title == "Python Developer"

    def test_count(self, temp_db):
        """Test counting jobs"""
        for i in range(7):
            JobRepository.insert(
                Job(
                    title=f"Job {i}",
                    company="Corp",
                    location="Paris",
                    url=f"https://example.com/job/count-{i}",
                    source="glassdoor",
                )
            )

        count = JobRepository.count()
        assert count == 7

    def test_update_job(self, temp_db):
        """Test updating a job"""
        job = Job(
            title="Original Title",
            company="OriginalCorp",
            location="Paris",
            url="https://example.com/job/update-test",
            source="glassdoor",
        )

        job_id = JobRepository.insert(job)
        retrieved = JobRepository.get_by_id(job_id)

        # Update fields
        retrieved.title = "Updated Title"
        retrieved.company = "UpdatedCorp"
        retrieved.salary_min = 50000

        success = JobRepository.update(retrieved)
        assert success

        # Verify update
        updated = JobRepository.get_by_id(job_id)
        assert updated.title == "Updated Title"
        assert updated.company == "UpdatedCorp"
        assert updated.salary_min == 50000

    def test_delete_job(self, temp_db):
        """Test deleting a job"""
        job = Job(
            title="To Delete",
            company="Corp",
            location="Paris",
            url="https://example.com/job/delete-test",
            source="glassdoor",
        )

        job_id = JobRepository.insert(job)
        assert JobRepository.get_by_id(job_id) is not None

        success = JobRepository.delete(job_id)
        assert success

        assert JobRepository.get_by_id(job_id) is None

    def test_insert_and_retrieve_new_fields(self, temp_db):
        """Test that new fields (is_easy_apply, job_external_id, posted_date) are saved and retrieved"""
        job = Job(
            title="Data Scientist",
            company="ML Corp",
            location="Paris",
            url="https://example.com/job/new-fields-test",
            source="glassdoor",
            is_easy_apply=True,
            job_external_id="glassdoor_123456",
            posted_date=datetime(2025, 10, 20, 10, 30, 0),
        )

        job_id = JobRepository.insert(job)
        assert job_id is not None

        # Retrieve and verify
        retrieved = JobRepository.get_by_id(job_id)
        assert retrieved is not None
        # SQLite stores booleans as integers (1/0)
        assert bool(retrieved.is_easy_apply) is True
        assert retrieved.job_external_id == "glassdoor_123456"
        assert retrieved.posted_date == datetime(2025, 10, 20, 10, 30, 0)


class TestApplicationRepository:
    """Test ApplicationRepository operations"""

    def test_insert_application(self, temp_db):
        """Test inserting an application"""
        # First create a job
        job = Job(
            title="Job for App",
            company="Corp",
            location="Paris",
            url="https://example.com/job/app-test",
            source="glassdoor",
        )
        job_id = JobRepository.insert(job)

        # Create application
        app = Application(
            job_id=job_id, status="applied", application_method="online_portal"
        )
        app_id = ApplicationRepository.insert(app)

        assert app_id is not None
        assert app_id > 0

    def test_get_by_job_id(self, temp_db):
        """Test getting application by job ID"""
        job_id = JobRepository.insert(
            Job(
                title="Job",
                company="Corp",
                location="Paris",
                url="https://example.com/job/app-get-test",
                source="glassdoor",
            )
        )

        app = Application(
            job_id=job_id,
            status="interview",
            notes="First round",
            application_method="email",
        )
        ApplicationRepository.insert(app)

        retrieved = ApplicationRepository.get_by_job_id(job_id)
        assert retrieved is not None
        assert retrieved.status == "interview"
        assert retrieved.notes == "First round"
        assert retrieved.application_method == "email"

    def test_get_by_status(self, temp_db):
        """Test getting applications by status"""
        # Create multiple jobs and applications
        for i, status in enumerate(["applied", "interview", "applied"]):
            job_id = JobRepository.insert(
                Job(
                    title=f"Job {i}",
                    company="Corp",
                    location="Paris",
                    url=f"https://example.com/job/status-{i}",
                    source="glassdoor",
                )
            )
            ApplicationRepository.insert(
                Application(
                    job_id=job_id, status=status, application_method="online_portal"
                )
            )

        applied = ApplicationRepository.get_by_status("applied")
        assert len(applied) == 2

        interview = ApplicationRepository.get_by_status("interview")
        assert len(interview) == 1

    def test_update_status(self, temp_db):
        """Test updating application status"""
        job_id = JobRepository.insert(
            Job(
                title="Job",
                company="Corp",
                location="Paris",
                url="https://example.com/job/update-status",
                source="glassdoor",
            )
        )

        ApplicationRepository.insert(
            Application(
                job_id=job_id, status="applied", application_method="online_portal"
            )
        )

        success = ApplicationRepository.update_status(
            job_id, "interview", "Scheduled for next week"
        )
        assert success

        updated = ApplicationRepository.get_by_job_id(job_id)
        assert updated is not None
        assert updated.status == "interview"
        assert updated.notes == "Scheduled for next week"


class TestScoreRepository:
    """Test ScoreRepository operations"""

    def test_insert_score(self, temp_db):
        """Test inserting a score"""
        job_id = JobRepository.insert(
            Job(
                title="Job",
                company="Corp",
                location="Paris",
                url="https://example.com/job/score-test",
                source="glassdoor",
            )
        )

        score = Score(
            job_id=job_id,
            tech_match=85.0,
            learning_opportunity=75.0,
            company_quality=70.0,
            practical_factors=80.0,
        )

        score_id = ScoreRepository.insert(score)
        assert score_id is not None

    def test_get_by_job_id(self, temp_db):
        """Test getting score by job ID"""
        job_id = JobRepository.insert(
            Job(
                title="Job",
                company="Corp",
                location="Paris",
                url="https://example.com/job/score-get",
                source="glassdoor",
            )
        )

        score = Score(job_id=job_id, tech_match=90.0, total_score=85.0)
        ScoreRepository.insert(score)

        retrieved = ScoreRepository.get_by_job_id(job_id)
        assert retrieved is not None
        assert retrieved.tech_match == 90.0

    def test_get_top_scored(self, temp_db):
        """Test getting top scored jobs"""
        # Create jobs with scores
        scores_data = [
            (95.0, "Top Job"),
            (85.0, "Good Job"),
            (60.0, "OK Job"),
            (40.0, "Low Job"),
        ]

        for total_score, title in scores_data:
            job_id = JobRepository.insert(
                Job(
                    title=title,
                    company="Corp",
                    location="Paris",
                    url=f"https://example.com/job/{title.replace(' ', '-')}",
                    source="glassdoor",
                )
            )
            ScoreRepository.insert(Score(job_id=job_id, total_score=total_score))

        # Get top 2
        top_jobs = ScoreRepository.get_top_scored(limit=2)
        assert len(top_jobs) == 2
        assert top_jobs[0][1].title == "Top Job"  # (Score, Job) tuple
        assert top_jobs[1][1].title == "Good Job"

    def test_update_score(self, temp_db):
        """Test updating a score"""
        job_id = JobRepository.insert(
            Job(
                title="Job",
                company="Corp",
                location="Paris",
                url="https://example.com/job/score-update",
                source="glassdoor",
            )
        )

        score = Score(job_id=job_id, tech_match=70.0)
        ScoreRepository.insert(score)

        # Update score
        updated_score = ScoreRepository.get_by_job_id(job_id)
        updated_score.tech_match = 85.0
        updated_score.calculate_total()

        ScoreRepository.update(updated_score)

        # Verify
        final = ScoreRepository.get_by_job_id(job_id)
        assert final.tech_match == 85.0
