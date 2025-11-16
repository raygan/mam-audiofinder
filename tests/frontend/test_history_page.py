"""Frontend tests for the History page."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from .utils.page_objects import HistoryPage
from .utils.helpers import wait_for_page_load


class TestHistoryPageLayout:
    """Test the layout and basic structure of the history page."""

    def test_page_loads(self, driver, base_url):
        """Test that the history page loads successfully."""
        page = HistoryPage(driver, base_url)
        assert "History" in page.get_page_title()
        assert "/history" in page.get_current_url()

    def test_navigation_present(self, driver, base_url):
        """Test that navigation links are present."""
        page = HistoryPage(driver, base_url)
        nav_links = page.get_nav_links()
        assert len(nav_links) > 0

    def test_history_table_present(self, driver, base_url):
        """Test that history table is present."""
        page = HistoryPage(driver, base_url)
        assert page.is_element_visible(*page.HISTORY_TABLE, timeout=10)


class TestHistoryDisplay:
    """Test history entries display."""

    def test_history_table_loads(self, driver, base_url):
        """Test that history table loads."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load(timeout=10)

        # Should either show rows or empty message
        has_rows = len(page.get_history_rows()) > 0
        has_empty_msg = page.is_element_visible(*page.EMPTY_MESSAGE, timeout=2)

        assert has_rows or has_empty_msg

    @pytest.mark.skip(reason="Requires history data")
    def test_history_entries_display(self, driver, base_url):
        """Test that history entries are displayed correctly."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        rows = page.get_history_rows()
        assert len(rows) > 0

        # Check that each row has expected cells
        first_row = rows[0]
        cells = first_row.find_elements(By.TAG_NAME, "td")
        assert len(cells) >= 4  # title, author, status, actions

    @pytest.mark.skip(reason="Requires history data")
    def test_history_titles_not_empty(self, driver, base_url):
        """Test that history titles are not empty."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        titles = page.get_history_titles()
        assert len(titles) > 0

        for title in titles:
            assert len(title.strip()) > 0

    @pytest.mark.skip(reason="Requires history data")
    def test_status_column_displays(self, driver, base_url):
        """Test that status column displays for each entry."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        statuses = page.get_statuses()
        assert len(statuses) > 0

        # Statuses should be one of the expected values
        valid_statuses = [
            "downloading", "seeding", "completed",
            "paused", "error", "queued", "not found"
        ]

        for status in statuses:
            status_lower = status.lower()
            assert any(valid in status_lower for valid in valid_statuses)


class TestHistoryActions:
    """Test actions on history entries."""

    @pytest.mark.skip(reason="Requires history data")
    def test_delete_button_present(self, driver, base_url):
        """Test that delete buttons are present."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        rows = page.get_history_rows()
        if len(rows) > 0:
            delete_buttons = page.find_elements(*page.DELETE_BUTTONS, timeout=5)
            assert len(delete_buttons) > 0

    @pytest.mark.skip(reason="Requires history data and confirmation")
    def test_delete_entry(self, driver, base_url):
        """Test deleting a history entry."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        initial_count = page.get_history_count()
        if initial_count > 0:
            page.delete_entry(index=0)

            # Wait for deletion to complete
            import time
            time.sleep(1)

            # Refresh or wait for update
            driver.refresh()
            page.wait_for_history_load()

            new_count = page.get_history_count()
            assert new_count == initial_count - 1

    @pytest.mark.skip(reason="Requires history data")
    def test_import_button_present(self, driver, base_url):
        """Test that import buttons are present for completed torrents."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        # Import buttons should be present for completed/seeding torrents
        # (implementation-dependent)


class TestImportForm:
    """Test import form functionality."""

    @pytest.mark.skip(reason="Requires completed torrent data")
    def test_import_form_opens(self, driver, base_url):
        """Test that clicking import opens the form."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        page.click_import_button(index=0)

        # Import form should be visible
        import_forms = page.find_elements(*page.IMPORT_FORMS, timeout=5)
        assert len(import_forms) > 0

    @pytest.mark.skip(reason="Requires completed torrent data")
    def test_import_form_has_options(self, driver, base_url):
        """Test that import form has all necessary options."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        page.click_import_button(index=0)

        # Should have flatten checkbox, submit button, etc.
        # (implementation-dependent)

    @pytest.mark.skip(reason="Requires completed torrent and file system")
    def test_import_submit(self, driver, base_url):
        """Test submitting the import form."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        page.click_import_button(index=0)

        # Fill form and submit
        # (implementation-dependent)


class TestLiveStateUpdates:
    """Test live torrent state updates."""

    @pytest.mark.skip(reason="Requires active torrents")
    def test_status_updates_periodically(self, driver, base_url):
        """Test that torrent statuses update periodically."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        initial_statuses = page.get_statuses()

        # Wait for potential update
        import time
        time.sleep(5)

        # Refresh to get updated statuses
        driver.refresh()
        page.wait_for_history_load()

        updated_statuses = page.get_statuses()

        # Statuses may have changed (especially for downloading torrents)
        assert len(updated_statuses) == len(initial_statuses)

    @pytest.mark.skip(reason="Requires active download")
    def test_progress_updates_for_downloading(self, driver, base_url):
        """Test that download progress updates."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        # Find a downloading torrent and check progress updates
        # (implementation-dependent)


class TestEmptyState:
    """Test empty state when no history exists."""

    @pytest.mark.skip(reason="Requires empty database")
    def test_empty_message_displays(self, driver, base_url):
        """Test that empty message displays when no history."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        # If no history, should show message
        if page.get_history_count() == 0:
            assert page.is_element_visible(*page.EMPTY_MESSAGE, timeout=5)

    @pytest.mark.skip(reason="Requires empty database")
    def test_no_rows_when_empty(self, driver, base_url):
        """Test that no rows are displayed when history is empty."""
        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        if page.is_element_visible(*page.EMPTY_MESSAGE, timeout=2):
            assert page.get_history_count() == 0


class TestSorting:
    """Test history table sorting."""

    @pytest.mark.skip(reason="Requires history data and sorting implementation")
    def test_sort_by_date(self, driver, base_url):
        """Test sorting by date added."""
        # If sorting is implemented
        pass

    @pytest.mark.skip(reason="Requires history data and sorting implementation")
    def test_sort_by_title(self, driver, base_url):
        """Test sorting by title."""
        # If sorting is implemented
        pass


class TestFiltering:
    """Test history filtering."""

    @pytest.mark.skip(reason="Requires history data and filter implementation")
    def test_filter_by_status(self, driver, base_url):
        """Test filtering by torrent status."""
        # If filtering is implemented
        pass


class TestNavigation:
    """Test navigation from history page."""

    def test_navigate_to_search(self, driver, base_url):
        """Test navigating to search page."""
        page = HistoryPage(driver, base_url)

        page.click_nav_link("Search")
        wait_for_page_load(driver)

        assert "/search" in driver.current_url

    def test_navigate_to_showcase(self, driver, base_url):
        """Test navigating to showcase page."""
        page = HistoryPage(driver, base_url)

        page.click_nav_link("Showcase")
        wait_for_page_load(driver)

        assert "/showcase" in driver.current_url


class TestResponsiveness:
    """Test responsive behavior of the history page."""

    def test_mobile_viewport(self, driver, base_url):
        """Test page in mobile viewport."""
        driver.set_window_size(375, 667)

        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        # Table should be present (may be scrollable)
        assert page.is_element_visible(*page.HISTORY_TABLE)

    def test_tablet_viewport(self, driver, base_url):
        """Test page in tablet viewport."""
        driver.set_window_size(768, 1024)

        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        assert page.is_element_visible(*page.HISTORY_TABLE)

    def test_desktop_viewport(self, driver, base_url):
        """Test page in desktop viewport."""
        driver.set_window_size(1920, 1080)

        page = HistoryPage(driver, base_url)
        page.wait_for_history_load()

        assert page.is_element_visible(*page.HISTORY_TABLE)
