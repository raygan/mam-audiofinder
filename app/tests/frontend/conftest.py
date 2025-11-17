"""Pytest configuration and fixtures for frontend Selenium tests."""

import os
import time
from typing import Generator
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager


# Configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8008")
SELENIUM_HUB = os.getenv("SELENIUM_HUB", None)  # e.g., http://localhost:4444
BROWSER = os.getenv("BROWSER", "chrome")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
IMPLICIT_WAIT = 10  # seconds
PAGE_LOAD_TIMEOUT = 30  # seconds
SCREENSHOT_DIR = Path("test-results/screenshots")


def pytest_addoption(parser):
    """Add custom command line options for Selenium tests."""
    parser.addoption(
        "--browser",
        action="store",
        default=BROWSER,
        help="Browser to use for tests: chrome, firefox",
    )
    parser.addoption(
        "--headless",
        action="store",
        default=str(HEADLESS),
        help="Run browser in headless mode: true, false",
    )
    parser.addoption(
        "--selenium-hub",
        action="store",
        default=SELENIUM_HUB,
        help="Selenium Grid hub URL (if using remote WebDriver)",
    )
    # Note: --base-url is provided by pytest-base-url plugin (dependency of pytest-selenium)
    # We read it in browser_config fixture to maintain compatibility


@pytest.fixture(scope="session")
def browser_config(request):
    """Get browser configuration from command line options."""
    # --base-url is provided by pytest-base-url plugin
    # Use it if available, otherwise fall back to our default
    try:
        base_url = request.config.getoption("--base-url")
    except ValueError:
        base_url = BASE_URL

    return {
        "browser": request.config.getoption("--browser"),
        "headless": request.config.getoption("--headless").lower() == "true",
        "selenium_hub": request.config.getoption("--selenium-hub"),
        "base_url": base_url or BASE_URL,
    }


@pytest.fixture(scope="function")
def driver(browser_config, request) -> Generator[webdriver.Remote, None, None]:
    """
    Create and configure a WebDriver instance.

    Supports both local and remote (Selenium Grid) execution.
    Automatically captures screenshots on test failure.
    """
    browser_name = browser_config["browser"]
    headless = browser_config["headless"]
    selenium_hub = browser_config["selenium_hub"]

    # Create screenshot directory
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    driver_instance = None

    try:
        if selenium_hub:
            # Remote WebDriver (Selenium Grid)
            driver_instance = _create_remote_driver(selenium_hub, browser_name, headless)
        else:
            # Local WebDriver
            driver_instance = _create_local_driver(browser_name, headless)

        # Configure timeouts
        driver_instance.implicitly_wait(IMPLICIT_WAIT)
        driver_instance.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

        # Maximize window (unless headless)
        if not headless:
            driver_instance.maximize_window()
        else:
            driver_instance.set_window_size(1920, 1080)

        yield driver_instance

    finally:
        # Capture screenshot on failure
        if request.node.rep_call.failed if hasattr(request.node, 'rep_call') else False:
            _capture_screenshot(driver_instance, request.node.name)

        # Cleanup
        if driver_instance:
            driver_instance.quit()


def _create_local_driver(browser_name: str, headless: bool) -> webdriver.Remote:
    """Create a local WebDriver instance."""
    if browser_name == "chrome":
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Check if running in container with system chromium
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
        if chromedriver_path and os.path.exists(chromedriver_path):
            # Use system-installed chromedriver (container mode)
            chrome_bin = os.getenv("CHROME_BIN")
            if chrome_bin:
                options.binary_location = chrome_bin
            service = ChromeService(executable_path=chromedriver_path)
            return webdriver.Chrome(service=service, options=options)
        else:
            # Use webdriver_manager for local development
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)

    elif browser_name == "firefox":
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")

        service = FirefoxService(GeckoDriverManager().install())
        return webdriver.Firefox(service=service, options=options)

    else:
        raise ValueError(f"Unsupported browser: {browser_name}")


def _create_remote_driver(hub_url: str, browser_name: str, headless: bool) -> webdriver.Remote:
    """Create a remote WebDriver instance for Selenium Grid."""
    if browser_name == "chrome":
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    elif browser_name == "firefox":
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")

    else:
        raise ValueError(f"Unsupported browser: {browser_name}")

    return webdriver.Remote(
        command_executor=hub_url,
        options=options
    )


def _capture_screenshot(driver: webdriver.Remote, test_name: str):
    """Capture a screenshot and save it to the test results directory."""
    if driver:
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"{test_name}_{timestamp}.png"
            filepath = SCREENSHOT_DIR / filename
            driver.save_screenshot(str(filepath))
            print(f"\n📸 Screenshot saved: {filepath}")
        except Exception as e:
            print(f"\n⚠️  Failed to capture screenshot: {e}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to capture test results for screenshot capture.

    This makes the test result available to the driver fixture
    so it can determine whether to capture a screenshot.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(scope="function")
def wait(driver) -> WebDriverWait:
    """Create a WebDriverWait instance with default timeout."""
    return WebDriverWait(driver, 10)


@pytest.fixture(scope="function")
def base_url(browser_config) -> str:
    """Get the base URL for the application."""
    return browser_config["base_url"]


@pytest.fixture(scope="function")
def navigate_to(driver, base_url):
    """
    Helper fixture to navigate to specific pages.

    Usage:
        def test_something(navigate_to):
            navigate_to("/search")
            # Test logic here
    """
    def _navigate(path: str = "/"):
        url = f"{base_url}{path}"
        driver.get(url)
        # Wait for page to be ready
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return driver

    return _navigate


@pytest.fixture(scope="function")
def wait_for_element(driver):
    """
    Helper fixture to wait for elements to be visible.

    Usage:
        def test_something(wait_for_element):
            element = wait_for_element(By.ID, "search-button")
            element.click()
    """
    def _wait(by: By, value: str, timeout: int = 10):
        try:
            return WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
        except TimeoutException:
            raise TimeoutException(
                f"Element not found: {by}='{value}' after {timeout}s"
            )

    return _wait


@pytest.fixture(scope="function")
def wait_for_elements(driver):
    """
    Helper fixture to wait for multiple elements to be present.

    Usage:
        def test_something(wait_for_elements):
            elements = wait_for_elements(By.CLASS_NAME, "result-card")
            assert len(elements) > 0
    """
    def _wait(by: By, value: str, timeout: int = 10):
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_all_elements_located((by, value))
            )
        except TimeoutException:
            raise TimeoutException(
                f"Elements not found: {by}='{value}' after {timeout}s"
            )

    return _wait


@pytest.fixture(scope="function")
def wait_for_text(driver):
    """
    Helper fixture to wait for text to be present in an element.

    Usage:
        def test_something(wait_for_text):
            wait_for_text(By.ID, "status", "Completed")
    """
    def _wait(by: By, value: str, text: str, timeout: int = 10):
        try:
            return WebDriverWait(driver, timeout).until(
                EC.text_to_be_present_in_element((by, value), text)
            )
        except TimeoutException:
            raise TimeoutException(
                f"Text '{text}' not found in {by}='{value}' after {timeout}s"
            )

    return _wait


@pytest.fixture(scope="function")
def click_when_ready(driver):
    """
    Helper fixture to click an element when it becomes clickable.

    Usage:
        def test_something(click_when_ready):
            click_when_ready(By.ID, "submit-button")
    """
    def _click(by: By, value: str, timeout: int = 10):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            element.click()
            return element
        except TimeoutException:
            raise TimeoutException(
                f"Element not clickable: {by}='{value}' after {timeout}s"
            )

    return _click


# Mark all tests in this directory as frontend tests
def pytest_collection_modifyitems(config, items):
    """Automatically mark all tests in frontend/ as frontend tests."""
    for item in items:
        if "frontend" in str(item.fspath):
            item.add_marker(pytest.mark.frontend)
