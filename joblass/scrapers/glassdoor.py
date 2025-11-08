import json
import logging
import re
import time
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import ValidationError
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from joblass.db import Job, JobRepository, ScrapedJobData
from joblass.utils.control import control
from joblass.utils.logger import setup_logger
from joblass.utils.selenium_helpers import (
    clear_and_type,
    highlight,
    human_click,
    human_delay,
    human_move,
    human_scroll_to_element,
    safe_browser_tab_switch,
    scroll_until_visible,
    wait_for_element,
    wait_page_loaded,
)

logger = setup_logger(__name__, level=logging.DEBUG)


class ExtraFilters:
    def __init__(self, driver):

        self.driver = driver
        self.actionchain = ActionChains(self.driver)

        self.accordions_names_check_box = [
            "is_easy_apply",
            "is_remote",
        ]

        self.accordions_names_choice = []
        self._open_dropdown()
        self._get_options()

    def _already_opened(self):
        try:
            self.dropdown = self.driver.find_element(
                By.XPATH,
                '//button[@data-test="expand-filters"]/following-sibling::div/div',
            )
            return True
        except:  # noqa: E722
            return False

    def _close_dropdown(self):
        if not self._already_opened():
            print("Dropdown already closed")
            return
        human_click(self.driver, self.open_close_dropdown)

    def _open_dropdown(self):

        if self._already_opened():
            print("Dropdown already opened")
            return

        try:
            self.open_close_dropdown = self.driver.find_element(
                By.CLASS_NAME, "SearchFiltersExpanded_filterMenuContainer__Ar0fV"
            )

            human_click(self.driver, self.open_close_dropdown)

            self.dropdown = self.driver.find_element(
                By.XPATH,
                '//button[@data-test="expand-filters"]/following-sibling::div/div',
            )
        except NoSuchElementException:
            logger.error("Could not find the dropdown element to open filters")
            raise NoSuchElementException(  # noqa: B904
                "Could not find the dropdown element to open filters"
            )

    def _get_options(self):

        self.salary_range = self.get_salary_range()
        self.parts = self.dropdown.find_elements(By.XPATH, "./div")

        self.easy_apply_toggle = self.parts[1].find_element(By.TAG_NAME, "label")
        self.remote_toggle = self.parts[2].find_element(By.TAG_NAME, "label")

        # get buttons
        self.clear_button = self.parts[-1].find_elements(By.TAG_NAME, "button")[0]
        self.confirm_button = self.parts[-1].find_elements(By.TAG_NAME, "button")[1]

        # accordions of choice
        self.accordions_choice_options = {}
        self.accordions_choice_elements = {}
        for i, part in enumerate(self.parts[4:-1]):

            human_delay(0.2, 0.5)
            name = part.text.lower().strip()
            self.accordions_names_choice.append(name)
            part.click()

            if i == 0:
                options = ["+1", "+2", "+3", "+4"]
            else:
                options = [
                    option.text.strip()
                    for option in part.find_elements(By.TAG_NAME, "button")[1:]
                    if option.text.strip()
                ]  # first is the accordion text

            self.accordions_choice_options[name] = options
            self.accordions_choice_elements[name] = part

    def choose_accordion_option(self, accordion_name, option_position):
        if accordion_name not in self.accordions_names_choice:
            raise ValueError(f"Invalid choice accordion name: {accordion_name}")
        if option_position < 1 or option_position > len(
            self.accordions_choice_options[accordion_name]
        ):
            raise ValueError(
                f"Invalid option position {option_position} for accordion {accordion_name}"
            )
        accordion = self.accordions_choice_elements[accordion_name]
        option_to_click = accordion.find_elements(By.TAG_NAME, "button")[
            option_position + 1
        ]  # first is the accordion text, +1 to start index at 1
        human_click(self.driver, option_to_click)
        return accordion_name, option_to_click.text.strip()

    def get_salary_range(self):
        min_val = self.dropdown.find_element(
            By.CSS_SELECTOR, 'input[data-test="min-salary"]'
        ).get_attribute("value")
        max_val = self.dropdown.find_element(
            By.CSS_SELECTOR, 'input[data-test="max-salary"]'
        ).get_attribute("value")
        return int(min_val), int(max_val)

    def set_salary_range(self, min_salary: int, max_salary: int):
        min_input = self.dropdown.find_element(
            By.CSS_SELECTOR, 'input[data-test="min-salary"]'
        )
        max_input = self.dropdown.find_element(
            By.CSS_SELECTOR, 'input[data-test="max-salary"]'
        )

        def _set_salary(element, value):
            element.clear()
            element.send_keys(str(value))

        clear_and_type(max_input, self.actionchain, str(max_salary))
        clear_and_type(min_input, self.actionchain, str(min_salary))
        return self.get_salary_range()

    def toggle_label(self, label_element: WebElement, desired_state: bool):
        current_state = label_element.get_attribute("aria-pressed") == "true"
        if current_state != desired_state:
            human_click(self.driver, label_element)
        return label_element.get_attribute("aria-pressed") == "true"

    def apply_filters(self, filters: dict):  # noqa: C901

        # validate filters
        for key, value in filters.items():
            if (
                key
                not in self.accordions_names_check_box
                + self.accordions_names_choice
                + ["salary_range"]
            ):
                logger.error(f"Unknown filter key: {key}, cannot apply filters.")
                return
            if value not in [True, False] and key in self.accordions_names_check_box:
                logger.error(
                    f"Invalid value for checkbox filter '{key}': {value}. Must be True or False."
                )
                return
            if (
                value not in self.accordions_choice_options.get(key, [])
                and key in self.accordions_names_choice
            ):
                logger.error(
                    f"Invalid value for choice filter '{key}': {value}. Available options: {self.accordions_choice_options.get(key, [])}"
                )
                return
            if key == "salary_range":
                if (
                    not isinstance(value, (list, tuple))
                    or len(value) != 2
                    or not all(isinstance(v, int) for v in value)
                ):
                    logger.error(
                        f"Invalid value for salary_range filter: {value}. Must be a tuple/list of two integers (min_salary, max_salary)."
                    )
                    return

        # apply filters
        for key, value in filters.items():
            if key in self.accordions_names_check_box:
                if key == "is_easy_apply":
                    self.toggle_label(self.easy_apply_toggle, value)
                    logger.debug("toggled easy apply")
                elif key == "is_remote":
                    self.toggle_label(self.remote_toggle, value)
                    logger.debug("toggled remote")
            elif key in self.accordions_names_choice:
                options = self.accordions_choice_options[key]
                option_position = options.index(value) + 1  # +1 to start index at 1
                self.choose_accordion_option(key, option_position)
                logger.debug(f"Set {key} to {value}")
            elif key == "salary_range":
                min_salary, max_salary = value
                self.set_salary_range(min_salary, max_salary)
                logger.debug(f"Set {key} to {value}")

    def validate_and_close(self):
        human_click(self.driver, self.confirm_button)


class GlassdoorScraper:
    """Handles Glassdoor job search scraping"""

    BASE_URL = "https://www.glassdoor.fr"

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.action: ActionChains = ActionChains(driver)

    def navigate_to_home(self):
        """Navigate to Glassdoor homepage"""
        logger.info(f"Navigating to {self.BASE_URL}")
        self.driver.get(self.BASE_URL)
        human_delay()

    def is_logged_in(self) -> bool:
        """Determine if user is logged in or not by the redirection from BASE_URL"""
        wait = WebDriverWait(self.driver, 10)
        current_page = wait.until(
            lambda d: d.execute_script(
                "return window.__GD_GLOBAL_NAV_DATA__?.appData?.id ?? null;"
            )
            is not None
        )
        current_page = self.driver.execute_script(
            "return window.__GD_GLOBAL_NAV_DATA__?.appData?.id;"
        )

        logger.info(f"URL page leads to: {current_page}")

        return current_page != "signed-out-home-page"

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
        self, validated_data: ScrapedJobData, session_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Save job from Pydantic-validated data with URL-based deduplication.

        Args:
            validated_data: Validated ScrapedJobData instance
            session_id: Optional search session ID to link job to

        Returns:
            Job ID if successful, None if duplicate or save failed

        Note:
            Database enforces URL uniqueness. Duplicate URLs are caught by
            JobRepository.insert() which returns None (logged as duplicate).
            Other errors are logged with full traceback.
        """
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
                posted_date=db_dict.get("posted_date"),
                job_age=validated_data.job_age,
                is_easy_apply=db_dict.get("is_easy_apply"),
                job_external_id=db_dict.get("job_external_id"),
                company_size=db_dict["company_size"],
                company_industry=db_dict["company_industry"],
                company_sector=db_dict["company_sector"],
                company_founded=db_dict["company_founded"],
                company_type=db_dict["company_type"],
                company_revenue=db_dict["company_revenue"],
                reviews_data=db_dict["reviews_data"],
                session_id=session_id,
            )

            # Let database handle uniqueness constraint
            # JobRepository.insert() returns None for duplicates (logs as warning)
            # or for other errors (logs as error)
            job_id = JobRepository.insert(job)

            if job_id:
                logger.info(
                    f"✓ Saved job to database: {job.title} at {job.company} (ID: {job_id})"
                )
            # If job_id is None, the error/warning was already logged by JobRepository

            return job_id

        except ValidationError as e:
            # Pydantic validation error (shouldn't happen since data is pre-validated)
            logger.error(f"Validation error creating Job object: {e}", exc_info=True)
            return None
        except Exception as e:
            # Unexpected error (not caught by JobRepository)
            logger.error(
                f"Unexpected error saving job {validated_data.job_title} at {validated_data.company}: {e}",
                exc_info=True,
            )
            return None

    def get_jobs_found_count(self) -> int:
        """Extract total number of jobs found from search results page"""
        try:
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

        except Exception as e:
            logger.error(f"Error extracting jobs found count: {str(e)}", exc_info=True)
            return 0

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
            clear_and_type(job_input, self.action, job_title)
            human_delay(0.3, 0.8)

            location_input = wait_for_element(
                self.driver, By.ID, "searchBar-location", timeout=3
            )
            human_move(self.driver, location_input)
            clear_and_type(location_input, self.action, location)
            human_delay(0.3, 0.8)

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
            return self.get_jobs_found_count()

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

    def _extract_job_posting_url(self) -> tuple[Optional[str], Optional[bool]]:
        """
        Extract external job posting URL (if not easy apply)

        Returns:
            Tuple of (external_url, is_easy_apply)
            - For easy apply jobs: (None, True)
            - For external apply jobs: (url, False) or (None, None) if failed
        """
        is_easy_apply = False
        try:
            # click the apply button to open the job posting in a new tab
            button = self.driver.find_element(
                By.CSS_SELECTOR, "button[data-test='applyButton']"
            )
            logger.debug("Standard Apply button detected")
        except NoSuchElementException:
            # Easy apply job
            is_easy_apply = True
            button = self.driver.find_element(
                By.CSS_SELECTOR, "button[data-test='easyApply']"
            )

        try:
            human_click(self.driver, button)
            logger.debug("Clicked apply button to open job posting")
            WebDriverWait(self.driver, 5).until(lambda d: len(d.window_handles) > 1)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            # Wait until URL is not empty or 'about:blank'
            WebDriverWait(self.driver, 10).until(
                lambda d: d.current_url not in ("", "about:blank")
            )
            url = self.driver.current_url
            logger.debug(f"Extracted external job posting URL: {url}")
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return url, is_easy_apply
        except Exception as e:
            logger.debug(f"Failed to extract external URL: {e}")
            return None, None

    def _parse_job_age_to_seconds(self, job_age: str) -> int | None:
        """Parse job age string to seconds.
        Example formats: "2d", "5h", "30j+"
        """
        # Extract number and unit using regex
        match = re.match(r"(\d+)([dhj])\+?", job_age)
        if not match:
            raise ValueError(f"Invalid job age format: {job_age}")
        value, unit = match.groups()
        value = int(value)
        if unit == "d":
            return value * 86400  # 1 day = 86400 seconds
        elif unit == "h":
            return value * 3600  # 1 hour = 3600 seconds
        elif unit == "j":
            return value * 86400  # Assuming 'j' means days as well
        else:
            raise ValueError(f"Unknown time unit in job age: {unit}")
        return 0  # Should never reach here due to ValueError, but satisfies mypy

    def _extract_job_header_info(self, element: WebElement) -> dict:
        # fromat: "XXd or XXh", can be 30j+
        job_age = element.find_element(By.CSS_SELECTOR, "div[data-test='job-age']").text
        job_age_seconds = self._parse_job_age_to_seconds(job_age)

        # Handle None case - if parsing fails, default to current time (0 days old)
        if job_age_seconds is None:
            job_age_seconds = 0

        job_published_date = time.time() - job_age_seconds
        job_external_id = element.get_attribute("data-jobid")
        return {
            "job_external_id": job_external_id,
            "job_age": job_age_seconds // 86400,  # in days
            "job_published_date": date.fromtimestamp(job_published_date),
        }

    def _click_on_show_more_description(self) -> None:
        """Click on 'Show More' button in job description if present"""
        try:
            show_more_button = self.driver.find_element(
                By.CSS_SELECTOR, "button[data-test='show-more-cta']"
            )
            human_click(self.driver, show_more_button)
        except NoSuchElementException:
            pass

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

            review_wrapper_selector = "section[data-test='company-reviews']"
            job_detail_container = wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "div.TwoColumnLayout_jobDetailsContainer__qyvJZ",
            )

            is_visible = scroll_until_visible(
                self.driver, job_detail_container, review_wrapper_selector, timeout=5
            )

            if not is_visible:
                logger.error(
                    "Review summary section not visible after scrolling, either internet connection is slow or the chrome brwoser"
                )
                return summary

            # Find the review wrapper that contains both pros and cons
            review_wrapper = wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                review_wrapper_selector,
                timeout=3,
            )

            pro_section, cons_section = review_wrapper.find_elements(
                By.CSS_SELECTOR, "ul"
            )

            def extract_review_summry_item(
                review_element: WebElement,
            ) -> tuple[str, int]:
                review, count_text = review_element.text.split('"')[1:]
                review = review.strip()
                # extract numbers from count_text
                count = int("".join(filter(str.isdigit, count_text)))
                return review, count

            for review in pro_section.find_elements(By.CSS_SELECTOR, "li"):
                review, count = extract_review_summry_item(review)
                summary["pros"].append({"text": review, "count": count})

            for review in cons_section.find_elements(By.CSS_SELECTOR, "li"):
                review, count = extract_review_summry_item(review)
                summary["cons"].append({"text": review, "count": count})

            return summary
        except (NoSuchElementException, TimeoutException) as e:
            logger.debug(f"Could not extract review summary: {str(e)}")
            return summary
        except Exception as e:
            logger.debug(f"Unexpected error in extract_review_summary: {str(e)}")
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

    # === main extractor ===

    def extract_job_details(self) -> dict[str, str | list | dict | bool | None]:
        """Extract job information from Glassdoor job details page"""
        job_data: dict[str, str | list | dict | bool | None] = {}

        try:
            wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "div.JobDetails_jobDetailsContainer__y9P3L",
            )

            # self._click_on_show_more_description()

            job_data["job_title"] = self._extract_job_title()
            job_data["company"] = self._extract_company()
            job_data["location"] = self._extract_location()
            job_data["verified_skills"] = self._extract_verified_skills()
            job_data["required_skills"] = self._extract_required_skills()
            job_data["description"] = self._extract_description()

            # Extract external URL and easy apply status
            external_url, job_data["is_easy_apply"] = self._extract_job_posting_url()
            # If we got an external URL, use it; otherwise keep the Glassdoor URL
            if external_url:
                job_data["url"] = external_url

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

    def search_jobs(  # noqa: C901
        self, jobs_found: int, max_jobs: Optional[int], skip_until: Optional[int]
    ) -> list[ScrapedJobData]:
        """Search for jobs on Glassdoor Loop through search results and extract job details."""
        try:

            scraped_jobs: list[ScrapedJobData] = []

            if max_jobs is not None:
                jobs_found = min(jobs_found, max_jobs)

            if not jobs_found:
                logger.warning("Failed to fill search form")
                return scraped_jobs

            current_job_index = 0
            if skip_until:
                current_job_index = skip_until
                logger.info(f"Skipping to job index {skip_until}")

            jobs = self.driver.find_elements(
                By.CSS_SELECTOR, "li[data-test='jobListing']"
            )

            while current_job_index < jobs_found:
                try:
                    control.wait_if_paused()
                    control.check_should_stop()
                    self.close_modal_if_present()

                    # if we reached the end of the currently loaded jobs, try to load more
                    if current_job_index == len(jobs):

                        load_more_jobs_button = self.driver.find_element(
                            By.CSS_SELECTOR, 'button[data-test="load-more"]'
                        )

                        if load_more_jobs_button.is_displayed():
                            human_scroll_to_element(self.driver, load_more_jobs_button)
                            human_click(self.driver, load_more_jobs_button)
                            human_delay(0.2, 1)
                            self.close_modal_if_present()
                            jobs = self.driver.find_elements(
                                By.CSS_SELECTOR, "li[data-test='jobListing']"
                            )
                        break

                    job_element = jobs[current_job_index]
                    job_element_info = self._extract_job_header_info(job_element)

                    # check if job_element is visible
                    if not job_element.is_displayed():
                        human_scroll_to_element(self.driver, job_element)

                    human_click(self.driver, job_element)
                    human_delay(0.3, 1)
                    job_data: ScrapedJobData | None = self.extract_and_validate_job()

                    # Add job info from header to job_data
                    if job_data:
                        job_data.job_external_id = job_element_info["job_external_id"]
                        job_data.job_age = job_element_info["job_age"]
                        job_data.posted_date = job_element_info["job_published_date"]

                    highlight(
                        job_element,
                        duration=0.5,
                        color="lightgreen",
                        border="2px solid green",
                    )
                    if job_data:
                        scraped_jobs.append(job_data)
                    current_job_index += 1
                except InterruptedError as e:
                    logger.info(str(e))
                    break
                except Exception as e:

                    highlight(
                        job_element,
                        duration=0.5,
                        color="salmon",
                        border="2px solid red",
                    )
                    logger.error(
                        f"Failed to process job at index {current_job_index}: {str(e)}",
                        exc_info=True,
                    )
                    current_job_index += 1
                    continue

            logger.info("=== Job search completed successfully ===")
            return scraped_jobs

        except Exception as e:
            logger.error(f"Search workflow failed: {str(e)}", exc_info=True)
            return scraped_jobs

    # =========== Company profile navigation ===========

    def navigate_to_company_profile(self) -> bool:
        """
        Navigate to the company profile page from job details.

        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            # Wait for and find the employer profile link
            company_link = wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "a.EmployerProfile_profileContainer__63w3R",
                timeout=2,
            )

            # Get the href before clicking (for logging/verification)
            company_url = company_link.get_attribute("href")
            company_name = company_link.find_element(
                By.CSS_SELECTOR, "h4.heading_Heading__aomVx"
            ).text

            logger.info(f"Navigating to {company_name} profile: {company_url}")

            # Click to navigate
            human_click(self.driver, company_link)
            safe_browser_tab_switch(self.driver, -1)

            return True

        except (NoSuchElementException, TimeoutException):
            logger.info("Company profile link not found, compnay has no profile")
            return False
        except Exception as e:
            logger.error(f"Failed to navigate to company profile: {e}", exc_info=True)
            return False

    def switch_company_tab(
        self,
        tab: Literal[
            "overview",
            "reviews",
            "jobs",
            "salaries",
            "interviews",
            "benefits",
            "photos",
            "diversity",
        ],
    ) -> bool:
        """
        Switch to a specific tab on company profile page.

        Args:
            tab: Tab name to switch to (e.g., "reviews", "jobs", "salaries")

        Returns:
            bool: True if tab switch successful, False otherwise

        Example:
            scraper.switch_company_tab("reviews")
            scraper.switch_company_tab("salaries")
        """
        try:

            control.wait_if_paused()
            control.check_should_stop()

            logger.info(f"Switching to '{tab}' tab")

            # Find the tab container by ID
            tab_element = wait_for_element(self.driver, By.ID, tab, timeout=5)

            # Check if already selected
            is_selected = tab_element.get_attribute("data-ui-selected") == "true"
            if is_selected:
                logger.debug(f"Tab '{tab}' already selected")
                return True

            # Click the tab
            human_click(self.driver, tab_element)
            wait_page_loaded(self.driver)

            # Verify tab is now selected
            tab_element = wait_for_element(self.driver, By.ID, tab, timeout=5)
            is_selected = tab_element.get_attribute("data-ui-selected") == "true"

            if is_selected:
                logger.debug(f"Successfully switched to '{tab}' tab")
                return True
            else:
                logger.warning(f"Tab '{tab}' clicked but not marked as selected")
                return False

        except InterruptedError as e:
            logger.info(str(e))
            return False
        except NoSuchElementException:
            logger.error(f"Tab '{tab}' not found on page")
            return False
        except Exception as e:
            logger.error(f"Failed to switch to tab '{tab}': {e}", exc_info=True)
            return False

    def extract_company_info(self) -> dict[str, str | None]:
        """
        Extract company overview information from profile page.

        Returns:
            dict: Company information with keys:
                - website: Company website URL
                - url: Current Glassdoor profile URL
                - headquarters: Company location
                - size: Employee count
                - type: Company type
                - founded: Year founded
                - revenue: Revenue range
                - industry: Industry/sector
                - description: Company description
        """
        info: dict[str, str | None] = {
            "website": None,
            "url": None,
            "headquarters": None,
            "size": None,
            "type": None,
            "founded": None,
            "revenue": None,
            "industry": None,
            "description": None,
        }

        try:
            control.wait_if_paused()
            control.check_should_stop()

            # Wait for overview module
            wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "div[data-test='employerOverviewModule']",
                timeout=5,
            )

            info["url"] = self.driver.current_url

            # Get all detail items
            detail_items = self.driver.find_elements(
                By.CSS_SELECTOR, "li.employer-overview_employerEntityContainer__RsMbe"
            )

            # Extract each field using a loop
            fields = [
                ("website", 0, "website"),
                ("headquarters", 1, "text"),
                ("size", 2, "text"),
                ("type", 3, "text"),
                ("founded", 4, "text"),
                ("revenue", 5, "text"),
                ("industry", 6, "industry"),
            ]

            for field_name, index, field_type in fields:
                try:
                    if field_type == "website":
                        website_link = detail_items[index].find_element(
                            By.CSS_SELECTOR, "a.employer-overview_websiteLink__vj3I0"
                        )
                        info[field_name] = website_link.get_attribute("href")
                    elif field_type == "industry":
                        industry_link = detail_items[index].find_element(
                            By.CSS_SELECTOR,
                            "a.employer-overview_employerOverviewLink__P8pxW",
                        )
                        info[field_name] = industry_link.text.strip()
                    else:  # text
                        info[field_name] = detail_items[index].text.strip()
                except (IndexError, NoSuchElementException):
                    pass

            # Extract description separately
            try:
                description_element = self.driver.find_element(
                    By.CSS_SELECTOR, "span[data-test='employerDescription']"
                )
                info["description"] = description_element.text.strip()
            except NoSuchElementException:
                logger.debug("Could not extract company description")

            logger.info(f"Extracted company info from: {info['url']}")

            return info

        except InterruptedError as e:
            logger.info(str(e))
            return info
        except Exception as e:
            logger.error(f"Failed to extract company info: {e}", exc_info=True)
            return info

    def extract_company_evaluations(self) -> dict:
        """Extract company evaluations"""
        result: dict[str, float | int | None] = {
            "global": None,
            "reviews_count": None,
            "recommend_to_friend": None,
            "culture_and_values": None,
            "diversity_equity_inclusion": None,
            "work_life_balance": None,
            "senior_management": None,
            "compensation_and_benefits": None,
            "career_opportunities": None,
        }
        # see_more_button = wait_for_element(driver, By.CSS_SELECTOR, "button[data-test='review-overview-insights-button']", timeout=2)
        # human_click(driver, see_more_button)
        result["global"] = float(
            wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "div[data-test='rating-headline']",
                timeout=2,
            )
            .find_element(By.CSS_SELECTOR, "p")
            .text.replace(",", ".")
        )
        result["recommend_to_friend"] = float(
            wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "p[data-test='recommendToFriend']",
                timeout=2,
            )
            .text.split("%")[0]
            .strip()
        )
        result["reviews_count"] = int(
            wait_for_element(
                self.driver, By.CSS_SELECTOR, "p[data-test='review-count']", timeout=2
            )
            .text.split()[0]
            .replace("(", "")
            .strip()
        )

        dirty_result = (
            wait_for_element(
                self.driver,
                By.CSS_SELECTOR,
                "div[data-test='industry-average-and-distribution']",
                timeout=2,
            )
            .find_element(By.CSS_SELECTOR, "div:first-child")
            .text.split("\n")
        )
        cleaned_result = [
            dirty_result[i] for i in range(len(dirty_result)) if i % 2 == 1
        ]
        cleaned_result = [
            float(element.strip().replace(",", ".")) for element in cleaned_result
        ]

        result["culture_and_values"] = cleaned_result[0]
        result["diversity_equity_inclusion"] = cleaned_result[1]
        result["work_life_balance"] = cleaned_result[2]
        result["senior_management"] = cleaned_result[3]
        result["compensation_and_benefits"] = cleaned_result[4]
        result["career_opportunities"] = cleaned_result[5]
        return result

    def _extract_review_data(self, review_element: WebElement) -> dict:  # noqa: C901
        """Extract review data from a review element"""
        data: dict[str, str | float | bool | None] = {
            "title": None,
            "rating": None,
            "date": None,
            "role": None,
            "is_current_employee": None,
            "employee_oldness": None,
            "pros": None,
            "cons": None,
            "does_recommend": None,
            "does_approve_ceo": None,
            "business_outlook": None,
            "advice_to_management": None,
        }

        try:
            # Extract title
            try:
                title_elem = review_element.find_element(
                    By.CSS_SELECTOR, "h3[data-test='review-details-title'] span"
                )
                data["title"] = title_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract rating
            try:
                rating_elem = review_element.find_element(
                    By.CSS_SELECTOR, "span[data-test='review-rating-label']"
                )
                data["rating"] = float(rating_elem.text.replace(",", "."))
            except NoSuchElementException:
                pass

            # Extract date
            try:
                date_elem = review_element.find_element(
                    By.CSS_SELECTOR, "span.timestamp_reviewDate__dsF9n"
                )
                data["date"] = date_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract role and employment status
            try:
                role_elem = review_element.find_element(
                    By.CSS_SELECTOR, "span.review-avatar_avatarLabel__P15ey"
                )
                data["role"] = role_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract employment status (current/former) and oldness
            try:
                status_elem = review_element.find_element(
                    By.CSS_SELECTOR,
                    "div[data-test='review-avatar-tag'] div.text-with-icon_LabelContainer__s0l4C",
                )
                status_text = status_elem.text.strip()

                # Check if current or former employee
                if "actuel" in status_text.lower() or "current" in status_text.lower():
                    data["is_current_employee"] = True
                elif "ancien" in status_text.lower() or "former" in status_text.lower():
                    data["is_current_employee"] = False

                # Extract employment duration (e.g., "plus de 3 an(s)" or "moins de 1 an")
                data["employee_oldness"] = status_text

            except NoSuchElementException:
                pass

            # Extract pros
            try:
                pros_elem = review_element.find_element(
                    By.CSS_SELECTOR, "span[data-test='review-text-PROS']"
                )
                data["pros"] = pros_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract cons
            try:
                cons_elem = review_element.find_element(
                    By.CSS_SELECTOR, "span[data-test='review-text-CONS']"
                )
                data["cons"] = cons_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract advice to management
            try:
                advice_elem = review_element.find_element(
                    By.CSS_SELECTOR, "span[data-test='review-text-FEEDBACK']"
                )
                data["advice_to_management"] = advice_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract recommendation, CEO approval, and business outlook
            experience_containers = review_element.find_elements(
                By.CSS_SELECTOR, "div.rating-icon_ratingContainer__9UoJ6"
            )

            for container in experience_containers:
                try:
                    label = (
                        container.find_element(By.TAG_NAME, "span").text.strip().lower()
                    )

                    # Check the style class to determine positive/negative/neutral/no data
                    classes = container.get_attribute("class")

                    if "recommande" in label or "recommend" in label:
                        if "positiveStyles" in classes:
                            data["does_recommend"] = True
                        elif "negativeStyles" in classes:
                            data["does_recommend"] = False
                        elif "noDataStyles" in classes or "neutralStyles" in classes:
                            data["does_recommend"] = None

                    elif "pdg" in label or "ceo" in label:
                        if "positiveStyles" in classes:
                            data["does_approve_ceo"] = True
                        elif "negativeStyles" in classes:
                            data["does_approve_ceo"] = False
                        elif "noDataStyles" in classes or "neutralStyles" in classes:
                            data["does_approve_ceo"] = None

                    elif (
                        "perspective" in label
                        or "outlook" in label
                        or "commerciale" in label
                    ):
                        if "positiveStyles" in classes:
                            data["business_outlook"] = "positive"
                        elif "negativeStyles" in classes:
                            data["business_outlook"] = "negative"
                        elif "neutralStyles" in classes:
                            data["business_outlook"] = "neutral"
                        elif "noDataStyles" in classes:
                            data["business_outlook"] = None

                except NoSuchElementException:
                    continue

        except Exception as e:
            logger.error(f"Error extracting review data: {e}")

        return data

    def extract_company_reviews(
        self,
        role: Optional[str] = None,
        location: Optional[str] = None,
        job_type: Optional[str] = None,
        max_reviews: int = -1,
    ) -> list[dict]:
        """Extract company reviews"""
        # TODO apply filters
        # #TODO extracting from multiple pages (now limited to first 10 reviews, 1 page)
        # TODO apply sort (by date, popularity)
        results: list[dict] = []
        if max_reviews == 0:
            return []
        review_elements = wait_for_element(
            self.driver, By.CSS_SELECTOR, "div[data-test='reviews-list']", timeout=2
        ).find_elements(By.TAG_NAME, "li")
        for review_element in review_elements:
            review_data = self._extract_review_data(review_element)
            if review_data:
                results.append(review_data)
        return results

    # TODO
    def extract_company_salaries(self) -> list[dict]:
        """Extract company salaries"""
        raise NotImplementedError

    # TODO
    def extract_company_interviews(self) -> list[dict]:
        """Extract company interviews"""
        raise NotImplementedError

    # TODO
    def extract_company_benefits(self) -> list[dict]:
        """Extract company benefits"""
        raise NotImplementedError

    def extract_company_page(self) -> dict:
        """Extract complete company page data"""
        raise NotImplementedError
        # TODO: Implement full company page extraction
        return {}
