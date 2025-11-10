"""
Shared pytest fixtures for all tests

This file contains fixtures used across multiple test files.
Put component-specific fixtures in the test files themselves.
"""

import os
import tempfile
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# ============================================================================
# FIXTURE PATHS
# ============================================================================


@pytest.fixture(scope="session")
def fixtures_dir():
    """Path to test fixtures directory"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def job_search_page_fixture(fixtures_dir):
    """Get file:// URL for the saved HTML fixture"""
    html_path = fixtures_dir / "glassdoor_job_search_page.html"
    if not html_path.exists():
        pytest.skip(f"Test fixture not found: {html_path}")
    return f"file://{html_path.absolute()}"


# ============================================================================
# SELENIUM FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def chrome_driver():
    """
    Create a real Chrome WebDriver for integration tests (session-scoped for speed).

    Used by: integration/test_scraper_extraction.py
    """
    options = Options()
    options.add_argument("--headless")  # Run without GUI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")

    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest.fixture
def temp_db():
    """
    Create a temporary database for integration tests.

    Automatically cleans up after test completion.
    Used by: integration/test_repositories.py, integration/test_session_tracking.py
    """
    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Monkey patch the DB_PATH
        import joblass.db.engine as engine_module
        from sqlalchemy import create_engine
        from sqlmodel import SQLModel

        original_path = engine_module.DB_PATH
        original_engine = engine_module.engine

        engine_module.DB_PATH = db_path
        engine_module.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

        # Initialize database
        SQLModel.metadata.create_all(engine_module.engine)

        yield db_path

        # Cleanup and restore
        engine_module.engine.dispose()
        engine_module.DB_PATH = original_path
        engine_module.engine = original_engine


@pytest.fixture
def temp_db_for_e2e():
    """
    Create a temporary database for e2e workflow tests.

    Similar to temp_db but with different cleanup strategy for workflow tests.
    Used by: e2e/test_workflow_complete.py
    """
    test_db = Path(tempfile.mkdtemp()) / "test_joblass.db"

    import joblass.db.engine as engine_module
    from sqlalchemy import create_engine

    original_db_path = engine_module.DB_PATH
    original_db_dir = engine_module.DB_DIR
    original_engine = engine_module.engine

    engine_module.DB_PATH = test_db
    engine_module.DB_DIR = test_db.parent

    # Dispose old engine and create new one
    engine_module.engine.dispose()
    engine_module.engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Initialize test database
    from joblass.db import init_db

    init_db()

    yield test_db

    # Cleanup
    engine_module.engine.dispose()
    engine_module.DB_PATH = original_db_path
    engine_module.DB_DIR = original_db_dir
    engine_module.engine = original_engine

    if test_db.exists():
        os.remove(test_db)
    if test_db.parent.exists():
        os.rmdir(test_db.parent)
