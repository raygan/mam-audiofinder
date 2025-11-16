"""End-to-end tests for the complete import workflow."""

import pytest
from selenium.webdriver.common.by import By
import time

from .utils.page_objects import SearchPage, HistoryPage, ShowcasePage
from .utils.helpers import wait_for_page_load


class TestCompleteWorkflow:
    """Test the complete workflow from search to showcase."""

    @pytest.mark.skip(reason="Requires full environment setup")
    def test_search_add_history_import_showcase(self, driver, base_url):
        """
        Test the complete workflow:
        1. Search for an audiobook
        2. Add to qBittorrent
        3. Verify in history
        4. Import to library
        5. Verify in showcase
        """
        # Step 1: Search for audiobook
        search_page = SearchPage(driver, base_url)
        search_page.search_for("Test Audiobook")

        assert search_page.get_result_count() > 0

        # Step 2: Add to qBittorrent
        initial_title = search_page.get_result_titles()[0]
        search_page.click_add_button(index=0)

        time.sleep(2)  # Wait for add operation

        # Step 3: Verify in history
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        history_titles = history_page.get_history_titles()
        assert initial_title in history_titles

        # Step 4: Wait for download to complete (in real scenario)
        # Then import to library
        # history_page.click_import_button(index=0)
        # ... submit import form ...

        # Step 5: Verify in showcase
        # showcase_page = ShowcasePage(driver, base_url)
        # showcase_page.wait_for_showcase_load()
        # ... verify audiobook appears ...


class TestSearchToHistory:
    """Test workflow from search to history."""

    @pytest.mark.skip(reason="Requires MAM and qBittorrent services")
    def test_add_appears_in_history(self, driver, base_url):
        """Test that adding a torrent makes it appear in history."""
        # Search for audiobook
        search_page = SearchPage(driver, base_url)
        search_page.search_for("Fiction")

        result_count = search_page.get_result_count()
        assert result_count > 0

        # Get first result title
        first_title = search_page.get_result_titles()[0]

        # Add to qBittorrent
        search_page.click_add_button(index=0)

        time.sleep(2)  # Wait for add operation

        # Navigate to history
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        # Verify the title appears in history
        history_titles = history_page.get_history_titles()
        assert first_title in history_titles

    @pytest.mark.skip(reason="Requires MAM and qBittorrent services")
    def test_multiple_adds_all_appear(self, driver, base_url):
        """Test that adding multiple torrents all appear in history."""
        search_page = SearchPage(driver, base_url)
        search_page.search_for("Audiobook")

        # Add first two results
        titles = search_page.get_result_titles()[:2]

        search_page.click_add_button(index=0)
        time.sleep(1)
        search_page.click_add_button(index=1)
        time.sleep(1)

        # Check history
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        history_titles = history_page.get_history_titles()

        for title in titles:
            assert title in history_titles


class TestHistoryToImport:
    """Test workflow from history to import."""

    @pytest.mark.skip(reason="Requires completed torrent")
    def test_import_form_interaction(self, driver, base_url):
        """Test the import form interaction."""
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        # Find a completed/seeding torrent
        statuses = history_page.get_statuses()
        completed_index = None

        for i, status in enumerate(statuses):
            if "completed" in status.lower() or "seeding" in status.lower():
                completed_index = i
                break

        if completed_index is not None:
            # Click import
            history_page.click_import_button(index=completed_index)

            # Verify form appears
            import_forms = history_page.find_elements(
                *history_page.IMPORT_FORMS,
                timeout=5
            )
            assert len(import_forms) > 0

    @pytest.mark.skip(reason="Requires completed torrent and filesystem")
    def test_flatten_option_detection(self, driver, base_url):
        """Test that multi-disc audiobooks are detected for flattening."""
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        # Open import form for a multi-disc audiobook
        history_page.click_import_button(index=0)

        # Check if flatten checkbox is auto-checked
        # (depends on multi-disc detection logic)

    @pytest.mark.skip(reason="Requires completed torrent and filesystem")
    def test_import_submission(self, driver, base_url):
        """Test submitting the import form."""
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        history_page.click_import_button(index=0)

        # Fill and submit import form
        # (implementation-dependent)

        # Wait for import to complete
        time.sleep(2)

        # Verify success message or status update


class TestImportToShowcase:
    """Test workflow from import to showcase."""

    @pytest.mark.skip(reason="Requires completed import")
    def test_imported_appears_in_showcase(self, driver, base_url):
        """Test that imported audiobook appears in showcase."""
        # Perform import
        # ...

        # Navigate to showcase
        showcase_page = ShowcasePage(driver, base_url)
        showcase_page.wait_for_showcase_load()

        # Verify audiobook appears
        cards = showcase_page.get_audiobook_cards()
        assert len(cards) > 0


class TestErrorHandling:
    """Test error handling in workflows."""

    @pytest.mark.skip(reason="Requires error simulation")
    def test_add_with_network_error(self, driver, base_url):
        """Test handling of network errors when adding."""
        search_page = SearchPage(driver, base_url)
        search_page.search_for("Test")

        # Simulate network error (stop qBittorrent)
        # Click add
        # Verify error message appears

    @pytest.mark.skip(reason="Requires error simulation")
    def test_import_with_missing_files(self, driver, base_url):
        """Test handling of import when files are missing."""
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        # Try to import an entry with missing files
        # Verify error message

    @pytest.mark.skip(reason="Requires error simulation")
    def test_import_with_permission_error(self, driver, base_url):
        """Test handling of permission errors during import."""
        # Try to import when destination has permission issues
        # Verify error message


class TestStateUpdates:
    """Test live state updates during workflows."""

    @pytest.mark.skip(reason="Requires active download")
    def test_status_updates_during_download(self, driver, base_url):
        """Test that status updates as torrent downloads."""
        # Add a torrent
        # Navigate to history
        # Watch status change from queued -> downloading -> completed

    @pytest.mark.skip(reason="Requires import operation")
    def test_status_after_import(self, driver, base_url):
        """Test that status updates after import."""
        # Perform import
        # Verify status shows as imported
        # Verify category changed (if applicable)


class TestMultiDiscWorkflow:
    """Test workflows involving multi-disc audiobooks."""

    @pytest.mark.skip(reason="Requires multi-disc torrent")
    def test_multi_disc_detection(self, driver, base_url):
        """Test that multi-disc structure is detected."""
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        # Find multi-disc entry
        # Open import form
        # Verify flatten is auto-detected and recommended

    @pytest.mark.skip(reason="Requires multi-disc torrent")
    def test_flatten_preview(self, driver, base_url):
        """Test the flatten preview functionality."""
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        # Open import form for multi-disc
        # Check flatten option
        # Verify preview shows flattened structure

    @pytest.mark.skip(reason="Requires multi-disc torrent and filesystem")
    def test_import_with_flatten(self, driver, base_url):
        """Test importing with flatten enabled."""
        # Import multi-disc audiobook with flatten
        # Verify files are flattened correctly


class TestNavigationBetweenPages:
    """Test navigation between different pages during workflow."""

    def test_search_to_history_navigation(self, driver, base_url):
        """Test navigating from search to history."""
        search_page = SearchPage(driver, base_url)

        search_page.click_nav_link("History")
        wait_for_page_load(driver)

        assert "/history" in driver.current_url

    def test_history_to_showcase_navigation(self, driver, base_url):
        """Test navigating from history to showcase."""
        history_page = HistoryPage(driver, base_url)

        history_page.click_nav_link("Showcase")
        wait_for_page_load(driver)

        assert "/showcase" in driver.current_url

    def test_showcase_to_search_navigation(self, driver, base_url):
        """Test navigating from showcase to search."""
        showcase_page = ShowcasePage(driver, base_url)

        showcase_page.click_nav_link("Search")
        wait_for_page_load(driver)

        assert "/search" in driver.current_url

    def test_back_button_works(self, driver, base_url):
        """Test that browser back button works."""
        search_page = SearchPage(driver, base_url)

        # Navigate to history
        search_page.click_nav_link("History")
        wait_for_page_load(driver)

        # Go back
        driver.back()
        wait_for_page_load(driver)

        # Should be back on search page
        assert "/search" in driver.current_url


class TestDataPersistence:
    """Test data persistence across page navigation."""

    @pytest.mark.skip(reason="Requires history data")
    def test_history_persists_across_navigation(self, driver, base_url):
        """Test that history persists when navigating away and back."""
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        initial_count = history_page.get_history_count()
        initial_titles = history_page.get_history_titles()

        # Navigate away
        history_page.click_nav_link("Search")
        wait_for_page_load(driver)

        # Navigate back
        search_page = SearchPage(driver, base_url)
        search_page.click_nav_link("History")
        wait_for_page_load(driver)

        # Verify data is still there
        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load()

        assert history_page.get_history_count() == initial_count
        assert history_page.get_history_titles() == initial_titles


class TestPerformance:
    """Test performance aspects of workflows."""

    @pytest.mark.skip(reason="Requires large dataset")
    def test_large_history_loads_reasonably(self, driver, base_url):
        """Test that large history tables load in reasonable time."""
        import time

        start_time = time.time()

        history_page = HistoryPage(driver, base_url)
        history_page.wait_for_history_load(timeout=30)

        load_time = time.time() - start_time

        # Should load within 5 seconds even with 100+ entries
        assert load_time < 5.0

    @pytest.mark.skip(reason="Requires large dataset")
    def test_showcase_with_many_audiobooks(self, driver, base_url):
        """Test showcase performance with many audiobooks."""
        import time

        start_time = time.time()

        showcase_page = ShowcasePage(driver, base_url)
        showcase_page.wait_for_showcase_load(timeout=30)

        load_time = time.time() - start_time

        # Should load within reasonable time
        assert load_time < 10.0
