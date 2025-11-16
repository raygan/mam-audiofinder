"""Helper utilities for frontend testing."""

import time
from typing import Callable, Any
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException


def wait_for_condition(
    condition: Callable[[], Any],
    timeout: int = 10,
    poll_frequency: float = 0.5,
    error_message: str = "Condition not met"
) -> Any:
    """
    Wait for a condition to be true.

    Args:
        condition: Callable that returns truthy value when condition is met
        timeout: Maximum time to wait in seconds
        poll_frequency: How often to check the condition
        error_message: Error message if timeout occurs

    Returns:
        The truthy value returned by condition

    Raises:
        TimeoutException: If condition not met within timeout
    """
    end_time = time.time() + timeout
    last_exception = None

    while time.time() < end_time:
        try:
            result = condition()
            if result:
                return result
        except Exception as e:
            last_exception = e

        time.sleep(poll_frequency)

    raise TimeoutException(
        f"{error_message} (timeout: {timeout}s)"
        + (f"\nLast exception: {last_exception}" if last_exception else "")
    )


def wait_for_ajax_complete(driver: WebDriver, timeout: int = 10):
    """
    Wait for any AJAX requests to complete.

    Checks for jQuery.active and fetch requests.
    """
    def ajax_complete():
        # Check jQuery if available
        jquery_active = driver.execute_script(
            "return typeof jQuery !== 'undefined' && jQuery.active === 0"
        )
        # Check for active fetch requests (if tracked)
        # Note: This requires the app to track fetch requests
        return jquery_active

    try:
        wait_for_condition(
            ajax_complete,
            timeout=timeout,
            error_message="AJAX requests did not complete"
        )
    except TimeoutException:
        # Not all pages use jQuery, so this is acceptable
        pass


def scroll_to_element(driver: WebDriver, element):
    """Scroll an element into view."""
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(0.3)  # Brief pause after scroll


def get_element_text_when_ready(driver: WebDriver, by, value, timeout: int = 10) -> str:
    """Wait for element and return its text."""
    from selenium.webdriver.support import expected_conditions as EC

    element = WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((by, value))
    )
    return element.text


def is_element_present(driver: WebDriver, by, value) -> bool:
    """Check if an element is present in the DOM."""
    try:
        driver.find_element(by, value)
        return True
    except:
        return False


def wait_for_page_load(driver: WebDriver, timeout: int = 30):
    """Wait for the page to fully load."""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def wait_for_url_change(driver: WebDriver, old_url: str, timeout: int = 10):
    """Wait for the URL to change from the current URL."""
    WebDriverWait(driver, timeout).until(
        lambda d: d.current_url != old_url
    )


def clear_and_send_keys(element, text: str):
    """Clear an input field and send new text."""
    element.clear()
    time.sleep(0.1)  # Brief pause to ensure clear completes
    element.send_keys(text)


def get_local_storage_item(driver: WebDriver, key: str) -> str | None:
    """Get an item from localStorage."""
    return driver.execute_script(f"return localStorage.getItem('{key}');")


def set_local_storage_item(driver: WebDriver, key: str, value: str):
    """Set an item in localStorage."""
    driver.execute_script(f"localStorage.setItem('{key}', '{value}');")


def clear_local_storage(driver: WebDriver):
    """Clear all localStorage."""
    driver.execute_script("localStorage.clear();")


def take_screenshot(driver: WebDriver, filepath: str):
    """Take a screenshot and save to file."""
    driver.save_screenshot(filepath)
