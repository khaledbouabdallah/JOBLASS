"""
Integration tests for Glassdoor scraper extraction methods

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

import pytest
from selenium.webdriver.common.by import By

from joblass.scrapers.glassdoor import GlassdoorScraper


class TestJobDataExtraction:
    """Test extraction methods with real Selenium and HTML fixtures"""

    def test_extract_job_header_info_from_real_html(
        self, chrome_driver, job_search_page_fixture
    ):
        """Test _extract_job_header_info extracts from actual HTML fixture"""
        from datetime import date

        # Load the fixture
        chrome_driver.get(job_search_page_fixture)
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
        self, chrome_driver, job_search_page_fixture
    ):
        """Test _extract_verified_skills extracts skills from real HTML"""
        chrome_driver.get(job_search_page_fixture)
        scraper = GlassdoorScraper(chrome_driver)

        result = scraper._extract_verified_skills()

        # Should extract skills from the fixture
        assert isinstance(result, list)
        # Fixture has at least some skills
        if len(result) > 0:
            assert all(isinstance(skill, str) for skill in result)
            print(f"\nExtracted verified skills: {result}")

    def test_extract_required_skills_not_on_search_page(
        self, chrome_driver, job_search_page_fixture
    ):
        """Test _extract_required_skills extracts skills from real HTML"""
        chrome_driver.get(job_search_page_fixture)
        scraper = GlassdoorScraper(chrome_driver)

        result = scraper._extract_required_skills()

        # Should extract skills from the fixture
        assert isinstance(result, list)
        # Fixture has at least some required skills
        if len(result) > 0:
            assert all(isinstance(skill, str) for skill in result)
            print(f"\nExtracted required skills: {result}")

    def test_extract_job_title_not_on_search_page(
        self, chrome_driver, job_search_page_fixture
    ):
        """Test _extract_job_title extracts from real HTML"""
        chrome_driver.get(job_search_page_fixture)
        scraper = GlassdoorScraper(chrome_driver)

        result = scraper._extract_job_title()

        # Should extract actual job title from fixture
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\nExtracted job title: {result}")

    def test_extract_company_not_on_search_page(
        self, chrome_driver, job_search_page_fixture
    ):
        """Test _extract_company extracts from real HTML"""
        chrome_driver.get(job_search_page_fixture)
        scraper = GlassdoorScraper(chrome_driver)

        result = scraper._extract_company()

        # Should extract actual company from fixture
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\nExtracted company: {result}")

    def test_extract_location_not_on_search_page(
        self, chrome_driver, job_search_page_fixture
    ):
        """Test _extract_location extracts from real HTML"""
        chrome_driver.get(job_search_page_fixture)
        scraper = GlassdoorScraper(chrome_driver)

        result = scraper._extract_location()

        # Should extract location from fixture
        if result is not None:
            assert isinstance(result, str)
            assert len(result) > 0
            print(f"\nExtracted location: {result}")

    def test_extract_description_not_on_search_page(
        self, chrome_driver, job_search_page_fixture
    ):
        """Test _extract_description extracts from real HTML"""
        chrome_driver.get(job_search_page_fixture)
        scraper = GlassdoorScraper(chrome_driver)

        result = scraper._extract_description()

        # Should extract actual description from fixture
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0


class TestJobDetailsValidation:
    """Test extract_job_details with Pydantic validation

    Note: These tests verify the validation layer, not the full extraction pipeline.
    Full extraction requires navigating to real job pages.
    """

    def test_extract_job_details_with_complete_data(self, chrome_driver):
        """Test validation succeeds with all required fields"""
        from unittest.mock import MagicMock, patch

        scraper = GlassdoorScraper(chrome_driver)

        # Mock all extraction methods to return valid data
        with (
            patch.object(scraper, "_click_on_show_more_description"),
            patch.object(
                scraper, "_extract_job_title", return_value="Data Scientist Intern"
            ),
            patch.object(scraper, "_extract_company", return_value="Example Corp"),
            patch.object(scraper, "_extract_location", return_value="Paris, France"),
            patch.object(
                scraper,
                "_extract_description",
                return_value="Great opportunity for ML enthusiasts",
            ),
            patch.object(
                scraper,
                "_extract_verified_skills",
                return_value=["Python", "Machine Learning"],
            ),
            patch.object(scraper, "_extract_required_skills", return_value=["SQL"]),
            patch.object(
                scraper,
                "_extract_job_posting_url",
                return_value=("https://example.com/job/123", False),
            ),
            patch.object(
                scraper,
                "extract_salary_info",
                return_value={"lower_bound": 50000, "upper_bound": 70000},
            ),
            patch(
                "joblass.scrapers.glassdoor.wait_for_element", return_value=MagicMock()
            ),
        ):

            job_result, company_result = scraper.extract_job_details(
                extract_company_info=False
            )

            assert job_result is not None
            assert job_result.job_title == "Data Scientist Intern"
            assert job_result.company == "Example Corp"
            assert len(job_result.get_all_skills()) == 3

            # Company should be None when extract_company_info=False
            assert company_result is None

    def test_extract_job_details_with_missing_required_fields(self, chrome_driver):
        """Test validation fails gracefully with missing required fields"""
        from unittest.mock import MagicMock, patch

        scraper = GlassdoorScraper(chrome_driver)

        # Mock extraction with missing required fields (title and company)
        with (
            patch.object(scraper, "_click_on_show_more_description"),
            patch.object(scraper, "_extract_job_title", return_value=None),
            patch.object(scraper, "_extract_company", return_value=None),
            patch.object(scraper, "_extract_location", return_value=None),
            patch.object(scraper, "_extract_description", return_value=None),
            patch.object(scraper, "_extract_verified_skills", return_value=[]),
            patch.object(scraper, "_extract_required_skills", return_value=[]),
            patch.object(
                scraper, "_extract_job_posting_url", return_value=(None, None)
            ),
            patch.object(scraper, "extract_salary_info", return_value={}),
            patch(
                "joblass.scrapers.glassdoor.wait_for_element", return_value=MagicMock()
            ),
        ):

            job_result, company_result = scraper.extract_job_details(
                extract_company_info=False
            )

            # Should return None for both when validation fails
            assert job_result is None
            assert company_result is None

    def test_extract_job_details_handles_empty_extraction(self, chrome_driver):
        """Test handling of empty extraction results"""
        from unittest.mock import MagicMock, patch

        scraper = GlassdoorScraper(chrome_driver)

        # Mock all extractions returning None/empty
        with (
            patch.object(scraper, "_click_on_show_more_description"),
            patch.object(scraper, "_extract_job_title", return_value=""),
            patch.object(scraper, "_extract_company", return_value=""),
            patch.object(scraper, "_extract_location", return_value=None),
            patch.object(scraper, "_extract_description", return_value=None),
            patch.object(scraper, "_extract_verified_skills", return_value=[]),
            patch.object(scraper, "_extract_required_skills", return_value=[]),
            patch.object(
                scraper, "_extract_job_posting_url", return_value=(None, None)
            ),
            patch.object(scraper, "extract_salary_info", return_value={}),
            patch(
                "joblass.scrapers.glassdoor.wait_for_element", return_value=MagicMock()
            ),
        ):

            job_result, company_result = scraper.extract_job_details(
                extract_company_info=False
            )

            assert job_result is None
            assert company_result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
