"""
Tests for SearchSession and SearchSessionRepository
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

from joblass.db import (
    Job,
    JobRepository,
    SearchCriteria,
    SearchSession,
    SearchSessionRepository,
)


def setup_test_db():
    """Setup test database in temporary directory"""
    # Use a temporary database for tests
    test_db = Path(tempfile.mkdtemp()) / "test_joblass.db"

    # Temporarily override DB_PATH
    import joblass.db.engine as engine_module
    from sqlalchemy import create_engine
    from sqlmodel import SQLModel

    original_path = engine_module.DB_PATH
    original_engine = engine_module.engine

    engine_module.DB_PATH = test_db
    engine_module.engine = create_engine(
        f"sqlite:///{test_db}", connect_args={"check_same_thread": False}, echo=False
    )

    # Initialize database
    SQLModel.metadata.create_all(engine_module.engine)

    return test_db, (original_path, original_engine), engine_module


def teardown_test_db(test_db, originals, engine_module):
    """Cleanup test database"""
    original_path, original_engine = originals

    # Cleanup engine
    engine_module.engine.dispose()

    # Restore original path and engine
    engine_module.DB_PATH = original_path
    engine_module.engine = original_engine

    # Remove test database
    if test_db.exists():
        os.remove(test_db)
    if test_db.parent.exists():
        os.rmdir(test_db.parent)


def test_search_criteria_creation():
    """Test creating SearchCriteria"""
    criteria = SearchCriteria(
        job_title="ML Engineer",
        location="Paris",
        preferred_location="Île-de-France",
        is_easy_apply=True,
        date_posted="7 jours",
        job_type="Stage",
        salary_min=30000,
        salary_max=50000,
    )

    assert criteria.job_title == "ML Engineer"
    assert criteria.location == "Paris"
    assert criteria.is_easy_apply is True
    assert criteria.salary_min == 30000

    # Test Pydantic's built-in JSON serialization
    json_str = criteria.model_dump_json(exclude_none=True)
    assert (
        '"job_title":"ML Engineer"' in json_str
        or '"job_title": "ML Engineer"' in json_str
    )

    # Test deserialization
    criteria2 = SearchCriteria.model_validate_json(json_str)
    assert criteria2.job_title == criteria.job_title
    assert criteria2.salary_min == criteria.salary_min


def test_search_criteria_to_filters_dict():
    """Test converting SearchCriteria to filters dict"""
    criteria = SearchCriteria(
        job_title="Data Scientist",
        location="Lyon",
        is_easy_apply=True,
        is_remote=True,
        salary_min=40000,
        salary_max=60000,
        date_posted="7 jours",
        job_type="CDI",
    )

    filters = criteria.to_filters_dict()

    assert filters["is_easy_apply"] is True
    assert filters["is_remote"] is True
    assert filters["salary_range"] == (40000, 60000)
    assert filters["date_posted"] == "7 jours"
    assert filters["job_type"] == "CDI"

    # Basic search fields should not be in filters
    assert "job_title" not in filters
    assert "location" not in filters


def test_search_session_creation():
    """Test creating SearchSession"""
    criteria = SearchCriteria(job_title="ML Engineer", location="Paris")

    session = SearchSession(
        search_criteria=criteria.model_dump(),
        source="glassdoor",
        status="in_progress",
        jobs_found=100,
    )

    assert session.search_criteria["job_title"] == "ML Engineer"
    assert session.source == "glassdoor"
    assert session.status == "in_progress"
    assert session.jobs_found == 100
    assert session.jobs_scraped == 0
    assert session.jobs_saved == 0
    assert session.jobs_skipped == 0


def test_search_session_mark_completed():
    """Test marking session as completed"""
    criteria = SearchCriteria(job_title="Data Analyst", location="Marseille")
    session = SearchSession(search_criteria=criteria.model_dump(), jobs_found=50)

    session.mark_completed(jobs_scraped=45, jobs_saved=40, jobs_skipped=5)

    assert session.status == "completed"
    assert session.jobs_scraped == 45
    assert session.jobs_saved == 40
    assert session.jobs_skipped == 5
    assert isinstance(session.updated_at, datetime)


def test_search_session_mark_failed():
    """Test marking session as failed"""
    criteria = SearchCriteria(job_title="DevOps Engineer", location="Toulouse")
    session = SearchSession(search_criteria=criteria.model_dump())

    error_msg = "Network timeout after 30 seconds"
    session.mark_failed(error_msg)

    assert session.status == "failed"
    assert session.error_message == error_msg
    assert isinstance(session.updated_at, datetime)


def test_search_session_repository_insert():
    """Test inserting search session into database"""
    test_db, originals, engine_module = setup_test_db()

    try:
        criteria = SearchCriteria(
            job_title="Backend Developer", location="Bordeaux", is_easy_apply=True
        )
        # SearchSession stores search_criteria as Dict - pass the model directly,
        # repository will convert it automatically
        session = SearchSession(
            search_criteria=criteria,
            source="glassdoor",
            jobs_found=75,
        )

        session_id = SearchSessionRepository.insert(session)

        assert session_id is not None
        assert session_id > 0

        # Retrieve and verify - search_criteria is stored as dict
        retrieved = SearchSessionRepository.get_by_id(session_id)
        assert retrieved is not None
        assert retrieved.id == session_id
        assert isinstance(retrieved.search_criteria, dict)
        assert retrieved.search_criteria["job_title"] == "Backend Developer"
        assert retrieved.jobs_found == 75
        assert retrieved.status == "in_progress"

    finally:
        teardown_test_db(test_db, originals, engine_module)


def test_search_session_repository_update():
    """Test updating search session"""
    test_db, originals, engine_module = setup_test_db()

    try:
        # Create session
        criteria = SearchCriteria(job_title="Frontend Developer", location="Nice")
        session = SearchSession(search_criteria=criteria.model_dump(), jobs_found=60)

        session_id = SearchSessionRepository.insert(session)
        session.id = session_id

        # Update session
        session.mark_completed(jobs_scraped=55, jobs_saved=50, jobs_skipped=5)
        success = SearchSessionRepository.update(session)

        assert success is True

        # Retrieve and verify
        retrieved = SearchSessionRepository.get_by_id(session_id)
        assert retrieved.status == "completed"
        assert retrieved.jobs_scraped == 55
        assert retrieved.jobs_saved == 50
        assert retrieved.jobs_skipped == 5

    finally:
        teardown_test_db(test_db, originals, engine_module)


def test_search_session_repository_get_all():
    """Test retrieving all sessions"""
    test_db, originals, engine_module = setup_test_db()

    try:
        # Create multiple sessions
        for i, job_title in enumerate(["Data Scientist", "ML Engineer", "DevOps"]):
            criteria = SearchCriteria(job_title=job_title, location="Paris")
            session = SearchSession(
                search_criteria=criteria.model_dump(), jobs_found=i * 10
            )
            SearchSessionRepository.insert(session)

        # Get all sessions
        all_sessions = SearchSessionRepository.get_all()
        assert len(all_sessions) == 3

        # Get with limit
        limited = SearchSessionRepository.get_all(limit=2)
        assert len(limited) == 2

        # Get by status
        completed_sessions = SearchSessionRepository.get_all(status="completed")
        assert len(completed_sessions) == 0  # All are in_progress

    finally:
        teardown_test_db(test_db, originals, engine_module)


def test_job_session_foreign_key():
    """Test jobs linked to search session"""
    test_db, originals, engine_module = setup_test_db()

    try:
        # Create search session
        criteria = SearchCriteria(job_title="Python Developer", location="Lille")
        session = SearchSession(search_criteria=criteria.model_dump(), jobs_found=30)
        session_id = SearchSessionRepository.insert(session)

        # Create jobs linked to session
        for i in range(3):
            job = Job(
                title=f"Python Developer {i}",
                company=f"Company {i}",
                location="Lille",
                url=f"https://example.com/job/{i}",
                source="glassdoor",
                session_id=session_id,
            )
            JobRepository.insert(job)

        # Retrieve jobs by session
        jobs = SearchSessionRepository.get_jobs_by_session(session_id)
        assert len(jobs) == 3
        assert all(job.session_id == session_id for job in jobs)
        assert all(job.company.startswith("Company") for job in jobs)

    finally:
        teardown_test_db(test_db, originals, engine_module)


def test_session_count():
    """Test counting sessions"""
    test_db, originals, engine_module = setup_test_db()

    try:
        # Create sessions with different statuses
        criteria1 = SearchCriteria(job_title="Job1", location="City1")
        session1 = SearchSession(search_criteria=criteria1.model_dump())
        session1_id = SearchSessionRepository.insert(session1)

        criteria2 = SearchCriteria(job_title="Job2", location="City2")
        session2 = SearchSession(search_criteria=criteria2.model_dump())
        session2_id = SearchSessionRepository.insert(session2)
        session2.id = session2_id
        session2.mark_completed(10, 8, 2)
        SearchSessionRepository.update(session2)

        # Count all
        total = SearchSessionRepository.count()
        assert total == 2

        # Count by status
        in_progress = SearchSessionRepository.count(status="in_progress")
        completed = SearchSessionRepository.count(status="completed")
        assert in_progress == 1
        assert completed == 1

    finally:
        teardown_test_db(test_db, originals, engine_module)


if __name__ == "__main__":
    print("Running SearchSession tests...")

    test_search_criteria_creation()
    print("✓ test_search_criteria_creation passed")

    test_search_criteria_to_filters_dict()
    print("✓ test_search_criteria_to_filters_dict passed")

    test_search_session_creation()
    print("✓ test_search_session_creation passed")

    test_search_session_mark_completed()
    print("✓ test_search_session_mark_completed passed")

    test_search_session_mark_failed()
    print("✓ test_search_session_mark_failed passed")

    test_search_session_repository_insert()
    print("✓ test_search_session_repository_insert passed")

    test_search_session_repository_update()
    print("✓ test_search_session_repository_update passed")

    test_search_session_repository_get_all()
    print("✓ test_search_session_repository_get_all passed")

    test_job_session_foreign_key()
    print("✓ test_job_session_foreign_key passed")

    test_session_count()
    print("✓ test_session_count passed")

    print("\n✅ All tests passed!")
