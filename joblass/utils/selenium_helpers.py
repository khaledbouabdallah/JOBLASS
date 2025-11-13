import random
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from joblass.utils.control import control
from joblass.utils.logger import setup_logger

logger = setup_logger(__name__)


def human_delay(min_sec: float = 0.3, max_sec: float = 0.8):
    """Random delay to simulate human timing"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(
    element: WebElement, text: str, min_delay: float = 0.05, max_delay: float = 0.2
):
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


def wait_for_element(
    driver: WebDriver, by: By, value: str, timeout: int = 10
) -> WebElement:
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


def wait_for_clickable(
    driver: WebDriver, by: By, value: str, timeout: int = 10
) -> WebElement:
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
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element
    )
    human_delay(0.5, 1.0)
    logger.debug("Scrolled to element")


def clear_and_type(element: WebElement, action: ActionChains, text: str):
    """
    Clear input field and type text with human-like behavior

    This function attempts several strategies to ensure the field is cleared:
    1. Click the element to focus.
    2. Use element.clear().
    3. Send Ctrl+A (select all) and Delete to remove any content.
    4. Fallback to JS to clear .value and .innerText for stubborn cases.
    Finally, it types the provided text using human_type.

    Args:
        element: Input WebElement
        text: Text to type
    """

    # Focus the element first
    element.click()
    human_delay(0.05, 0.15)
    # Try select-all + delete (works for many input fields)

    action.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
    human_delay(0.02, 0.05)
    action.send_keys(Keys.DELETE).perform()

    human_delay(0.1, 0.2)
    human_type(element, text)


def human_scroll_to_element(driver: WebDriver, element: WebElement):
    driver.execute_script(
        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element
    )
    human_delay(0.3, 0.7)


def highlight(element, duration=2, color="yellow", border="3px solid green"):
    """Highlight element asynchronously so Selenium can continue working."""
    driver = element._parent
    # original_style = element.get_attribute("style")
    highlight_style = f"background: {color}; border: {border};"

    # Apply highlight immediately
    driver.execute_script(
        "arguments[0].setAttribute('style', arguments[1]);", element, highlight_style
    )

    # # Define a background function to restore style later
    # def restore():
    #     time.sleep(duration)
    #     try:
    #         driver.execute_script("arguments[0].setAttribute('style', arguments[1]);", element, original_style)
    #     except Exception:
    #         # Element might be gone or page changed
    #         pass


def safe_browser_tab_switch(driver: WebDriver, index: int = -1):
    driver.switch_to.window(driver.window_handles[index])
    # wait for page to load
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


# TODO: improve scrolling logic to detect end of scroll
def scroll_until_visible(
    driver,
    scroll_container,
    target_selector,
    step=300,
    timeout=10,
    continuous=True,
):
    """
    Scrolls inside a container to make a target element visible.

    Args:
        driver: Selenium WebDriver instance.
        scroll_container: The scrollable WebElement.
        target_selector: CSS selector string of the target element to find.
        step: Pixels to scroll per iteration.
        delay: Wait time (seconds) between scrolls.
        timeout: Max time (seconds) before stopping (only used if continuous=True).
        continuous:
            - True → keep scrolling until visible or timeout.
            - False → scroll once and return True/False immediately.

    Returns:
        The target WebElement if found and visible, otherwise None.
    """

    def is_visible():
        try:
            el = driver.find_element("css selector", target_selector)
            if el.is_displayed():
                return el
        except NoSuchElementException:
            pass
        return None

    # --- Single scroll mode ---
    if not continuous:
        driver.execute_script(f"arguments[0].scrollBy(0, {step});", scroll_container)
        delay = random.uniform(0.3, 1.0)
        time.sleep(delay)
        el = is_visible()
        return el

    # --- Continuous scroll mode ---
    start_time = time.time()
    while True:
        # Timeout
        if time.time() - start_time > timeout:
            print("⏱️ Timeout reached (target not found).")
            return None

        # Check if visible
        el = is_visible()
        if el:
            return el

        # Scroll and wait
        driver.execute_script(f"arguments[0].scrollBy(0, {step});", scroll_container)
        delay = random.uniform(0.3, 1.0)
        time.sleep(delay)


def wait_page_loaded(driver: WebDriver, timeout: int = 5):
    """
    Wait until the page is fully loaded

    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum wait time in seconds
    """
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def text_has_changed(locator, old_text):
    def _predicate(driver):
        try:
            return driver.find_element(*locator).text != old_text
        except:  # noqa: E722
            return False

    return _predicate


def safe_find_element(
    driver: WebDriver, by: By, value: str, timeout: int = 10
) -> WebElement:
    """
    Safely find an element, returning None if not found within timeout

    Args:
        driver: Selenium WebDriver instance
        by: Locator strategy (By.ID, By.CSS_SELECTOR, etc.)
        value: Locator value
        timeout: Maximum wait time in seconds
    """
    try:
        element = driver.find_element(by, value)
        return element
    except NoSuchElementException:
        logger.warning(f"Element not found: {by}={value}")
        return None
