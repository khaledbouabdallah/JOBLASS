from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from typing import Optional
from datetime import datetime

from joblass.utils.selenium_helpers import (
    human_delay,
    human_click,
    human_move,
    wait_for_element,
    clear_and_type
)

from joblass.utils.logger import setup_logger
from joblass.utils.control import control
from joblass.db import Job, JobRepository

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
    
    # TODO implement modal handling
    # In glassdoor, some modals popup randomly asking for preferences
    # ideally should be called if an action is blocked by a modal in a try-except block and with retry mechanism, maybe using a decorator
    def close_modal_if_present(self) -> bool:
        """
        Detect and close modal dialog if present

        Args:
            driver: Selenium WebDriver instance
            timeout: How long to wait for modal (seconds)

        Returns:
            True if modal was closed, False if no modal found
        """
        try:
            # Check if modal is present
            modal = wait_for_element(self.driver, By.CSS_SELECTOR, "dialog[aria-modal='true'][open]", timeout=1)
            logger.info("Modal detected")

            # Find close button
            close_button = modal.find_element(By.CSS_SELECTOR, "button[data-test*='modal-close']")

            human_delay(0.3, 0.6)
            human_click(self.driver, close_button)

            # Wait for modal to disappear
            wait_for_element(self.driver, By.CSS_SELECTOR, "dialog[aria-modal='true'][open]", timeout=1)

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
        **kwargs
    ) -> Optional[int]:
        """
        Save job to database with deduplication
        
        Args:
            title: Job title
            company: Company name
            location: Job location
            url: Job posting URL (used for deduplication)
            description: Job description (optional)
            **kwargs: Additional job fields (tech_stack, salary_min, etc.)
        
        Returns:
            Job ID if inserted, None if duplicate
        """
        # Check if job already exists
        if JobRepository.exists(url):
            logger.info(f"Job already in database: {url}")
            return None
        
        # Create Job object
        job = Job(
            title=title,
            company=company,
            location=location,
            url=url,
            source="glassdoor",
            description=description,
            scraped_date=datetime.now(),
            **kwargs
        )
        
        # Insert into database
        job_id = JobRepository.insert(job)
        
        if job_id:
            logger.info(f"Saved job to database: {title} at {company} (ID: {job_id})")
        
        return job_id
    
    def fill_search_form(
        self, 
        job_title: str, 
        location: str, 
        preferred_location: Optional[str] = None
    ) -> bool:
        """
        Fill Glassdoor search form with job title and location
        
        Args:
            job_title: Job title to search for
            location: Location to search in
            preferred_location: Specific text to match in dropdown (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Searching for '{job_title}' in '{location}'")
            
            # Wait for pause if needed
            control.wait_if_paused()
            control.check_should_stop()
            
            # Fill job title
            logger.info("Filling job title field")
            job_input = wait_for_element(self.driver, By.ID, "searchBar-jobTitle", timeout=3)
            human_move(self.driver, job_input)
            clear_and_type(job_input, job_title)
            human_delay(0.5, 1.0)
            
            # Fill location
            logger.info("Filling location field")
            location_input = wait_for_element(self.driver, By.ID, "searchBar-location", timeout=3)
            human_move(self.driver, location_input)
            clear_and_type(location_input, location)
            human_delay(1.0, 2.0)
            
            # Wait for suggestions dropdown
            logger.info("Waiting for location suggestions")
            suggestions_list = wait_for_element(
                self.driver, 
                By.ID, 
                "searchBar-location-search-suggestions",
                timeout=5
            )
            
            # Get all suggestion items
            suggestions = suggestions_list.find_elements(By.TAG_NAME, "li")
            
            if not suggestions:
                logger.warning("No location suggestions found")
                return False
            
            # Log all available suggestions
            logger.info(f"Found {len(suggestions)} location suggestions:")
            for idx, suggestion in enumerate(suggestions):
                logger.info(f"  [{idx}] {suggestion.text}")
            
            # Find matching suggestion
            target_text = preferred_location if preferred_location else location
            clicked = False
            
            for idx, suggestion in enumerate(suggestions):
                if target_text.lower() in suggestion.text.lower():
                    logger.info(f"Selecting suggestion [{idx}]: {suggestion.text}")
                    
                    # Check for pause before clicking
                    control.wait_if_paused()
                    control.check_should_stop()
                    
                    human_move(self.driver, suggestion)
                    human_delay(0.2, 0.5)
                    human_click(self.driver, suggestion)
                    clicked = True
                    logger.info("Location selected successfully")
                    break
            
            if not clicked:
                logger.error(f"Could not find suggestion matching '{target_text}'")
                logger.info("Available suggestions printed above. Adjust search term or use manual intervention.")
                return False
            
            human_delay(0,3, 0.7)
            return True
            
        except InterruptedError as e:
            logger.info(str(e))
            return False
            
        except Exception as e:
            logger.error(f"Error filling search form: {str(e)}", exc_info=True)
            return False
    
    
    
    def search_jobs(
        self, 
        job_title: str, 
        location: str, 
        preferred_location: Optional[str] = None
    ) -> bool:
        """
        Complete job search workflow
        
        Args:
            job_title: Job title to search
            location: Location to search in
            preferred_location: Specific location text to match
        
        Returns:
            True if search completed successfully
        """
        try:
            logger.info("=== Starting Glassdoor job search ===")
            
            # Navigate to homepage
            self.navigate_to_home()
            
            # Fill search form
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