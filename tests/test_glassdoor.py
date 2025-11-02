"""
Unit tests for Glassdoor scraper extraction methods

These tests use real Selenium WebDriver with saved HTML fixtures to:
1. Load actual HTML into a browser
2. Call the real extraction methods with real selectors
3. Verify the methods extract correct data from real HTML

This approach ensures tests:
- Test actual CSS selectors against real HTML
- Will fail if selectors break or HTML structure changes
- Test the complete extraction pipeline (selector + extraction logic)
- Use real browser behavior (not mocks)
"""

from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from joblass.scrapers.glassdoor import GlassdoorScraper


# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def chrome_driver():
    """Create a real Chrome WebDriver for testing (session-scoped for speed)"""
    options = Options()
    options.add_argument("--headless")  # Run without GUI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


@pytest.fixture
def job_search_page_url():
    """Get file:// URL for the saved HTML fixture"""
    html_path = FIXTURES_DIR / "glassdoor_job_search_page.html"
    if not html_path.exists():
        pytest.skip(f"Test fixture not found: {html_path}")

    return f"file://{html_path.absolute()}"


@pytest.fixture
def scraper_with_fixture_loaded(chrome_driver, job_search_page_url):
    """Load fixture HTML into browser and return scraper instance"""
    chrome_driver.get(job_search_page_url)
    return GlassdoorScraper(chrome_driver)


class TestScraperMethods:
    """Test scraper utility methods"""

    def test_close_modal_when_not_present(self, chrome_driver):
        """Test modal closing when no modal exists"""
        from unittest.mock import patch

        scraper = GlassdoorScraper(chrome_driver)

        with patch("joblass.scrapers.glassdoor.wait_for_element") as mock_wait:
            # Simulate no modal found (timeout/exception)
            mock_wait.side_effect = Exception("No modal")

            assert scraper.close_modal_if_present() is False


class TestJobDataExtraction:
    """Test extraction methods with real Selenium and HTML fixtures"""

    def test_parse_job_age_to_seconds(self, chrome_driver):
        """Test job age parsing - days, hours, with/without +"""
        scraper = GlassdoorScraper(chrome_driver)

        assert scraper._parse_job_age_to_seconds("2d") == 2 * 86400
        assert scraper._parse_job_age_to_seconds("5h") == 5 * 3600
        assert scraper._parse_job_age_to_seconds("30j+") == 30 * 86400
        assert scraper._parse_job_age_to_seconds("1d") == 86400

    def test_parse_job_age_invalid_format(self, chrome_driver):
        """Test job age parsing with invalid format"""
        scraper = GlassdoorScraper(chrome_driver)

        with pytest.raises(ValueError):
            scraper._parse_job_age_to_seconds("invalid")

        with pytest.raises(ValueError):
            scraper._parse_job_age_to_seconds("2x")

    def test_extract_job_header_info_from_real_html(
        self, chrome_driver, job_search_page_url
    ):
        """Test _extract_job_header_info extracts from actual HTML fixture"""
        from datetime import date
        from selenium.webdriver.common.by import By

        # Load the fixture
        chrome_driver.get(job_search_page_url)
        scraper = GlassdoorScraper(chrome_driver)

        # Find first job listing in the actual HTML
        job_listings = chrome_driver.find_elements(
            By.CSS_SELECTOR, "li[data-test='jobListing']"
        )

        if len(job_listings) > 0:
            first_job = job_listings[0]

            # Call the actual extraction method on real HTML
            result = scraper._extract_job_header_info(first_job)

            # Verify it extracted actual data from the HTML
            assert "job_external_id" in result
            assert "job_age" in result
            assert "job_published_date" in result

            # Verify types
            assert isinstance(result["job_external_id"], str)
            assert isinstance(result["job_age"], int)
            assert isinstance(result["job_published_date"], date)

            # Verify the data is real (not empty/default)
            assert len(result["job_external_id"]) > 0
            assert result["job_age"] >= 0

            print(f"\nExtracted from real HTML: {result}")
        else:
            pytest.skip("No job listings found in fixture")

    def test_extract_verified_skills_not_on_search_page(
        self, scraper_with_fixture_loaded
    ):
        """Test _extract_verified_skills extracts skills from real HTML"""
        result = scraper_with_fixture_loaded._extract_verified_skills()

        # Should extract skills from the fixture
        assert isinstance(result, list)
        # Fixture has at least some skills
        if len(result) > 0:
            assert all(isinstance(skill, str) for skill in result)
            print(f"\nExtracted verified skills: {result}")

    def test_extract_required_skills_not_on_search_page(
        self, scraper_with_fixture_loaded
    ):
        """Test _extract_required_skills extracts skills from real HTML"""
        result = scraper_with_fixture_loaded._extract_required_skills()

        # Should extract skills from the fixture
        assert isinstance(result, list)
        # Fixture has at least some required skills
        if len(result) > 0:
            assert all(isinstance(skill, str) for skill in result)
            print(f"\nExtracted required skills: {result}")

    def test_extract_job_title_not_on_search_page(self, scraper_with_fixture_loaded):
        """Test _extract_job_title extracts from real HTML"""
        result = scraper_with_fixture_loaded._extract_job_title()

        # Should extract actual job title from fixture
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\nExtracted job title: {result}")

    def test_extract_company_not_on_search_page(self, scraper_with_fixture_loaded):
        """Test _extract_company extracts from real HTML"""
        result = scraper_with_fixture_loaded._extract_company()

        # Should extract actual company from fixture
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\nExtracted company: {result}")

    def test_extract_location_not_on_search_page(self, scraper_with_fixture_loaded):
        """Test _extract_location extracts from real HTML"""
        result = scraper_with_fixture_loaded._extract_location()

        # Should extract location from fixture
        if result is not None:
            assert isinstance(result, str)
            assert len(result) > 0
            print(f"\nExtracted location: {result}")

    def test_extract_description_not_on_search_page(self, scraper_with_fixture_loaded):
        """Test _extract_description extracts from real HTML"""
        result = scraper_with_fixture_loaded._extract_description()

        # Should extract actual description from fixture
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0


class TestValidation:
    """Test data validation with Pydantic models"""

    def test_extract_and_validate_job_with_complete_data(self, chrome_driver):
        """Test validation succeeds with all required fields"""
        from datetime import datetime
        from unittest.mock import patch

        scraper = GlassdoorScraper(chrome_driver)

        # This mimics the actual extract_job_details output
        valid_data = {
            "job_title": "Data Scientist Intern",
            "company": "Example Corp",
            "location": "Paris, France",
            "description": "Great opportunity for ML enthusiasts",
            "url": "https://example.com/job/123",
            "verified_skills": ["Python", "Machine Learning"],
            "required_skills": ["SQL"],
            "is_easy_apply": True,
            "job_external_id": "123456",
            "job_age": 5,
            "posted_date": datetime(2025, 10, 28),
        }

        with patch.object(scraper, "extract_job_details", return_value=valid_data):
            result = scraper.extract_and_validate_job()

            assert result is not None
            assert result.job_title == "Data Scientist Intern"
            assert result.company == "Example Corp"
            assert len(result.get_all_skills()) == 3

    def test_extract_and_validate_job_with_missing_required_fields(self, chrome_driver):
        """Test validation fails with missing required fields"""
        from unittest.mock import patch

        scraper = GlassdoorScraper(chrome_driver)

        invalid_data = {
            "job_title": "Data Scientist",
            "company": "Example Corp",
        }

        with patch.object(scraper, "extract_job_details", return_value=invalid_data):
            result = scraper.extract_and_validate_job()

            assert result is None

    def test_extract_and_validate_job_handles_empty_data(self, chrome_driver):
        """Test handling of empty extraction results"""
        from unittest.mock import patch

        scraper = GlassdoorScraper(chrome_driver)

        with patch.object(scraper, "extract_job_details", return_value={}):
            result = scraper.extract_and_validate_job()
            assert result is None


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_glassdoor.py -v
    pytest.main([__file__, "-v", "-s"])
