"""Job search workflow orchestration"""

from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver

from joblass.db import (
    JobRepository,
    SearchCriteria,
    SearchSession,
    SearchSessionRepository,
)
from joblass.scrapers.glassdoor import ExtraFilters, GlassdoorScraper
from joblass.utils.control import control
from joblass.utils.logger import setup_logger

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
            logger.info(f"Filter options loaded: {list(self.available_filters.keys())}")

        return jobs_found

    def apply_advanced_filters(self, filters: dict) -> None:
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

        logger.info("Applying advanced filters...")
        self.filters._open_dropdown()
        self.filters.apply_filters(filters)
        self.filters.validate_and_close()
        logger.info("Advanced filters applied")

    def scrape_jobs(
        self,
        jobs_found: int,
        max_jobs: Optional[int] = None,
        skip_until: Optional[int] = None,
    ) -> list:
        """
        Scrape job listings from search results.

        Args:
            jobs_found: Total number of jobs found in search
            max_jobs: Maximum number of jobs to scrape (None = all)
            skip_until: Skip to specific job index (for resume)

        Returns:
            list: List of validated ScrapedJobData instances
        """
        if not jobs_found:
            logger.warning("No jobs to scrape")
            return []

        logger.info(f"Starting scrape of up to {max_jobs or jobs_found} jobs")
        scraped_jobs = self.scraper.search_jobs(
            jobs_found=jobs_found, max_jobs=max_jobs, skip_until=skip_until
        )

        if not scraped_jobs or scraped_jobs is False:
            logger.warning("No jobs scraped")
            return []

        return scraped_jobs

    def save_jobs_to_db(
        self, scraped_jobs: list, session_id: Optional[int] = None
    ) -> dict[str, int]:
        """
        Save scraped jobs to database with deduplication.

        Args:
            scraped_jobs: List of validated ScrapedJobData instances
            session_id: Optional session ID to link jobs to

        Returns:
            dict: Statistics with keys 'saved' and 'skipped'
        """
        stats = {"saved": 0, "skipped": 0}

        if not scraped_jobs:
            return stats

        logger.info(f"Saving {len(scraped_jobs)} jobs to database...")
        for job_data in scraped_jobs:
            control.wait_if_paused()
            control.check_should_stop()

            # Check if already exists (logs info automatically)
            if JobRepository.exists(job_data.url):
                stats["skipped"] += 1
                logger.debug(f"Skipping duplicate: {job_data.url}")
                continue

            # Save new job with session_id
            job_id = self.scraper.save_job_from_validated_data(
                job_data, session_id=session_id
            )
            if job_id:
                stats["saved"] += 1

        logger.info(
            f"Database save complete: {stats['saved']}/{len(scraped_jobs)} "
            f"jobs saved ({stats['skipped']} duplicates)"
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
    ) -> dict[str, int]:
        """
        Run complete job search workflow (search -> filter -> scrape -> save).
        Creates and tracks a SearchSession in the database.

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
        stats = {
            "jobs_found": 0,
            "jobs_scraped": 0,
            "jobs_saved": 0,
            "jobs_skipped": 0,
            "session_id": None,
        }

        # Create SearchCriteria from inputs
        search_criteria = SearchCriteria(
            job_title=job_title,
            location=location,
            preferred_location=preferred_location,
            **(advanced_filters or {}),
        )

        # Create initial SearchSession
        self.current_session = SearchSession(
            search_criteria=search_criteria, source=self.source, status="in_progress"
        )

        try:
            # Save session to database
            session_id = SearchSessionRepository.insert(self.current_session)
            if not session_id:
                logger.error("Failed to create search session in database")
                return stats

            self.current_session.id = session_id
            stats["session_id"] = session_id
            logger.info(f"Created search session (ID: {session_id})")

            # 1. Fill search form and initialize filters
            jobs_found = self.fill_search_form(job_title, location, preferred_location)
            stats["jobs_found"] = jobs_found
            self.current_session.jobs_found = jobs_found

            if not jobs_found:
                logger.warning("No jobs found, marking session as completed")
                self.current_session.mark_completed(0, 0, 0)
                SearchSessionRepository.update(self.current_session)
                return stats

            # 2. Apply advanced filters if provided
            if advanced_filters:
                self.apply_advanced_filters(advanced_filters)
            else:
                logger.info("No advanced filters to apply")
                self.filters._close_dropdown()

            # 3. Scrape jobs
            scraped_jobs = self.scrape_jobs(jobs_found, max_jobs, skip_until)
            stats["jobs_scraped"] = len(scraped_jobs)

            # 4. Save jobs to database with session_id
            save_stats = self.save_jobs_to_db(scraped_jobs, session_id=session_id)
            stats["jobs_saved"] = save_stats["saved"]
            stats["jobs_skipped"] = save_stats["skipped"]

            # 5. Mark session as completed
            self.current_session.mark_completed(
                jobs_scraped=stats["jobs_scraped"],
                jobs_saved=stats["jobs_saved"],
                jobs_skipped=stats["jobs_skipped"],
            )
            SearchSessionRepository.update(self.current_session)

            logger.info(
                f"=== Workflow complete (Session {session_id}): "
                f"{stats['jobs_saved']}/{stats['jobs_scraped']} "
                f"jobs saved ({stats['jobs_skipped']} duplicates) ==="
            )
            return stats

        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)

            # Mark session as failed
            if self.current_session and self.current_session.id:
                self.current_session.mark_failed(str(e))
                SearchSessionRepository.update(self.current_session)
                logger.info(
                    f"Marked session {self.current_session.id} as failed: {str(e)}"
                )

            return stats
