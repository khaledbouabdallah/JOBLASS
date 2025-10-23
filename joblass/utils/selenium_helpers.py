import time
import random
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from joblass.utils.logger import setup_logger
from joblass.utils.control import control

logger = setup_logger(__name__)


def human_delay(min_sec: float = 0.3, max_sec: float = 0.8):
    """Random delay to simulate human timing"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(element: WebElement, text: str, min_delay: float = 0.05, max_delay: float = 0.2):
    """
    Type text with human-like delays between characters
    
    Args:
        element: WebElement to type into
        text: Text to type
        min_delay: Minimum delay between characters
        max_delay: Maximum delay between characters
    """
    for char in text:
        control.check_should_stop()
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))
    
    logger.debug(f"Typed: {text}")


def human_click(driver: WebDriver, element: WebElement):
    """
    Click element with human-like mouse movement
    
    Args:
        driver: Selenium WebDriver instance
        element: WebElement to click
    """
    control.check_should_stop()
    tag_name = element.tag_name
    actions = ActionChains(driver)
    actions.move_to_element(element)
    actions.pause(random.uniform(0.2, 0.5))
    actions.click()
    actions.perform()
    
    human_delay(0.2, 0.5)
    logger.debug(f"Clicked element: {tag_name}")


def human_move(driver: WebDriver, element: WebElement):
    """
    Move mouse to element with human-like behavior
    
    Args:
        driver: Selenium WebDriver instance
        element: WebElement to move to
    """
    actions = ActionChains(driver)
    actions.move_to_element(element)
    actions.pause(random.uniform(0.3, 0.7))
    actions.perform()
    
    logger.debug(f"Moved to element: {element.tag_name}")


def wait_for_element(driver: WebDriver, by: By, value: str, timeout: int = 10) -> WebElement:
    """
    Wait for element to be present and return it
    
    Args:
        driver: Selenium WebDriver instance
        by: Locator strategy (By.ID, By.CSS_SELECTOR, etc.)
        value: Locator value
        timeout: Maximum wait time in seconds
    
    Returns:
        WebElement when found
    
    Raises:
        TimeoutException if element not found
    """
    wait = WebDriverWait(driver, timeout)
    element = wait.until(EC.presence_of_element_located((by, value)))
    logger.debug(f"Found element: {by}={value}")
    return element


def wait_for_clickable(driver: WebDriver, by: By, value: str, timeout: int = 10) -> WebElement:
    """
    Wait for element to be clickable and return it
    
    Args:
        driver: Selenium WebDriver instance
        by: Locator strategy
        value: Locator value
        timeout: Maximum wait time in seconds
    
    Returns:
        WebElement when clickable
    """
    wait = WebDriverWait(driver, timeout)
    element = wait.until(EC.element_to_be_clickable((by, value)))
    logger.debug(f"Element clickable: {by}={value}")
    return element


def scroll_to_element(driver: WebDriver, element: WebElement):
    """
    Scroll element into view smoothly
    
    Args:
        driver: Selenium WebDriver instance
        element: WebElement to scroll to
    """
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
    human_delay(0.5, 1.0)
    logger.debug("Scrolled to element")


def clear_and_type(element: WebElement, text: str):
    """
    Clear input field and type text with human-like behavior
    
    Args:
        element: Input WebElement
        text: Text to type
    """
    element.clear()
    human_delay(0.2, 0.4)
    human_type(element, text)