"""Frontend tests for the Search page."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .utils.page_objects import SearchPage
from .utils.helpers import wait_for_page_load


class TestSearchPageLayout:
    """Test the layout and basic structure of the search page."""

    def test_page_loads(self, driver, base_url):
        """Test that the search page loads successfully."""
        page = SearchPage(driver, base_url)
        assert "Search" in page.get_page_title()
        assert "/search" in page.get_current_url()

    def test_navigation_present(self, driver, base_url):
        """Test that navigation links are present."""
        page = SearchPage(driver, base_url)
        nav_links = page.get_nav_links()
        assert len(nav_links) > 0

        # Check for expected nav items
        nav_text = [link.text.lower() for link in nav_links]
        assert any("search" in text for text in nav_text)
        assert any("history" in text for text in nav_text)

    def test_search_form_elements_present(self, driver, base_url):
        """Test that all search form elements are present."""
        page = SearchPage(driver, base_url)

        # Check for search input
        assert page.is_element_visible(*page.SEARCH_INPUT)

        # Check for search button
        assert page.is_element_visible(*page.SEARCH_BUTTON)

        # Check for results container
        assert page.is_element_visible(*page.RESULTS_CONTAINER)


class TestSearchFunctionality:
    """Test search functionality."""

    @pytest.mark.skip(reason="Requires running MAM service")
    def test_search_with_valid_query(self, driver, base_url):
        """Test searching with a valid query."""
        page = SearchPage(driver, base_url)

        # Perform search
        page.enter_search_query("Harry Potter")
        page.click_search()

        # Wait for results
        page.wait_for_results(timeout=15)

        # Verify results are displayed
        result_count = page.get_result_count()
        assert result_count > 0, "Expected at least one search result"

    def test_search_input_accepts_text(self, driver, base_url):
        """Test that search input accepts text."""
        page = SearchPage(driver, base_url)

        test_query = "Test Audiobook"
        page.enter_search_query(test_query)

        # Verify text was entered
        search_input = page.find_element(*page.SEARCH_INPUT)
        assert search_input.get_attribute("value") == test_query

    def test_search_button_clickable(self, driver, base_url):
        """Test that search button is clickable."""
        page = SearchPage(driver, base_url)

        page.enter_search_query("Test")
        page.click_search()  # Should not raise exception

    @pytest.mark.skip(reason="Requires running MAM service")
    def test_empty_search_handling(self, driver, base_url):
        """Test behavior when searching with empty query."""
        page = SearchPage(driver, base_url)

        # Try to search with empty query
        page.click_search()

        # Should either show validation or handle gracefully
        # (implementation-dependent)


class TestSearchResults:
    """Test search results display and interaction."""

    @pytest.mark.skip(reason="Requires running MAM service and mock data")
    def test_results_display_correctly(self, driver, base_url):
        """Test that search results display with correct structure."""
        page = SearchPage(driver, base_url)

        page.search_for("Narnia")
        cards = page.get_result_cards()

        assert len(cards) > 0

        # Check first card structure
        first_card = cards[0]
        assert first_card.find_element(By.CSS_SELECTOR, ".title")
        assert first_card.find_element(By.CSS_SELECTOR, ".author")

    @pytest.mark.skip(reason="Requires running MAM service and mock data")
    def test_result_titles_not_empty(self, driver, base_url):
        """Test that result titles are not empty."""
        page = SearchPage(driver, base_url)

        page.search_for("Fiction")
        titles = page.get_result_titles()

        assert len(titles) > 0
        for title in titles:
            assert len(title.strip()) > 0

    @pytest.mark.skip(reason="Requires running MAM service and mock data")
    def test_add_button_present_on_results(self, driver, base_url):
        """Test that each result has an add button."""
        page = SearchPage(driver, base_url)

        page.search_for("Mystery")
        cards = page.get_result_cards()

        assert len(cards) > 0

        for card in cards:
            buttons = card.find_elements(By.CSS_SELECTOR, "button")
            assert len(buttons) > 0


class TestAddToQBittorrent:
    """Test adding torrents to qBittorrent."""

    @pytest.mark.skip(reason="Requires running services")
    def test_add_button_click(self, driver, base_url):
        """Test clicking the add button."""
        page = SearchPage(driver, base_url)

        page.search_for("Audiobook")
        page.click_add_button(index=0)

        # Should show some feedback (implementation-dependent)
        # Could be a success message, button text change, etc.

    @pytest.mark.skip(reason="Requires running services")
    def test_multiple_add_clicks(self, driver, base_url):
        """Test adding multiple items."""
        page = SearchPage(driver, base_url)

        page.search_for("Fiction")

        # Add first two results
        page.click_add_button(index=0)
        page.click_add_button(index=1)

        # Should handle multiple adds without errors


class TestCoverImages:
    """Test cover image loading and display."""

    @pytest.mark.skip(reason="Requires running services and cover data")
    def test_covers_have_src_attribute(self, driver, base_url):
        """Test that cover images have src attributes."""
        page = SearchPage(driver, base_url)

        page.search_for("Popular")

        images = page.find_elements(*page.COVER_IMAGES)
        assert len(images) > 0

        for img in images:
            src = img.get_attribute("src")
            assert src is not None
            assert len(src) > 0

    @pytest.mark.skip(reason="Requires running services and cover data")
    def test_covers_load_progressively(self, driver, base_url):
        """Test that covers use lazy loading."""
        page = SearchPage(driver, base_url)

        page.search_for("Series")

        # Initially, some images may use placeholder
        # As user scrolls, real covers should load
        # (This is implementation-dependent)


class TestErrorHandling:
    """Test error handling on the search page."""

    @pytest.mark.skip(reason="Requires error simulation")
    def test_network_error_handling(self, driver, base_url):
        """Test handling of network errors."""
        # This would require simulating a network error
        # e.g., by stopping the backend service
        pass

    @pytest.mark.skip(reason="Requires error simulation")
    def test_invalid_response_handling(self, driver, base_url):
        """Test handling of invalid API responses."""
        # This would require mocking the API to return invalid data
        pass


class TestResponsiveness:
    """Test responsive behavior of the search page."""

    def test_mobile_viewport(self, driver, base_url):
        """Test page in mobile viewport."""
        driver.set_window_size(375, 667)  # iPhone size

        page = SearchPage(driver, base_url)

        # Page should still be usable
        assert page.is_element_visible(*page.SEARCH_INPUT)
        assert page.is_element_visible(*page.SEARCH_BUTTON)

    def test_tablet_viewport(self, driver, base_url):
        """Test page in tablet viewport."""
        driver.set_window_size(768, 1024)  # iPad size

        page = SearchPage(driver, base_url)

        assert page.is_element_visible(*page.SEARCH_INPUT)
        assert page.is_element_visible(*page.SEARCH_BUTTON)

    def test_desktop_viewport(self, driver, base_url):
        """Test page in desktop viewport."""
        driver.set_window_size(1920, 1080)

        page = SearchPage(driver, base_url)

        assert page.is_element_visible(*page.SEARCH_INPUT)
        assert page.is_element_visible(*page.SEARCH_BUTTON)


class TestNavigation:
    """Test navigation from search page."""

    def test_navigate_to_history(self, driver, base_url):
        """Test navigating to history page."""
        page = SearchPage(driver, base_url)

        page.click_nav_link("History")
        wait_for_page_load(driver)

        assert "/history" in driver.current_url

    def test_navigate_to_showcase(self, driver, base_url):
        """Test navigating to showcase page."""
        page = SearchPage(driver, base_url)

        page.click_nav_link("Showcase")
        wait_for_page_load(driver)

        assert "/showcase" in driver.current_url
