import json
import re
from datetime import datetime
from typing import Optional

from pydantic import ValidationError
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from joblass.db import Job, JobRepository, ScrapedJobData
from joblass.utils.control import control
from joblass.utils.logger import setup_logger
from joblass.utils.selenium_helpers import (
    clear_and_type,
    human_click,
    human_delay,
    human_move,
    wait_for_element,
)

logger = setup_logger(__name__)


class GlassdoorScraper:
    """Handles Glassdoor job search scraping"""

    BASE_URL = "https://www.glassdoor.fr"

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def navigate_to_home(self):
        """Navigate to Glassdoor homepage"""
        logger.info(f"Navigating to {self.BASE_URL}")
        self.driver.get(self.BASE_URL)
        human_delay()

    def close_modal_if_present(self) -> bool:
        """Detect and close modal dialog if present"""
        try:
            modal = wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "dialog[aria-modal='true'][open]",
                timeout=1,
            )
            logger.info("Modal detected")

            close_button = modal.find_element(
                By.CSS_SELECTOR, "button[data-test*='modal-close']"
            )

            human_delay(0.3, 0.6)
            human_click(self.driver, close_button)

            wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "dialog[aria-modal='true'][open]",
                timeout=1,
            )

            logger.info("Modal closed")
            return True

        except Exception:
            logger.debug("No modal found")
            return False

    def save_job(
        self,
        title: str,
        company: str,
        location: str,
        url: str,
        description: Optional[str] = None,
        **kwargs,
    ) -> Optional[int]:
        """
        Save job to database with deduplication and Pydantic validation

        Args:
            title: Job title
            company: Company name
            location: Job location
            url: Job posting URL
            description: Job description
            **kwargs: Additional fields matching Job dataclass

        Returns:
            Job ID if successful, None if already exists or validation fails
        """
        if JobRepository.exists(url):
            logger.info(f"Job already in database: {url}")
            return None

        try:
            # Create Job object with all fields
            job = Job(
                title=title,
                company=company,
                location=location,
                url=url,
                source="glassdoor",
                description=description,
                scraped_date=datetime.now(),
                **kwargs,
            )

            job_id = JobRepository.insert(job)

            if job_id:
                logger.info(
                    f"Saved job to database: {title} at {company} (ID: {job_id})"
                )

            return job_id

        except ValueError as e:
            logger.error(f"Validation error saving job: {e}")
            return None
        except Exception as e:
            logger.error(f"Error saving job: {e}", exc_info=True)
            return None

    def save_job_from_validated_data(
        self, validated_data: ScrapedJobData
    ) -> Optional[int]:
        """
        Save job from Pydantic-validated data

        Args:
            validated_data: Validated ScrapedJobData instance

        Returns:
            Job ID if successful, None otherwise
        """
        if JobRepository.exists(validated_data.url):
            logger.info(f"Job already in database: {validated_data.url}")
            return None

        try:
            # Convert validated Pydantic model to database dict
            db_dict = validated_data.to_db_dict()

            # Create Job object from validated data
            job = Job(
                title=db_dict["title"],
                company=db_dict["company"],
                location=db_dict["location"],
                url=db_dict["url"],
                source=db_dict["source"],
                description=db_dict["description"],
                tech_stack=db_dict["tech_stack"],
                verified_skills=db_dict["verified_skills"],
                required_skills=db_dict["required_skills"],
                salary_min=db_dict["salary_min"],
                salary_max=db_dict["salary_max"],
                salary_median=db_dict["salary_median"],
                salary_currency=db_dict["salary_currency"],
                scraped_date=db_dict["scraped_date"],
                company_size=db_dict["company_size"],
                company_industry=db_dict["company_industry"],
                company_sector=db_dict["company_sector"],
                company_founded=db_dict["company_founded"],
                company_type=db_dict["company_type"],
                company_revenue=db_dict["company_revenue"],
                reviews_data=db_dict["reviews_data"],
            )

            job_id = JobRepository.insert(job)

            if job_id:
                logger.info(
                    f"Saved validated job to database: {job.title} at {job.company} (ID: {job_id})"
                )

            return job_id

        except Exception as e:
            logger.error(f"Error saving validated job: {e}", exc_info=True)
            return None

    def fill_search_form(
        self, job_title: str, location: str, preferred_location: Optional[str] = None
    ) -> int:
        """Fill Glassdoor search form with job title and location"""
        try:
            logger.info(f"Searching for '{job_title}' in '{location}'")

            control.wait_if_paused()
            control.check_should_stop()

            job_input = wait_for_element(
                self.driver, By.ID, "searchBar-jobTitle", timeout=3
            )
            human_move(self.driver, job_input)
            clear_and_type(job_input, job_title)
            human_delay(0.5, 1.0)

            location_input = wait_for_element(
                self.driver, By.ID, "searchBar-location", timeout=3
            )
            human_move(self.driver, location_input)
            clear_and_type(location_input, location)
            human_delay(1.0, 2.0)

            suggestions_list = wait_for_element(
                self.driver, By.ID, "searchBar-location-search-suggestions", timeout=5
            )
            suggestions = suggestions_list.find_elements(By.TAG_NAME, "li")

            if not suggestions:
                logger.warning("No location suggestions found")
                return 0

            logger.info(f"Found {len(suggestions)} location suggestions:")
            for idx, suggestion in enumerate(suggestions):
                logger.info(f"  [{idx}] {suggestion.text}")

            target_text = preferred_location if preferred_location else location
            clicked = False

            for idx, suggestion in enumerate(suggestions):
                if target_text.lower() in suggestion.text.lower():
                    logger.info(f"Selecting suggestion [{idx}]: {suggestion.text}")
                    control.wait_if_paused()
                    control.check_should_stop()
                    human_move(self.driver, suggestion)
                    human_delay(0.2, 0.5)
                    human_click(self.driver, suggestion)
                    clicked = True
                    break

            if not clicked:
                logger.error(f"Could not find suggestion matching '{target_text}'")
                return 0

            human_delay(0.3, 0.7)
            text = self.driver.find_element(
                By.CSS_SELECTOR, "h1[data-test='search-title']"
            ).text

            # Match numbers with optional thousand separators (1,234 or 1234)
            match = re.search(r"([\d,]+)", text)
            if match:
                # Remove commas and convert to int: "1,234" -> 1234
                total_jobs = int(match.group(1).replace(",", ""))
                logger.info(f"Found {total_jobs:,} total jobs")
                return total_jobs

            logger.warning("Could not extract job count from search results")
            return 0

        except InterruptedError as e:
            logger.info(str(e))
            return 0

        except Exception as e:
            logger.error(f"Error filling search form: {str(e)}", exc_info=True)
            return 0

    # === Extraction helpers ===

    def _safe_extract(self, func):
        """Run extractor safely, return None if it fails."""
        try:
            return func()
        except NoSuchElementException:
            return None
        except Exception as e:
            logger.debug(f"Safe extract failed for {func.__name__}: {e}")
            return None

    def _extract_job_title(self) -> Optional[str]:
        try:
            return self.driver.find_element(
                By.CSS_SELECTOR, "h1[id^='jd-job-title-']"
            ).text
        except NoSuchElementException:
            return None

    def _extract_company(self) -> Optional[str]:
        try:
            return self.driver.find_element(
                By.CSS_SELECTOR, "h4.heading_Subhead__jiUbT"
            ).text
        except NoSuchElementException:
            return None

    def _extract_location(self) -> Optional[str]:
        try:
            return self.driver.find_element(
                By.CSS_SELECTOR, "div[data-test='location']"
            ).text
        except NoSuchElementException:
            return None

    def _extract_verified_skills(self) -> list[str]:
        try:
            skills = self.driver.find_elements(
                By.CSS_SELECTOR, "li.VerifiedQualification_qualification__G0mvl span"
            )
            return [s.text for s in skills]
        except NoSuchElementException:
            return []

    def _extract_required_skills(self) -> list[str]:
        try:
            skills = self.driver.find_elements(
                By.CSS_SELECTOR, "span.PendingQualification_label__vCsCk"
            )
            return [s.text for s in skills]
        except NoSuchElementException:
            return []

    def _extract_description(self) -> Optional[str]:
        try:
            return self.driver.find_element(
                By.CSS_SELECTOR, "div.JobDetails_jobDescription__uW_fK"
            ).text
        except NoSuchElementException:
            return None

    def _extract_job_posting_url(self) -> Optional[str]:
        try:

            # click the apply button to open the job posting in a new tab
            _ = self.driver.find_element(
                By.CSS_SELECTOR, "button[data-test='applyButton']"
            )
            _.click()
            WebDriverWait(self.driver, 10).until(lambda d: len(d.window_handles) > 1)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            url = self.driver.current_url
            human_delay(0.5, 1.0)
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return url
        except Exception:
            return None

    # === Core extractors reused by safe_extract ===

    def extract_company_overview(self) -> dict[str, str | None]:
        """Extract company overview information"""
        overview: dict[str, str | None] = {
            "size": None,
            "founded": None,
            "type": None,
            "industry": None,
            "sector": None,
            "revenue": None,
        }
        try:
            items = self.driver.find_elements(
                By.CSS_SELECTOR, "div.JobDetails_overviewItem__cAsry"
            )
            for item in items:
                try:
                    label = item.find_element(
                        By.CSS_SELECTOR, "span.JobDetails_overviewItemLabel__KjFln"
                    ).text
                    value = item.find_element(
                        By.CSS_SELECTOR, "div.JobDetails_overviewItemValue__xn8EF"
                    ).text

                    if "Taille" in label:
                        overview["size"] = value
                    elif "Date de création" in label or "Fondée" in label:
                        overview["founded"] = value
                    elif "Type" in label:
                        overview["type"] = value
                    elif "Filière" in label:
                        overview["industry"] = value
                    elif "Secteur" in label:
                        overview["sector"] = value
                    elif "Ch. d'affaires" in label or "Chiffre" in label:
                        overview["revenue"] = value
                except NoSuchElementException:
                    continue
            return overview
        except Exception as e:
            logger.debug(f"Could not extract company overview: {str(e)}")
            return overview

    def extract_review_summary(self) -> dict:
        """Extract review summary with pros and cons"""
        summary: dict[str, list[dict[str, str | int]]] = {"pros": [], "cons": []}
        try:
            pros_label = "span.JobDetails_reviewProsLabel__40LEp"
            cons_label = "span.JobDetails_reviewConsLabel__rua2F"

            # Pros
            try:
                pros_list = self.driver.find_element(pros_label).find_element(
                    By.XPATH, "following-sibling::ul"
                )
                for item in pros_list.find_elements(By.TAG_NAME, "li"):
                    match = re.match(r'"(.+?)"\s*\(.*?(\d+)', item.text)
                    if match:
                        summary["pros"].append(
                            {"text": match.group(1), "count": int(match.group(2))}
                        )
            except NoSuchElementException:
                pass

            # Cons
            try:
                cons_list = self.driver.find_element(cons_label).find_element(
                    By.XPATH, "following-sibling::ul"
                )
                for item in cons_list.find_elements(By.TAG_NAME, "li"):
                    match = re.match(r'"(.+?)"\s*\(.*?(\d+)', item.text)
                    if match:
                        summary["cons"].append(
                            {"text": match.group(1), "count": int(match.group(2))}
                        )
            except NoSuchElementException:
                pass

            return summary
        except Exception as e:
            logger.debug(f"Could not extract review summary: {str(e)}")
            return summary

    def extract_salary_info(self) -> dict[str, str | int | None]:
        """Extract and parse salary information"""

        salary_info: dict[str, str | int | None] = {
            "lower_bound": None,
            "upper_bound": None,
            "median": None,
            "currency": None,
        }

        try:
            text = self.driver.find_element(
                By.CSS_SELECTOR, "div.SalaryEstimate_salaryRange__brHFy"
            ).text
            numbers = re.findall(r"(\d+)\s*k", text)
            if len(numbers) >= 2:
                salary_info["lower_bound"], salary_info["upper_bound"] = [
                    int(n) * 1000 for n in numbers[:2]
                ]

            match = re.search(r"([€$£¥])", text)
            if match:
                salary_info["currency"] = match.group(1)

            median_text = self.driver.find_element(
                By.CSS_SELECTOR, "div.SalaryEstimate_medianEstimate__fOYN1"
            ).text
            median_match = re.search(r"(\d+)\s*k", median_text)
            if median_match:
                salary_info["median"] = int(median_match.group(1)) * 1000

            return salary_info
        except NoSuchElementException:
            return salary_info
        except Exception as e:
            logger.debug(f"Could not extract salary info: {str(e)}")
            return salary_info

    # === Refactored main extractor ===

    def extract_job_details(self) -> dict[str, str | list | dict | None]:
        """Extract job information from Glassdoor job details page"""
        job_data: dict[str, str | list | dict | None] = {}
        driver = self.driver

        try:
            wait_for_element(
                driver, By.CSS_SELECTOR, "div.JobDetails_jobDetailsContainer__y9P3L"
            )

            job_data["job_title"] = self._extract_job_title()
            job_data["company"] = self._extract_company()
            job_data["location"] = self._extract_location()
            job_data["verified_skills"] = self._extract_verified_skills()
            job_data["required_skills"] = self._extract_required_skills()
            job_data["description"] = self._extract_description()
            job_data["url"] = self._extract_job_posting_url()
            job_data["salary_estimate"] = self._safe_extract(self.extract_salary_info)
            job_data["company_overview"] = self._safe_extract(
                self.extract_company_overview
            )
            job_data["reviews_summary"] = self._safe_extract(
                self.extract_review_summary
            )

            logger.info(
                f"Extracted: {job_data.get('job_title', 'Unknown')} at {job_data.get('company', 'Unknown')}"
            )
            return job_data

        except Exception as e:
            logger.error(f"Error extracting job details: {str(e)}", exc_info=True)
            return job_data

    def extract_and_validate_job(self) -> Optional[ScrapedJobData]:
        """
        Extract job details and validate with Pydantic

        Args:
            url: Job posting URL

        Returns:
            Validated ScrapedJobData instance or None if validation fails
        """
        try:
            # Extract raw data
            raw_data = self.extract_job_details()

            if not raw_data:
                logger.warning("No data extracted from job page")
                return None

            # Validate with Pydantic
            validated_data = ScrapedJobData.from_glassdoor_extract(raw_data)

            logger.info(
                f"✓ Validated job data: {validated_data.job_title} at {validated_data.company}"
            )
            logger.debug(
                f"Skills: {len(validated_data.get_all_skills())} total "
                f"({len(validated_data.verified_skills)} verified, "
                f"{len(validated_data.required_skills)} required)"
            )

            return validated_data

        except ValidationError as e:
            logger.error(f"Pydantic validation failed: {e}")
            logger.debug(
                f"Raw data that failed validation: {json.dumps(raw_data, indent=2)}"
            )
            return None
        except Exception as e:
            logger.error(f"Error extracting and validating job: {e}", exc_info=True)
            return None

    def search_jobs(
        self, job_title: str, location: str, preferred_location: Optional[str] = None
    ) -> bool:
        """Complete job search workflow"""
        try:
            logger.info("=== Starting Glassdoor job search ===")
            self.navigate_to_home()

            if not self.fill_search_form(job_title, location, preferred_location):
                logger.error("Failed to fill search form")
                return False

            # TODO: implement extra filters
            # date posted, easy apply, salary estiamte, company rating, sort by relevance/date

            # TODO: save search url for future reference

            # TODO: Scrape job listings from results page
            # iterate through jobs by clicking, then scrap its contenet, go the next job, and keep scolling
            # no pagination exist, after some scrolling, "see more jobs" button appears at the bottom
            # no changing page, clicking show job details
            # smart search: if job already exists in db, skip it (no need to click it)
            # maybe save job listing urls to a set to avoid duplicates

            logger.info("=== Job search completed successfully ===")
            return True

        except Exception as e:
            logger.error(f"Search workflow failed: {str(e)}", exc_info=True)
            return False
