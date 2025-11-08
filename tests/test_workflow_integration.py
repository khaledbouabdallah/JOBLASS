"""
Workflow Integration Tests - End-to-end user journey testing

Tests the complete workflow: search → scrape → save → session tracking
Uses mocked scraper to avoid actual browser automation.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from joblass.db import (
    JobRepository,
    SearchSessionRepository,
    init_db,
)
from joblass.db.models import ScrapedJobData
from joblass.workflows import JobSearchWorkflow


def setup_test_db():
    """Setup test database in temporary directory"""
    test_db = Path(tempfile.mkdtemp()) / "test_joblass.db"

    # Temporarily override DB_PATH
    import joblass.db.connection as conn_module

    original_db_path = conn_module.DB_PATH
    original_db_dir = conn_module.DB_DIR

    conn_module.DB_PATH = test_db
    conn_module.DB_DIR = test_db.parent

    # Initialize test database
    init_db()

    return test_db, original_db_path, original_db_dir


def teardown_test_db(test_db, original_db_path, original_db_dir):
    """Cleanup test database"""
    import joblass.db.connection as conn_module

    # Restore original paths
    conn_module.DB_PATH = original_db_path
    conn_module.DB_DIR = original_db_dir

    # Remove test database
    if test_db.exists():
        os.remove(test_db)
    if test_db.parent.exists():
        os.rmdir(test_db.parent)


class MockGlassdoorScraper:
    """Mock scraper that returns fake job data without browser automation"""

    def __init__(self, driver):
        self.driver = driver
        self.jobs_to_return = []

    def navigate_to_home(self):
        """Mock navigation"""
        pass

    def fill_search_form(self, job_title, location, preferred_location=None):
        """Mock search form - returns mocked job count"""
        return 100  # Simulate finding 100 jobs

    def search_jobs(self, jobs_found, max_jobs=None, skip_until=None):
        """Mock job scraping - returns fake ScrapedJobData"""
        return self.jobs_to_return

    def save_job_from_validated_data(self, validated_data, session_id=None):
        """Mock job saving - calls real repository"""
        from joblass.db import Job

        # Check if job already exists
        if JobRepository.exists(validated_data.url):
            return None

        # Create Job from validated data
        db_dict = validated_data.to_db_dict()
        job = Job(
            title=db_dict["title"],
            company=db_dict["company"],
            location=db_dict["location"],
            url=db_dict["url"],
            source=db_dict["source"],
            description=db_dict["description"],
            scraped_date=db_dict["scraped_date"],
            session_id=session_id,
        )

        return JobRepository.insert(job)


class MockExtraFilters:
    """Mock filter handler"""

    def __init__(self, driver):
        self.driver = driver
        self.accordions_choice_options = {
            "company_rating": ["+1", "+2", "+3", "+4"],
            "date_posted": ["24 heures", "3 jours", "7 jours", "14 jours"],
            "job_type": ["Temps plein", "Temps partiel", "Stage"],
        }

    def _close_dropdown(self):
        pass

    def _open_dropdown(self):
        pass

    def apply_filters(self, filters):
        pass

    def validate_and_close(self):
        pass


def create_mock_jobs(count=5):
    """Create list of mock ScrapedJobData instances"""
    return [
        ScrapedJobData(
            job_title=f"Software Engineer {i}",
            company=f"TechCorp {i}",
            location="Paris",
            url=f"https://example.com/job/{i}",
        )
        for i in range(count)
    ]


def test_workflow_creates_and_tracks_session():
    """Verify complete session lifecycle from start to finish"""
    test_db, orig_path, orig_dir = setup_test_db()

    try:
        # Create mock driver
        mock_driver = Mock()

        # Create workflow with mocked scraper
        with (
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.GlassdoorScraper",
                MockGlassdoorScraper,
            ),
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.ExtraFilters",
                MockExtraFilters,
            ),
        ):

            workflow = JobSearchWorkflow(mock_driver)

            # Configure mock scraper to return 5 jobs
            workflow.scraper.jobs_to_return = create_mock_jobs(5)

            # Run workflow
            stats = workflow.run(
                job_title="Software Engineer",
                location="Paris",
                preferred_location="Île-de-France",
                max_jobs=10,
            )

            # Verify session was created and returned
            assert stats["session_id"] is not None, "Session ID should be returned"
            assert stats["session_id"] > 0, "Session ID should be positive"

            # Verify statistics
            assert stats["jobs_found"] == 100, "Should find 100 jobs (mocked)"
            assert stats["jobs_scraped"] == 5, "Should scrape 5 jobs"
            assert stats["jobs_saved"] == 5, "Should save 5 jobs (no duplicates)"
            assert stats["jobs_skipped"] == 0, "Should skip 0 jobs (no duplicates)"

            # Retrieve session from database
            session = SearchSessionRepository.get_by_id(stats["session_id"])

            assert session is not None, "Session should exist in database"
            assert session.status == "completed", "Session should be marked completed"
            assert session.jobs_found == 100
            assert session.jobs_scraped == 5
            assert session.jobs_saved == 5
            assert session.jobs_skipped == 0
            assert session.error_message is None

            # Verify search criteria stored correctly
            assert session.search_criteria.job_title == "Software Engineer"
            assert session.search_criteria.location == "Paris"
            assert session.search_criteria.preferred_location == "Île-de-France"

            print("✓ Session created and tracked correctly")

    finally:
        teardown_test_db(test_db, orig_path, orig_dir)


def test_workflow_links_jobs_to_session():
    """Verify all scraped jobs have correct session_id foreign key"""
    test_db, orig_path, orig_dir = setup_test_db()

    try:
        mock_driver = Mock()

        with (
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.GlassdoorScraper",
                MockGlassdoorScraper,
            ),
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.ExtraFilters",
                MockExtraFilters,
            ),
        ):

            workflow = JobSearchWorkflow(mock_driver)
            workflow.scraper.jobs_to_return = create_mock_jobs(3)

            stats = workflow.run(
                job_title="Data Scientist", location="Lyon", max_jobs=5
            )

            session_id = stats["session_id"]

            # Retrieve all jobs from this session
            jobs = SearchSessionRepository.get_jobs_by_session(session_id)

            assert len(jobs) == 3, "Should have 3 jobs linked to session"

            # Verify all jobs have correct session_id
            for job in jobs:
                assert (
                    job.session_id == session_id
                ), f"Job {job.id} should have session_id={session_id}"

            # Verify job details
            assert any(
                "Software Engineer 0" in job.title for job in jobs
            ), "Should have first job"
            assert any(
                "TechCorp 1" in job.company for job in jobs
            ), "Should have second job"

            print("✓ All jobs correctly linked to session")

    finally:
        teardown_test_db(test_db, orig_path, orig_dir)


def test_workflow_handles_duplicates():
    """Verify workflow correctly tracks duplicate jobs in session stats"""
    test_db, orig_path, orig_dir = setup_test_db()

    try:
        mock_driver = Mock()

        with (
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.GlassdoorScraper",
                MockGlassdoorScraper,
            ),
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.ExtraFilters",
                MockExtraFilters,
            ),
        ):

            # First workflow run - insert 3 jobs
            workflow1 = JobSearchWorkflow(mock_driver)
            workflow1.scraper.jobs_to_return = create_mock_jobs(3)

            stats1 = workflow1.run(job_title="Engineer", location="Paris", max_jobs=5)

            assert stats1["jobs_saved"] == 3
            assert stats1["jobs_skipped"] == 0

            # Second workflow run - same 3 jobs + 2 new ones
            workflow2 = JobSearchWorkflow(mock_driver)
            workflow2.scraper.jobs_to_return = create_mock_jobs(3) + [
                ScrapedJobData(
                    job_title="New Job 1",
                    company="NewCorp 1",
                    location="Paris",
                    url="https://example.com/job/new1",
                ),
                ScrapedJobData(
                    job_title="New Job 2",
                    company="NewCorp 2",
                    location="Paris",
                    url="https://example.com/job/new2",
                ),
            ]

            stats2 = workflow2.run(job_title="Engineer", location="Paris", max_jobs=10)

            # Verify duplicate tracking
            assert stats2["jobs_scraped"] == 5, "Should scrape 5 jobs total"
            assert stats2["jobs_saved"] == 2, "Should save only 2 new jobs"
            assert stats2["jobs_skipped"] == 3, "Should skip 3 duplicate jobs"

            # Verify session stats updated correctly
            session2 = SearchSessionRepository.get_by_id(stats2["session_id"])
            assert session2.jobs_saved == 2
            assert session2.jobs_skipped == 3

            # Verify total jobs in database
            total_jobs = JobRepository.count()
            assert (
                total_jobs == 5
            ), "Should have 5 total jobs (3 from run1, 2 from run2)"

            print("✓ Duplicates handled correctly")

    finally:
        teardown_test_db(test_db, orig_path, orig_dir)


def test_workflow_marks_session_failed_on_error():
    """Verify error handling updates session status to failed"""
    test_db, orig_path, orig_dir = setup_test_db()

    try:
        mock_driver = Mock()

        # Create a mock scraper that raises an exception
        class FailingScraper(MockGlassdoorScraper):
            def search_jobs(self, **kwargs):
                raise Exception("Network timeout after 30 seconds")

        with (
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.GlassdoorScraper",
                FailingScraper,
            ),
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.ExtraFilters",
                MockExtraFilters,
            ),
        ):

            workflow = JobSearchWorkflow(mock_driver)

            stats = workflow.run(job_title="DevOps Engineer", location="Toulouse")

            # Workflow should return stats even on failure
            assert stats["session_id"] is not None, "Session should be created"
            assert stats["jobs_scraped"] == 0, "No jobs scraped due to error"
            assert stats["jobs_saved"] == 0, "No jobs saved due to error"

            # Retrieve session and verify it's marked as failed
            session = SearchSessionRepository.get_by_id(stats["session_id"])

            assert session.status == "failed", "Session should be marked as failed"
            assert session.error_message is not None, "Error message should be recorded"
            assert "Network timeout" in session.error_message

            print("✓ Session marked as failed on error")

    finally:
        teardown_test_db(test_db, orig_path, orig_dir)


def test_workflow_handles_no_jobs_found():
    """Verify session completed successfully even when no jobs found"""
    test_db, orig_path, orig_dir = setup_test_db()

    try:
        mock_driver = Mock()

        # Mock scraper that returns 0 jobs found
        class NoJobsScraper(MockGlassdoorScraper):
            def fill_search_form(self, *args, **kwargs):
                return 0  # No jobs found

        with (
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.GlassdoorScraper",
                NoJobsScraper,
            ),
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.ExtraFilters",
                MockExtraFilters,
            ),
        ):

            workflow = JobSearchWorkflow(mock_driver)

            stats = workflow.run(
                job_title="Unicorn Engineer", location="Middle of Nowhere"
            )

            assert stats["jobs_found"] == 0
            assert stats["jobs_scraped"] == 0
            assert stats["jobs_saved"] == 0
            assert stats["jobs_skipped"] == 0

            # Session should still be created and marked completed
            session = SearchSessionRepository.get_by_id(stats["session_id"])

            assert session.status == "completed", "Session should be completed"
            assert session.jobs_found == 0
            assert session.error_message is None

            print("✓ No jobs found handled correctly")

    finally:
        teardown_test_db(test_db, orig_path, orig_dir)


def test_workflow_with_advanced_filters():
    """Verify workflow correctly stores advanced filters in session"""
    test_db, orig_path, orig_dir = setup_test_db()

    try:
        mock_driver = Mock()

        with (
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.GlassdoorScraper",
                MockGlassdoorScraper,
            ),
            patch(
                "joblass.workflows.search_job_glassdoor_workflow.ExtraFilters",
                MockExtraFilters,
            ),
        ):

            workflow = JobSearchWorkflow(mock_driver)
            workflow.scraper.jobs_to_return = create_mock_jobs(2)

            # Run with advanced filters
            stats = workflow.run(
                job_title="ML Engineer",
                location="Nice",
                max_jobs=5,
                advanced_filters={
                    "is_easy_apply": True,
                    "date_posted": "7 jours",
                    "job_type": "Stage",
                    "salary_range": (30000, 50000),
                },
            )

            # Retrieve session and verify filters stored
            session = SearchSessionRepository.get_by_id(stats["session_id"])

            assert session.search_criteria.is_easy_apply is True
            assert session.search_criteria.date_posted == "7 jours"
            assert session.search_criteria.job_type == "Stage"

            # Verify filters can be converted back to dict format
            filters_dict = session.search_criteria.to_filters_dict()
            assert filters_dict["is_easy_apply"] is True
            assert filters_dict["date_posted"] == "7 jours"

            print("✓ Advanced filters stored correctly in session")

    finally:
        teardown_test_db(test_db, orig_path, orig_dir)


if __name__ == "__main__":
    print("=" * 70)
    print("WORKFLOW INTEGRATION TESTS")
    print("=" * 70)

    test_workflow_creates_and_tracks_session()
    print()

    test_workflow_links_jobs_to_session()
    print()

    test_workflow_handles_duplicates()
    print()

    test_workflow_marks_session_failed_on_error()
    print()

    test_workflow_handles_no_jobs_found()
    print()

    test_workflow_with_advanced_filters()
    print()

    print("=" * 70)
    print("✅ ALL WORKFLOW INTEGRATION TESTS PASSED!")
    print("=" * 70)
