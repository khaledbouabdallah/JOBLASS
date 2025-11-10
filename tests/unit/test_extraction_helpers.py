"""
Unit tests for Glassdoor scraper helper methods

Pure unit tests for utility functions that don't require Selenium or database.
"""

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from joblass.scrapers.glassdoor import GlassdoorScraper


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


class TestScraperUtilityMethods:
    """Test scraper utility methods that don't require real HTML"""

    def test_parse_job_age_to_seconds_days(self, chrome_driver):
        """Test job age parsing for days"""
        scraper = GlassdoorScraper(chrome_driver)
        assert scraper._parse_job_age_to_seconds("2d") == 2 * 86400
        assert scraper._parse_job_age_to_seconds("1d") == 86400

    def test_parse_job_age_to_seconds_hours(self, chrome_driver):
        """Test job age parsing for hours"""
        scraper = GlassdoorScraper(chrome_driver)
        assert scraper._parse_job_age_to_seconds("5h") == 5 * 3600

    def test_parse_job_age_to_seconds_with_plus_sign(self, chrome_driver):
        """Test job age parsing with + indicator"""
        scraper = GlassdoorScraper(chrome_driver)
        assert scraper._parse_job_age_to_seconds("30j+") == 30 * 86400

    def test_parse_job_age_invalid_format(self, chrome_driver):
        """Test job age parsing with invalid format"""
        scraper = GlassdoorScraper(chrome_driver)

        with pytest.raises(ValueError):
            scraper._parse_job_age_to_seconds("invalid")

        with pytest.raises(ValueError):
            scraper._parse_job_age_to_seconds("2x")

    def test_close_modal_when_not_present(self, chrome_driver):
        """Test modal closing when no modal exists"""
        from unittest.mock import patch

        scraper = GlassdoorScraper(chrome_driver)

        with patch("joblass.scrapers.glassdoor.wait_for_element") as mock_wait:
            # Simulate no modal found (timeout/exception)
            mock_wait.side_effect = Exception("No modal")

            assert scraper.close_modal_if_present() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
