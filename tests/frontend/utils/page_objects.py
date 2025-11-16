"""Page Object Model classes for MAM Audiobook Finder frontend testing."""

import time
from typing import List
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .helpers import (
    wait_for_page_load,
    scroll_to_element,
    clear_and_send_keys,
    is_element_present,
)


class BasePage:
    """Base class for all page objects."""

    def __init__(self, driver: WebDriver, base_url: str):
        """Initialize the page object."""
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, 10)

    def navigate_to(self, path: str = "/"):
        """Navigate to a specific path."""
        url = f"{self.base_url}{path}"
        self.driver.get(url)
        wait_for_page_load(self.driver)
        return self

    def get_current_url(self) -> str:
        """Get the current URL."""
        return self.driver.current_url

    def get_page_title(self) -> str:
        """Get the page title."""
        return self.driver.title

    def find_element(self, by: By, value: str, timeout: int = 10) -> WebElement:
        """Find a single element with explicit wait."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
        except TimeoutException:
            raise TimeoutException(f"Element not found: {by}='{value}' after {timeout}s")

    def find_elements(self, by: By, value: str, timeout: int = 10) -> List[WebElement]:
        """Find multiple elements with explicit wait."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((by, value))
            )
        except TimeoutException:
            return []

    def click_element(self, by: By, value: str, timeout: int = 10):
        """Click an element when it's clickable."""
        element = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
        scroll_to_element(self.driver, element)
        element.click()
        return self

    def enter_text(self, by: By, value: str, text: str, timeout: int = 10):
        """Enter text into an input field."""
        element = self.find_element(by, value, timeout)
        clear_and_send_keys(element, text)
        return self

    def get_text(self, by: By, value: str, timeout: int = 10) -> str:
        """Get text from an element."""
        element = self.find_element(by, value, timeout)
        return element.text

    def is_element_visible(self, by: By, value: str, timeout: int = 3) -> bool:
        """Check if an element is visible."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
            return True
        except (TimeoutException, NoSuchElementException):
            return False

    def wait_for_text_in_element(self, by: By, value: str, text: str, timeout: int = 10):
        """Wait for specific text to appear in an element."""
        WebDriverWait(self.driver, timeout).until(
            EC.text_to_be_present_in_element((by, value), text)
        )
        return self

    def get_nav_links(self) -> List[WebElement]:
        """Get all navigation links."""
        return self.find_elements(By.CSS_SELECTOR, "nav a")

    def click_nav_link(self, text: str):
        """Click a navigation link by its text."""
        links = self.get_nav_links()
        for link in links:
            if text.lower() in link.text.lower():
                link.click()
                wait_for_page_load(self.driver)
                return self
        raise NoSuchElementException(f"Navigation link '{text}' not found")


class SearchPage(BasePage):
    """Page object for the Search page."""

    # Locators
    SEARCH_INPUT = (By.ID, "search-input")
    SEARCH_BUTTON = (By.ID, "search-button")
    RESULTS_CONTAINER = (By.ID, "results")
    RESULT_CARDS = (By.CLASS_NAME, "result-card")
    LOADING_INDICATOR = (By.CLASS_NAME, "loading")
    ERROR_MESSAGE = (By.CLASS_NAME, "error-message")
    ADD_BUTTONS = (By.CSS_SELECTOR, ".result-card button")
    COVER_IMAGES = (By.CSS_SELECTOR, ".result-card img")

    def __init__(self, driver: WebDriver, base_url: str):
        """Initialize the search page."""
        super().__init__(driver, base_url)
        self.navigate_to("/search")

    def enter_search_query(self, query: str):
        """Enter text into the search input."""
        self.enter_text(*self.SEARCH_INPUT, query)
        return self

    def click_search(self):
        """Click the search button."""
        self.click_element(*self.SEARCH_BUTTON)
        return self

    def search_for(self, query: str):
        """Perform a complete search."""
        self.enter_search_query(query)
        self.click_search()
        self.wait_for_results()
        return self

    def wait_for_results(self, timeout: int = 10):
        """Wait for search results to appear."""
        # Wait for loading to finish (if present)
        time.sleep(0.5)  # Brief pause for loading indicator to appear
        try:
            WebDriverWait(self.driver, 2).until(
                EC.invisibility_of_element_located(self.LOADING_INDICATOR)
            )
        except TimeoutException:
            pass  # Loading indicator may not appear for cached results

        # Wait for results or error
        WebDriverWait(self.driver, timeout).until(
            lambda d: (
                is_element_present(d, *self.RESULT_CARDS) or
                is_element_present(d, *self.ERROR_MESSAGE)
            )
        )
        return self

    def get_result_cards(self) -> List[WebElement]:
        """Get all result cards."""
        return self.find_elements(*self.RESULT_CARDS)

    def get_result_count(self) -> int:
        """Get the number of search results."""
        return len(self.get_result_cards())

    def get_result_titles(self) -> List[str]:
        """Get titles of all results."""
        cards = self.get_result_cards()
        titles = []
        for card in cards:
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, ".title")
                titles.append(title_elem.text)
            except NoSuchElementException:
                continue
        return titles

    def click_add_button(self, index: int = 0):
        """Click the add button for a specific result."""
        buttons = self.find_elements(*self.ADD_BUTTONS)
        if index < len(buttons):
            scroll_to_element(self.driver, buttons[index])
            buttons[index].click()
            time.sleep(0.5)  # Wait for add action
        else:
            raise IndexError(f"Result index {index} out of range (max: {len(buttons) - 1})")
        return self

    def are_covers_loaded(self) -> bool:
        """Check if cover images are loaded."""
        images = self.find_elements(*self.COVER_IMAGES, timeout=5)
        if not images:
            return False

        # Check if at least one image has a valid src
        for img in images:
            src = img.get_attribute("src")
            if src and not src.endswith("placeholder.png"):
                return True
        return False


class HistoryPage(BasePage):
    """Page object for the History page."""

    # Locators
    HISTORY_TABLE = (By.ID, "history-table")
    HISTORY_ROWS = (By.CSS_SELECTOR, "#history-table tbody tr")
    DELETE_BUTTONS = (By.CSS_SELECTOR, ".delete-btn")
    IMPORT_FORMS = (By.CSS_SELECTOR, ".import-form")
    STATUS_CELLS = (By.CSS_SELECTOR, "td.status")
    EMPTY_MESSAGE = (By.CLASS_NAME, "empty-message")

    def __init__(self, driver: WebDriver, base_url: str):
        """Initialize the history page."""
        super().__init__(driver, base_url)
        self.navigate_to("/history")

    def wait_for_history_load(self, timeout: int = 10):
        """Wait for history table to load."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: (
                is_element_present(d, *self.HISTORY_ROWS) or
                is_element_present(d, *self.EMPTY_MESSAGE)
            )
        )
        return self

    def get_history_rows(self) -> List[WebElement]:
        """Get all history rows."""
        return self.find_elements(*self.HISTORY_ROWS, timeout=5)

    def get_history_count(self) -> int:
        """Get the number of history entries."""
        return len(self.get_history_rows())

    def get_history_titles(self) -> List[str]:
        """Get titles from history entries."""
        rows = self.get_history_rows()
        titles = []
        for row in rows:
            try:
                title_cell = row.find_element(By.CSS_SELECTOR, ".title")
                titles.append(title_cell.text)
            except NoSuchElementException:
                continue
        return titles

    def get_statuses(self) -> List[str]:
        """Get all torrent statuses."""
        status_elements = self.find_elements(*self.STATUS_CELLS, timeout=5)
        return [elem.text for elem in status_elements]

    def delete_entry(self, index: int = 0):
        """Delete a history entry by index."""
        buttons = self.find_elements(*self.DELETE_BUTTONS)
        if index < len(buttons):
            scroll_to_element(self.driver, buttons[index])
            buttons[index].click()
            time.sleep(0.5)  # Wait for deletion
        else:
            raise IndexError(f"History index {index} out of range")
        return self

    def click_import_button(self, index: int = 0):
        """Click import button for a specific entry."""
        import_buttons = self.driver.find_elements(
            By.CSS_SELECTOR, ".import-btn"
        )
        if index < len(import_buttons):
            scroll_to_element(self.driver, import_buttons[index])
            import_buttons[index].click()
            time.sleep(0.5)  # Wait for form to expand
        else:
            raise IndexError(f"Import button index {index} out of range")
        return self


class ShowcasePage(BasePage):
    """Page object for the Showcase page."""

    # Locators
    SHOWCASE_GRID = (By.ID, "showcase-grid")
    AUDIOBOOK_CARDS = (By.CLASS_NAME, "audiobook-card")
    FILTER_SELECT = (By.ID, "filter-select")
    SEARCH_INPUT = (By.ID, "showcase-search")
    DETAIL_MODAL = (By.ID, "detail-modal")
    MODAL_CLOSE_BTN = (By.CLASS_NAME, "modal-close")
    COVER_IMAGES = (By.CSS_SELECTOR, ".audiobook-card img")

    def __init__(self, driver: WebDriver, base_url: str):
        """Initialize the showcase page."""
        super().__init__(driver, base_url)
        self.navigate_to("/showcase")

    def wait_for_showcase_load(self, timeout: int = 10):
        """Wait for showcase grid to load."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: is_element_present(d, *self.AUDIOBOOK_CARDS)
        )
        return self

    def get_audiobook_cards(self) -> List[WebElement]:
        """Get all audiobook cards."""
        return self.find_elements(*self.AUDIOBOOK_CARDS, timeout=5)

    def get_audiobook_count(self) -> int:
        """Get the number of audiobooks displayed."""
        return len(self.get_audiobook_cards())

    def click_audiobook_card(self, index: int = 0):
        """Click an audiobook card to open details."""
        cards = self.get_audiobook_cards()
        if index < len(cards):
            scroll_to_element(self.driver, cards[index])
            cards[index].click()
            time.sleep(0.5)  # Wait for modal
        else:
            raise IndexError(f"Card index {index} out of range")
        return self

    def is_detail_modal_open(self) -> bool:
        """Check if the detail modal is open."""
        return self.is_element_visible(*self.DETAIL_MODAL, timeout=3)

    def close_detail_modal(self):
        """Close the detail modal."""
        if self.is_detail_modal_open():
            self.click_element(*self.MODAL_CLOSE_BTN)
            time.sleep(0.3)
        return self

    def filter_by(self, filter_text: str):
        """Apply a filter."""
        filter_elem = self.find_element(*self.FILTER_SELECT)
        from selenium.webdriver.support.ui import Select
        select = Select(filter_elem)
        select.select_by_visible_text(filter_text)
        time.sleep(0.5)  # Wait for filter to apply
        return self


class LogsPage(BasePage):
    """Page object for the Logs page."""

    # Locators
    LOGS_CONTAINER = (By.ID, "logs-container")
    LOG_LINES = (By.CLASS_NAME, "log-line")
    LEVEL_FILTER = (By.ID, "level-filter")
    REFRESH_BUTTON = (By.ID, "refresh-logs")

    def __init__(self, driver: WebDriver, base_url: str):
        """Initialize the logs page."""
        super().__init__(driver, base_url)
        self.navigate_to("/logs")

    def wait_for_logs_load(self, timeout: int = 10):
        """Wait for logs to load."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: is_element_present(d, *self.LOG_LINES)
        )
        return self

    def get_log_lines(self) -> List[WebElement]:
        """Get all log lines."""
        return self.find_elements(*self.LOG_LINES, timeout=5)

    def get_log_count(self) -> int:
        """Get the number of log lines."""
        return len(self.get_log_lines())

    def click_refresh(self):
        """Click the refresh button."""
        self.click_element(*self.REFRESH_BUTTON)
        time.sleep(0.5)  # Wait for refresh
        return self

    def filter_by_level(self, level: str):
        """Filter logs by level (ERROR, WARN, INFO, DEBUG)."""
        level_elem = self.find_element(*self.LEVEL_FILTER)
        from selenium.webdriver.support.ui import Select
        select = Select(level_elem)
        select.select_by_visible_text(level)
        time.sleep(0.5)  # Wait for filter
        return self
