"""
Integration tests for database repositories (CRUD operations)

Tests CRUD operations with a real SQLite database.
Uses temp_db fixture from conftest.py for automatic cleanup.

Run with: pytest tests/integration/test_repositories.py -v
"""

from datetime import datetime

from pydantic import ValidationError

from joblass.db import (
    Application,
    ApplicationRepository,
    Company,
    CompanyRepository,
    Job,
    JobRepository,
    Score,
    ScoreRepository,
)


class TestCompanyRepository:
    """Test CompanyRepository operations"""

    def test_insert_company(self, temp_db):
        """Test inserting a company via upsert"""
        company = Company(
            name="DataCorp",
            page_source="job_posting",
            source="glassdoor",
            overview={"size": "100-500", "industry": "Data Science"},
        )

        company_id = CompanyRepository.upsert(company)
        assert company_id is not None
        assert company_id > 0

    def test_get_by_id(self, temp_db):
        """Test getting company by ID"""
        company = Company(
            name="MLStartup",
            page_source="company_profile",
            source="glassdoor",
        )

        company_id = CompanyRepository.upsert(company)
        retrieved = CompanyRepository.get_by_id(company_id)

        assert retrieved is not None
        assert retrieved.id == company_id
        assert retrieved.name == "MLStartup"

    def test_get_by_name(self, temp_db):
        """Test getting company by name (case-insensitive)"""
        company = Company(
            name="TechGiant Inc",
            page_source="job_posting",
        )

        CompanyRepository.upsert(company)

        # Case-insensitive search
        result1 = CompanyRepository.get_by_name("TechGiant Inc")
        result2 = CompanyRepository.get_by_name("techgiant inc")
        result3 = CompanyRepository.get_by_name("TECHGIANT INC")

        assert result1 is not None
        assert result2 is not None
        assert result3 is not None
        assert result1.name == result2.name == result3.name == "TechGiant Inc"

    def test_upsert_creates_new_company(self, temp_db):
        """Test upsert creates company when it doesn't exist"""
        company = Company(
            name="NewCompany",
            page_source="job_posting",
            overview={"size": "1-50", "industry": "Startup"},
        )

        company_id = CompanyRepository.upsert(company)

        assert company_id is not None
        retrieved = CompanyRepository.get_by_id(company_id)
        assert retrieved.name == "NewCompany"
        assert retrieved.page_source == "job_posting"

    def test_upsert_merges_job_posting_then_company_profile(self, temp_db):
        """Test upsert merges job_posting data with company_profile data"""
        # First insert from job posting (partial data)
        job_posting_company = Company(
            name="Acme Corp",
            page_source="job_posting",
            overview={"size": "500-1000"},
        )

        company_id_1 = CompanyRepository.upsert(job_posting_company)

        # Then scrape full company profile
        company_profile_company = Company(
            name="Acme Corp",  # Same name
            page_source="company_profile",
            profile_url="https://glassdoor.com/acme",
            overview={"size": "500-1000", "industry": "Technology", "founded": "2005"},
            evaluations={"global_rating": 4.5, "reviews_count": 200},
        )

        company_id_2 = CompanyRepository.upsert(company_profile_company)

        # Should be same company
        assert company_id_1 == company_id_2

        # Retrieve and verify merged data
        merged = CompanyRepository.get_by_id(company_id_1)

        assert merged.page_source == "merged"
        assert merged.overview["size"] == "500-1000"
        assert merged.overview["industry"] == "Technology"
        assert merged.evaluations["global_rating"] == 4.5
        assert merged.profile_url == "https://glassdoor.com/acme"

    def test_upsert_respects_company_profile_priority(self, temp_db):
        """Test that company_profile data takes priority in merges"""
        # First: Company profile with full data
        profile_company = Company(
            name="GlobalTech",
            page_source="company_profile",
            overview={"size": "10000+", "industry": "Software"},
            evaluations={"global_rating": 4.0},
        )

        company_id_1 = CompanyRepository.upsert(profile_company)

        # Second: Job posting with less data
        job_posting_company = Company(
            name="GlobalTech",
            page_source="job_posting",
            overview={"size": "5000-10000"},  # Different size
        )

        company_id_2 = CompanyRepository.upsert(job_posting_company)

        assert company_id_1 == company_id_2

        # Retrieve and verify profile data wasn't overwritten
        merged = CompanyRepository.get_by_id(company_id_1)

        # Page source should stay "company_profile" (not downgraded)
        # This tests the merge logic priority
        assert merged.page_source == "company_profile"
        assert merged.overview["size"] == "10000+"  # Original profile data preserved
        assert merged.evaluations["global_rating"] == 4.0

    def test_upsert_handles_duplicate_names_case_insensitive(self, temp_db):
        """Test upsert with case-insensitive name matching"""
        company1 = Company(
            name="StartupXYZ",
            page_source="job_posting",
        )

        company2 = Company(
            name="startupxyz",  # Different case
            page_source="company_profile",
            profile_url="https://glassdoor.com/startupxyz",
        )

        id1 = CompanyRepository.upsert(company1)
        id2 = CompanyRepository.upsert(company2)

        # Should match and merge
        assert id1 == id2

        # Verify only one company exists
        retrieved = CompanyRepository.get_by_id(id1)
        assert retrieved.profile_url == "https://glassdoor.com/startupxyz"


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
        """Test that inserting duplicate URL fails"""
        # Create two jobs with SAME URL - should detect as duplicate
        job1 = Job(
            title="Developer",
            company="Corp1",
            location="Paris",
            url="https://example.com/job/url-1",  # Same URL
            source="glassdoor",
        )

        job2 = Job(
            title="Developer2",  # Different title
            company="Corp2",  # Different company
            location="London",  # Different location
            url="https://example.com/job/url-1",  # Same URL - should fail
            source="glassdoor",
        )

        job_id_1 = JobRepository.insert(job1)
        job_id_2 = JobRepository.insert(job2)

        assert job_id_1 is not None
        assert job_id_2 is None  # Should fail due to duplicate URL

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
        retrieved.salary_estimate = {"min": 50000, "currency": "EUR"}

        success = JobRepository.update(retrieved)
        assert success

        # Verify update
        updated = JobRepository.get_by_id(job_id)
        assert updated.title == "Updated Title"
        assert updated.company == "UpdatedCorp"
        assert updated.salary_min == 50000  # Access via property

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
            tech_stack=[
                "Python",
                "scikit-learn",
                "pandas",
            ],  # Direct list, not JSON string
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
        assert retrieved.tech_stack == ["Python", "scikit-learn", "pandas"]


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
