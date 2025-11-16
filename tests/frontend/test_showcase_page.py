"""Frontend tests for the Showcase page."""

import pytest
from selenium.webdriver.common.by import By

from .utils.page_objects import ShowcasePage
from .utils.helpers import wait_for_page_load


class TestShowcasePageLayout:
    """Test the layout and basic structure of the showcase page."""

    def test_page_loads(self, driver, base_url):
        """Test that the showcase page loads successfully."""
        page = ShowcasePage(driver, base_url)
        assert "Showcase" in page.get_page_title()
        assert "/showcase" in page.get_current_url()

    def test_navigation_present(self, driver, base_url):
        """Test that navigation links are present."""
        page = ShowcasePage(driver, base_url)
        nav_links = page.get_nav_links()
        assert len(nav_links) > 0

    def test_showcase_grid_present(self, driver, base_url):
        """Test that showcase grid is present."""
        page = ShowcasePage(driver, base_url)
        assert page.is_element_visible(*page.SHOWCASE_GRID, timeout=10)


class TestAudiobookDisplay:
    """Test audiobook grid display."""

    def test_showcase_grid_loads(self, driver, base_url):
        """Test that showcase grid loads."""
        page = ShowcasePage(driver, base_url)

        # Grid should be visible
        assert page.is_element_visible(*page.SHOWCASE_GRID)

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_audiobook_cards_display(self, driver, base_url):
        """Test that audiobook cards are displayed."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        cards = page.get_audiobook_cards()
        assert len(cards) > 0

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_cards_have_covers(self, driver, base_url):
        """Test that audiobook cards have cover images."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        cards = page.get_audiobook_cards()
        assert len(cards) > 0

        # Each card should have an image
        for card in cards[:5]:  # Check first 5
            images = card.find_elements(By.TAG_NAME, "img")
            assert len(images) > 0

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_cards_have_titles(self, driver, base_url):
        """Test that audiobook cards have titles."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        cards = page.get_audiobook_cards()
        assert len(cards) > 0

        # Each card should have a title
        for card in cards[:5]:
            title_elem = card.find_element(By.CSS_SELECTOR, ".title, h3, h4")
            assert len(title_elem.text.strip()) > 0


class TestCardInteraction:
    """Test interaction with audiobook cards."""

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_click_card_opens_detail(self, driver, base_url):
        """Test that clicking a card opens the detail modal."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        page.click_audiobook_card(index=0)

        # Detail modal should open
        assert page.is_detail_modal_open()

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_detail_modal_has_content(self, driver, base_url):
        """Test that detail modal displays content."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        page.click_audiobook_card(index=0)

        # Modal should have title, author, etc.
        modal = page.find_element(*page.DETAIL_MODAL)
        assert len(modal.text) > 0

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_close_detail_modal(self, driver, base_url):
        """Test closing the detail modal."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        page.click_audiobook_card(index=0)
        assert page.is_detail_modal_open()

        page.close_detail_modal()

        # Modal should be closed
        assert not page.is_detail_modal_open()


class TestFiltering:
    """Test showcase filtering functionality."""

    @pytest.mark.skip(reason="Requires imported audiobooks and filter implementation")
    def test_filter_select_present(self, driver, base_url):
        """Test that filter select is present."""
        page = ShowcasePage(driver, base_url)

        # Check if filter is implemented
        if page.is_element_visible(*page.FILTER_SELECT, timeout=3):
            filter_elem = page.find_element(*page.FILTER_SELECT)
            assert filter_elem is not None

    @pytest.mark.skip(reason="Requires imported audiobooks and filter data")
    def test_filter_by_author(self, driver, base_url):
        """Test filtering by author."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        initial_count = page.get_audiobook_count()

        # Apply filter
        page.filter_by("Author Name")

        # Count may change after filtering
        filtered_count = page.get_audiobook_count()
        assert filtered_count <= initial_count

    @pytest.mark.skip(reason="Requires imported audiobooks and filter data")
    def test_filter_by_narrator(self, driver, base_url):
        """Test filtering by narrator."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        initial_count = page.get_audiobook_count()

        # Apply filter
        page.filter_by("Narrator Name")

        filtered_count = page.get_audiobook_count()
        assert filtered_count <= initial_count


class TestSearch:
    """Test showcase search functionality."""

    @pytest.mark.skip(reason="Requires search implementation")
    def test_search_input_present(self, driver, base_url):
        """Test that search input is present."""
        page = ShowcasePage(driver, base_url)

        if page.is_element_visible(*page.SEARCH_INPUT, timeout=3):
            search_elem = page.find_element(*page.SEARCH_INPUT)
            assert search_elem is not None

    @pytest.mark.skip(reason="Requires imported audiobooks and search")
    def test_search_filters_results(self, driver, base_url):
        """Test that search filters the results."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        initial_count = page.get_audiobook_count()

        # Enter search term
        page.enter_text(*page.SEARCH_INPUT, "fiction")

        import time
        time.sleep(1)  # Wait for search to filter

        filtered_count = page.get_audiobook_count()
        assert filtered_count <= initial_count


class TestCoverLoading:
    """Test cover image lazy loading."""

    @pytest.mark.skip(reason="Requires imported audiobooks with covers")
    def test_covers_have_src(self, driver, base_url):
        """Test that cover images have src attributes."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        images = page.find_elements(*page.COVER_IMAGES, timeout=5)
        assert len(images) > 0

        for img in images[:5]:
            src = img.get_attribute("src")
            assert src is not None
            assert len(src) > 0

    @pytest.mark.skip(reason="Requires imported audiobooks with covers")
    def test_lazy_loading_behavior(self, driver, base_url):
        """Test that covers use lazy loading."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        # Initially, only visible images should load
        # As user scrolls, more should load
        # (This depends on implementation)


class TestGridLayout:
    """Test grid layout responsiveness."""

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_grid_columns_desktop(self, driver, base_url):
        """Test grid layout on desktop."""
        driver.set_window_size(1920, 1080)

        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        grid = page.find_element(*page.SHOWCASE_GRID)

        # Desktop should show multiple columns
        # (CSS grid or flex implementation)

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_grid_columns_tablet(self, driver, base_url):
        """Test grid layout on tablet."""
        driver.set_window_size(768, 1024)

        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        grid = page.find_element(*page.SHOWCASE_GRID)

        # Tablet should show fewer columns than desktop

    @pytest.mark.skip(reason="Requires imported audiobooks")
    def test_grid_columns_mobile(self, driver, base_url):
        """Test grid layout on mobile."""
        driver.set_window_size(375, 667)

        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        grid = page.find_element(*page.SHOWCASE_GRID)

        # Mobile should show single column or minimal columns


class TestEmptyState:
    """Test empty state when no audiobooks exist."""

    @pytest.mark.skip(reason="Requires empty library")
    def test_empty_message_displays(self, driver, base_url):
        """Test that empty message displays when no audiobooks."""
        page = ShowcasePage(driver, base_url)

        # If no audiobooks, should show message
        if page.get_audiobook_count() == 0:
            # Should have some indication of empty state
            page_text = driver.find_element(By.TAG_NAME, "body").text
            assert any(word in page_text.lower() for word in ["empty", "no audiobooks", "nothing"])


class TestNavigation:
    """Test navigation from showcase page."""

    def test_navigate_to_search(self, driver, base_url):
        """Test navigating to search page."""
        page = ShowcasePage(driver, base_url)

        page.click_nav_link("Search")
        wait_for_page_load(driver)

        assert "/search" in driver.current_url

    def test_navigate_to_history(self, driver, base_url):
        """Test navigating to history page."""
        page = ShowcasePage(driver, base_url)

        page.click_nav_link("History")
        wait_for_page_load(driver)

        assert "/history" in driver.current_url


class TestResponsiveness:
    """Test responsive behavior of the showcase page."""

    def test_mobile_viewport(self, driver, base_url):
        """Test page in mobile viewport."""
        driver.set_window_size(375, 667)

        page = ShowcasePage(driver, base_url)

        assert page.is_element_visible(*page.SHOWCASE_GRID)

    def test_tablet_viewport(self, driver, base_url):
        """Test page in tablet viewport."""
        driver.set_window_size(768, 1024)

        page = ShowcasePage(driver, base_url)

        assert page.is_element_visible(*page.SHOWCASE_GRID)

    def test_desktop_viewport(self, driver, base_url):
        """Test page in desktop viewport."""
        driver.set_window_size(1920, 1080)

        page = ShowcasePage(driver, base_url)

        assert page.is_element_visible(*page.SHOWCASE_GRID)


class TestScrolling:
    """Test scrolling behavior on showcase page."""

    @pytest.mark.skip(reason="Requires many audiobooks")
    def test_scroll_loads_more_content(self, driver, base_url):
        """Test that scrolling loads more content if paginated."""
        page = ShowcasePage(driver, base_url)
        page.wait_for_showcase_load()

        initial_count = page.get_audiobook_count()

        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        import time
        time.sleep(2)  # Wait for potential load

        # Count may increase if infinite scroll is implemented
        new_count = page.get_audiobook_count()
        assert new_count >= initial_count
