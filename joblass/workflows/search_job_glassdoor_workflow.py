"""Job search workflow orchestration"""

from typing import List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from joblass.db import (
    CompanyRepository,
    JobRepository,
    ScrapedCompanyFromJobPosting,
    ScrapedJobData,
    SearchCriteria,
    SearchSession,
    SearchSessionRepository,
)
from joblass.scrapers.glassdoor import ExtraFilters, GlassdoorScraper
from joblass.utils.control import control
from joblass.utils.logger import setup_logger
from joblass.utils.selenium_helpers import wait_for_element

logger = setup_logger(__name__)


class JobSearchWorkflow:
    """Orchestrates the complete job search and scraping workflow"""

    def __init__(self, driver: WebDriver, source: str = "glassdoor"):
        self.driver = driver
        self.scraper = GlassdoorScraper(driver)
        self.filters: Optional[ExtraFilters] = None
        self.available_filters: Optional[dict[str, list[str]]] = None
        self.source = source
        self.current_session: Optional[SearchSession] = None

    def get_available_filters(self) -> dict[str, list[str]]:
        """
        Get available filter options after performing a search.
        Must be called after fill_search_form() to get dynamic options.

        Returns:
            dict: Available filter options with keys matching filter names
                 Example: {
                     "company_rating": ["+1", "+2", "+3", "+4"],
                     "date_posted": ["24 heures", "3 jours", "7 jours", "14 jours"],
                     "job_type": ["Temps plein", "Temps partiel", "Stage", ...],
                     ...
                 }

        Raises:
            RuntimeError: If called before fill_search_form()
        """
        if self.filters is None:
            raise RuntimeError(
                "Filters not initialized. Call fill_search_form() first to get available options."
            )

        return self.filters.accordions_choice_options

    def fill_search_form(
        self, job_title: str, location: str, preferred_location: Optional[str] = None
    ) -> int:
        """
        Fill search form and initialize filters.
        After this, call get_available_filters() to see dynamic filter options.

        Args:
            job_title: Job search query
            location: Location to search in
            preferred_location: Specific location to select from suggestions

        Returns:
            int: Number of jobs found
        """
        logger.info("=== Starting job search ===")
        self.scraper.navigate_to_home()

        jobs_found = self.scraper.fill_search_form(
            job_title, location, preferred_location
        )

        if jobs_found:
            # Initialize filters to get available options
            logger.info("Initializing filter options...")
            self.filters = ExtraFilters(self.driver)
            self.available_filters = self.filters.accordions_choice_options
            # Close the filter dropdown after getting options
            # self.filters._close_dropdown()
            if self.available_filters:
                logger.info(
                    f"Filter options loaded: {list(self.available_filters.keys())}"
                )

        return jobs_found

    def apply_advanced_filters(self, filters: dict) -> int:
        """
        Apply advanced filters to search results.
        Must be called after fill_search_form().

        Args:
            filters: Dict of filter name -> value pairs
                    Example: {
                        "is_easy_apply": True,
                        "is_remote": False,
                        "date_posted": "7 jours",
                        "job_type": "Stage",
                        "company_rating": "+3",
                        "salary_range": (30000, 50000),
                    }

        Raises:
            RuntimeError: If called before fill_search_form()
        """
        if self.filters is None:
            raise RuntimeError(
                "Filters not initialized. Call fill_search_form() first."
            )

        try:
            logger.info("Applying advanced filters...")
            self.filters._open_dropdown()
            self.filters.apply_filters(filters)
            self.filters.validate_and_close()
            logger.info("Advanced filters applied")
        except Exception as e:
            logger.error(f"Error applying advanced filters: {e}")
            self.filters.clear_button.click()
            self.filters._close_dropdown()
            raise e

        # Wait for results to refresh
        _ = wait_for_element(
            self.driver, By.CSS_SELECTOR, "li[data-test='jobListing']", timeout=5
        )

        return self.scraper.get_jobs_found_count()

    def scrape_jobs(
        self,
        jobs_found: int,
        max_jobs: Optional[int] = None,
        skip_until: Optional[int] = None,
    ) -> tuple[List[ScrapedJobData], List[ScrapedCompanyFromJobPosting]]:
        """
        Scrape job listings and company data from search results.

        Args:
            jobs_found: Total number of jobs found in search
            max_jobs: Maximum number of jobs to scrape (None = all)
            skip_until: Skip to specific job index (for resume)

        Returns:
            tuple: (list of ScrapedJobData, list of ScrapedCompanyFromJobPosting)
        """
        if not jobs_found:
            logger.warning("No jobs to scrape")
            return [], []

        logger.info(f"Starting scrape of up to {max_jobs or jobs_found} jobs")
        scraped_jobs, scraped_companies = self.scraper.search_jobs(
            jobs_found=jobs_found, max_jobs=max_jobs, skip_until=skip_until
        )

        # search_jobs returns empty lists on no results or interruption
        if not scraped_jobs:
            logger.warning("No jobs scraped")
            return [], []

        logger.info(
            f"Scraped {len(scraped_jobs)} jobs with {len(scraped_companies)} company records"
        )
        return scraped_jobs, scraped_companies

    def save_companies_to_db(
        self, scraped_companies: List[ScrapedCompanyFromJobPosting]
    ) -> dict[str, int]:
        """
        Save/upsert scraped companies to database.
        Returns a mapping of company names to their IDs for linking jobs.

        Args:
            scraped_companies: List of validated ScrapedCompanyFromJobPosting instances

        Returns:
            dict: Company name -> company ID mapping
        """
        company_map: dict[str, int] = {}

        if not scraped_companies:
            return company_map

        logger.info(f"Saving {len(scraped_companies)} companies to database...")

        for company_data in scraped_companies:
            control.wait_if_paused()
            control.check_should_stop()

            try:
                # Convert to Company model and upsert
                company_model = company_data.to_company_model()
                company_id = CompanyRepository.upsert(company_model)

                if company_id:
                    company_map[company_data.company_name] = company_id
                else:
                    logger.warning(
                        f"Failed to upsert company: {company_data.company_name}"
                    )
            except Exception as e:
                logger.error(
                    f"Error saving company {company_data.company_name}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Company save complete: {len(company_map)}/{len(scraped_companies)} companies saved/updated"
        )
        return company_map

    def save_jobs_to_db(
        self,
        scraped_jobs: List[ScrapedJobData],
        company_map: dict[str, int],
        session_id: Optional[int] = None,
    ) -> dict[str, int]:
        """
        Save scraped jobs to database with URL-based deduplication and company linking.

        Args:
            scraped_jobs: List of validated ScrapedJobData instances
            company_map: Mapping of company names to company IDs (from save_companies_to_db)
            session_id: Optional session ID to link jobs to

        Returns:
            dict: Statistics with keys 'saved' and 'skipped' and 'failed'

        Note:
            Deduplication is handled by JobRepository.insert() which checks
            for duplicate URLs before inserting. Returns None for duplicates.
        """
        stats = {"saved": 0, "skipped": 0, "failed": 0}

        if not scraped_jobs:
            return stats

        logger.info(f"Saving {len(scraped_jobs)} jobs to database...")
        for job_data in scraped_jobs:
            control.wait_if_paused()
            control.check_should_stop()

            try:
                # Get company_id from map (case-sensitive match for now)
                company_id = company_map.get(job_data.company)

                # Convert to Job model with company_id link
                job_model = job_data.to_job_model(
                    session_id=session_id, company_id=company_id
                )

                # Save job (deduplication handled internally by JobRepository)
                job_id = JobRepository.insert(job_model)

                if job_id:
                    stats["saved"] += 1
                    logger.debug(
                        f"✓ Saved job: {job_data.job_title} at {job_data.company} "
                        f"(ID: {job_id}, company_id: {company_id})"
                    )
                else:
                    # job_id is None means duplicate or save failed
                    stats["skipped"] += 1
            except Exception as e:
                logger.error(
                    f"Error saving job {job_data.job_title} at {job_data.company}: {e}",
                    exc_info=True,
                )
                stats["failed"] += 1

        logger.info(
            f"Database save complete: {stats['saved']}/{len(scraped_jobs)} "
            f"jobs saved ({stats['skipped']} duplicates, {stats['failed']} failed)"
        )
        return stats

    def run(
        self,
        job_title: str,
        location: str,
        preferred_location: Optional[str] = None,
        max_jobs: Optional[int] = None,
        skip_until: Optional[int] = None,
        advanced_filters: Optional[dict] = None,
    ) -> tuple[
        dict[str, int], List[ScrapedJobData], List[ScrapedCompanyFromJobPosting]
    ]:
        """
        Run complete job search workflow (search -> filter -> scrape -> save).
        Creates and tracks a SearchSession in the database.

        This is a convenience method that combines start_search() and complete_search()
        for non-interactive workflows where filters are known upfront.

        Args:
            job_title: Job search query
            location: Location to search in
            preferred_location: Specific location to select from suggestions
            max_jobs: Maximum number of jobs to scrape (None = all)
            skip_until: Skip to specific job index (for resume)
            advanced_filters: Dict of advanced filters to apply

        Returns:
            dict: Statistics (jobs_found, jobs_scraped, jobs_saved, jobs_skipped, session_id)

        Example:
            workflow = JobSearchWorkflow(driver)
            stats = workflow.run(
                job_title="Machine Learning Intern",
                location="Paris",
                preferred_location="Île-de-France",
                max_jobs=50,
                advanced_filters={
                    "is_easy_apply": True,
                    "date_posted": "7 jours",
                    "job_type": "Stage"
                }
            )
        """
        # Phase 1: Initial search
        search_result = self.start_search(job_title, location, preferred_location)

        # If no jobs found, return early
        if not search_result["jobs_found"]:
            return (
                {
                    "jobs_found": 0,
                    "jobs_scraped": 0,
                    "jobs_saved": 0,
                    "jobs_skipped": 0,
                    "session_id": search_result["session_id"],
                },
                [],
                [],
            )

        # Phase 2: Complete search with filters (returns tuple)
        stats, scraped_jobs, scraped_companies = self.complete_search(
            advanced_filters=advanced_filters, max_jobs=max_jobs, skip_until=skip_until
        )
        return stats, scraped_jobs, scraped_companies

    def start_search(
        self,
        job_title: str,
        location: str,
        preferred_location: Optional[str] = None,
    ) -> dict:
        """
        Phase 1: Perform initial search and return available filter options.
        Creates a SearchSession and waits for user to decide on advanced filters.

        Args:
            job_title: Job search query
            location: Location to search in
            preferred_location: Specific location to select from suggestions

        Returns:
            dict: {
                "jobs_found": int,
                "session_id": int,
                "available_filters": dict[str, list[str]],
                "search_criteria": SearchCriteria
            }

        Example:
            workflow = JobSearchWorkflow(driver)
            result = workflow.start_search(
                job_title="Machine Learning Intern",
                location="Paris",
                preferred_location="Île-de-France"
            )
            print(f"Found {result['jobs_found']} jobs")
            print(f"Available filters: {result['available_filters']}")
        """
        # Create initial SearchCriteria (no advanced filters yet)
        search_criteria = SearchCriteria.model_validate(
            {
                "job_title": job_title,
                "location": location,
                "preferred_location": preferred_location,
            }
        )

        # Create SearchSession
        self.current_session = SearchSession(
            search_criteria=search_criteria,
            source=self.source,
            status="in_progress",
        )

        # Save session to database
        session_id = SearchSessionRepository.insert(self.current_session)
        if not session_id:
            logger.error("Failed to create search session in database")
            return {
                "jobs_found": 0,
                "session_id": 0,
                "available_filters": {},
                "search_criteria": search_criteria,
            }

        self.current_session.id = session_id
        logger.info(f"Created search session (ID: {session_id})")

        # Fill search form and get available filters
        jobs_found = self.fill_search_form(job_title, location, preferred_location)
        self.current_session.jobs_found = jobs_found
        SearchSessionRepository.update(self.current_session)

        if not jobs_found:
            logger.warning("No jobs found")
            self.current_session.mark_completed(0, 0, 0)
            SearchSessionRepository.update(self.current_session)

        return {
            "jobs_found": jobs_found,
            "session_id": session_id,
            "available_filters": self.available_filters or {},
            "search_criteria": search_criteria,
        }

    def complete_search(
        self,
        advanced_filters: Optional[dict] = None,
        max_jobs: Optional[int] = None,
        skip_until: Optional[int] = None,
    ) -> tuple[
        dict[str, int], List[ScrapedJobData], List[ScrapedCompanyFromJobPosting]
    ]:
        """
        Phase 2: Apply user-selected filters and complete the scraping workflow.
        Must be called after start_search().

        Args:
            advanced_filters: Dict of advanced filters to apply (or None to skip)
            max_jobs: Maximum number of jobs to scrape (None = all)
            skip_until: Skip to specific job index (for resume)

        Returns:
            tuple: (
                stats dict (jobs_found, jobs_scraped, jobs_saved, jobs_skipped, session_id),
                list of ScrapedJobData,
                list of ScrapedCompanyFromJobPosting
            )

        Raises:
            RuntimeError: If called before start_search() or if session doesn't exist

        Example:
            # Phase 1: Initial search
            workflow = JobSearchWorkflow(driver)
            result = workflow.start_search(
                job_title="Machine Learning Intern",
                location="Paris"
            )

            # User reviews available_filters and decides what to apply
            print(f"Available filters: {result['available_filters']}")

            # Phase 2: Apply filters and complete scraping
            stats = workflow.complete_search(
                advanced_filters={
                    "is_easy_apply": True,
                    "date_posted": "7 jours",
                    "job_type": "Stage"
                },
                max_jobs=50
            )
        """
        if self.current_session is None or self.current_session.id is None:
            raise RuntimeError(
                "No active session. Call start_search() first to initialize the workflow."
            )

        stats = {
            "jobs_found": self.current_session.jobs_found or 0,
            "jobs_scraped": 0,
            "jobs_saved": 0,
            "jobs_skipped": 0,
            "session_id": self.current_session.id,
        }

        # Initialize to empty lists to avoid UnboundLocalError in exception handler
        scraped_jobs: List[ScrapedJobData] = []
        scraped_companies: List[ScrapedCompanyFromJobPosting] = []

        try:
            # Check if there are jobs to scrape
            if not stats["jobs_found"]:
                logger.warning("No jobs to scrape from initial search")
                return stats, [], []

            # 1. Apply advanced filters if provided
            if advanced_filters:
                # Update search criteria using Pydantic's model_copy to avoid
                # calling the constructor with many optional fields (mypy-safe).
                current_criteria = self.current_session.get_search_criteria()
                # model_copy(update=...) returns a new SearchCriteria with updated fields
                updated_criteria = current_criteria.model_copy(
                    update=(advanced_filters or {})
                )
                self.current_session.update_search_criteria(updated_criteria)
                SearchSessionRepository.update(self.current_session)

                # Apply filters in browser
                jobs_found_after_filter = self.apply_advanced_filters(advanced_filters)
                stats["jobs_found"] = jobs_found_after_filter
                self.current_session.jobs_found = jobs_found_after_filter
                SearchSessionRepository.update(self.current_session)
            else:
                logger.info("No advanced filters to apply")
                # Only close dropdown if filters object exists
                if self.filters is not None:
                    self.filters._close_dropdown()

            # 2. Scrape jobs and companies
            scraped_jobs, scraped_companies = self.scrape_jobs(
                stats["jobs_found"], max_jobs, skip_until
            )
            stats["jobs_scraped"] = len(scraped_jobs)

            # 3. Save companies first (upsert), then save jobs with company links
            logger.info("Saving companies to database...")
            company_map = self.save_companies_to_db(scraped_companies)

            logger.info("Saving jobs to database with company links...")
            save_stats = self.save_jobs_to_db(
                scraped_jobs, company_map, session_id=self.current_session.id
            )
            stats["jobs_saved"] = save_stats["saved"]
            stats["jobs_skipped"] = save_stats["skipped"]

            # 4. Mark session as completed
            self.current_session.mark_completed(
                jobs_scraped=stats["jobs_scraped"],
                jobs_saved=stats["jobs_saved"],
                jobs_skipped=stats["jobs_skipped"],
            )
            SearchSessionRepository.update(self.current_session)

            logger.info(
                f"=== Workflow complete (Session {self.current_session.id}): "
                f"{stats['jobs_saved']}/{stats['jobs_scraped']} "
                f"jobs saved ({stats['jobs_skipped']} duplicates) ==="
            )
            return stats, scraped_jobs, scraped_companies

        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)

            # Mark session as failed
            if self.current_session and self.current_session.id:
                self.current_session.mark_failed(str(e))
                SearchSessionRepository.update(self.current_session)
                logger.info(
                    f"Marked session {self.current_session.id} as failed: {str(e)}"
                )

            return stats, scraped_jobs, scraped_companies
