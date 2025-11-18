"""
Tests for unified description service.
Tests cascading fallback logic: ABS → Hardcover → None
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def description_service():
    """Create a fresh description service instance for each test."""
    from description_service import DescriptionService
    service = DescriptionService()
    service._cache.clear()  # Clear cache before each test
    return service


@pytest.fixture
def mock_abs_client():
    """Mock ABS client."""
    with patch("description_service.abs_client") as mock:
        mock.is_configured = True
        mock._get_cached_library_items = AsyncMock(return_value=[])
        mock.fetch_item_details = AsyncMock(return_value=None)
        yield mock


@pytest.fixture
def mock_hardcover_client():
    """Mock Hardcover client."""
    with patch("description_service.hardcover_client") as mock:
        mock.is_configured = True
        mock.search_book_by_title = AsyncMock(return_value=None)
        yield mock


class TestDescriptionServiceCacheKeys:
    """Test cache key generation."""

    def test_cache_key_with_abs_item_id(self, description_service):
        """Should use abs_item_id as most specific cache key."""
        key = description_service._get_cache_key(
            title="Test Book",
            author="Test Author",
            abs_item_id="li_abc123"
        )
        assert key == "desc:abs:li_abc123"

    def test_cache_key_with_asin(self, description_service):
        """Should use ASIN when no abs_item_id provided."""
        key = description_service._get_cache_key(
            title="Test Book",
            author="Test Author",
            asin="B003P2WO5E"
        )
        assert key == "desc:asin:b003p2wo5e"

    def test_cache_key_with_isbn(self, description_service):
        """Should use ISBN when no ASIN or abs_item_id provided."""
        key = description_service._get_cache_key(
            title="Test Book",
            author="Test Author",
            isbn="9780765365279"
        )
        assert key == "desc:isbn:9780765365279"

    def test_cache_key_with_title_author(self, description_service):
        """Should use title+author when no identifiers provided."""
        key = description_service._get_cache_key(
            title="Test Book",
            author="Test Author"
        )
        assert key == "desc:title:test book|test author"

    def test_cache_key_with_title_only(self, description_service):
        """Should use title only when no author or identifiers."""
        key = description_service._get_cache_key(title="Test Book")
        assert key == "desc:title:test book"


class TestDescriptionServiceABS:
    """Test ABS description fetching."""

    @pytest.mark.asyncio
    async def test_abs_success_with_item_id(self, description_service, mock_abs_client):
        """Should fetch from ABS using item_id directly."""
        # Mock ABS response
        mock_abs_client.fetch_item_details.return_value = {
            "description": "A great book",
            "metadata": {"title": "Test Book", "authorName": "Test Author"}
        }

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author",
            abs_item_id="li_abc123"
        )

        assert result["description"] == "A great book"
        assert result["source"] == "abs"
        assert result["cached"] is False
        mock_abs_client.fetch_item_details.assert_called_once_with("li_abc123")

    @pytest.mark.asyncio
    async def test_abs_success_with_library_search(self, description_service, mock_abs_client):
        """Should search ABS library and find match."""
        # Mock library items
        mock_abs_client._get_cached_library_items.return_value = [
            {
                "id": "li_found123",
                "media": {
                    "metadata": {
                        "title": "Test Book",
                        "authorName": "Test Author",
                        "asin": "",
                        "isbn": ""
                    }
                }
            }
        ]

        # Mock item details fetch
        mock_abs_client.fetch_item_details.return_value = {
            "description": "Found in library",
            "metadata": {"title": "Test Book"}
        }

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["description"] == "Found in library"
        assert result["source"] == "abs"
        mock_abs_client.fetch_item_details.assert_called_once_with("li_found123")

    @pytest.mark.asyncio
    async def test_abs_match_with_asin(self, description_service, mock_abs_client):
        """Should match by ASIN with high priority."""
        # Mock library items with ASIN match
        mock_abs_client._get_cached_library_items.return_value = [
            {
                "id": "li_asin_match",
                "media": {
                    "metadata": {
                        "title": "Different Title",  # Title doesn't match
                        "authorName": "Different Author",
                        "asin": "B003P2WO5E",
                        "isbn": ""
                    }
                }
            }
        ]

        mock_abs_client.fetch_item_details.return_value = {
            "description": "Matched by ASIN",
            "metadata": {}
        }

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author",
            asin="B003P2WO5E"
        )

        assert result["description"] == "Matched by ASIN"
        assert result["source"] == "abs"

    @pytest.mark.asyncio
    async def test_abs_not_configured(self, description_service, mock_abs_client):
        """Should skip ABS when not configured."""
        mock_abs_client.is_configured = False

        result = await description_service._try_abs(
            title="Test Book",
            author="Test Author",
            asin="",
            isbn="",
            abs_item_id=None
        )

        assert result is None


class TestDescriptionServiceHardcover:
    """Test Hardcover description fetching."""

    @pytest.mark.asyncio
    async def test_hardcover_success(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should fetch from Hardcover when ABS fails."""
        # Mock ABS failure
        mock_abs_client._get_cached_library_items.return_value = []

        # Mock Hardcover success
        mock_hardcover_client.search_book_by_title.return_value = {
            "book_id": 12345,
            "title": "Test Book",
            "description": "From Hardcover",
            "authors": ["Test Author"],
            "series_names": [],
            "published_year": 2020
        }

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["description"] == "From Hardcover"
        assert result["source"] == "hardcover"
        assert result["metadata"]["book_id"] == 12345
        mock_hardcover_client.search_book_by_title.assert_called_once_with("Test Book", "Test Author")

    @pytest.mark.asyncio
    async def test_hardcover_not_configured(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should skip Hardcover when not configured."""
        mock_abs_client._get_cached_library_items.return_value = []
        mock_hardcover_client.is_configured = False

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["source"] == "none"
        assert result["description"] == ""
        mock_hardcover_client.search_book_by_title.assert_not_called()

    @pytest.mark.asyncio
    async def test_hardcover_disabled(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should skip Hardcover when fallback disabled."""
        mock_abs_client._get_cached_library_items.return_value = []
        description_service.fallback_enabled = False

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["source"] == "none"
        mock_hardcover_client.search_book_by_title.assert_not_called()


class TestDescriptionServiceFallback:
    """Test fallback logic and source priority."""

    @pytest.mark.asyncio
    async def test_abs_preferred_over_hardcover(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should prefer ABS description over Hardcover."""
        # Mock both sources having descriptions
        mock_abs_client._get_cached_library_items.return_value = [
            {
                "id": "li_abc",
                "media": {
                    "metadata": {
                        "title": "Test Book",
                        "authorName": "Test Author",
                        "asin": "",
                        "isbn": ""
                    }
                }
            }
        ]
        mock_abs_client.fetch_item_details.return_value = {
            "description": "From ABS",
            "metadata": {}
        }

        mock_hardcover_client.search_book_by_title.return_value = {
            "description": "From Hardcover",
            "book_id": 123
        }

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["source"] == "abs"
        assert result["description"] == "From ABS"
        # Hardcover should not be called since ABS succeeded
        mock_hardcover_client.search_book_by_title.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_hardcover_on_abs_empty(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should fallback to Hardcover if ABS returns empty description."""
        # Mock ABS with empty description
        mock_abs_client._get_cached_library_items.return_value = [
            {
                "id": "li_abc",
                "media": {
                    "metadata": {
                        "title": "Test Book",
                        "authorName": "Test Author",
                        "asin": "",
                        "isbn": ""
                    }
                }
            }
        ]
        mock_abs_client.fetch_item_details.return_value = {
            "description": "",  # Empty description
            "metadata": {}
        }

        # Mock Hardcover with description
        mock_hardcover_client.search_book_by_title.return_value = {
            "description": "From Hardcover",
            "book_id": 123,
            "title": "Test Book",
            "authors": ["Test Author"]
        }

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["source"] == "hardcover"
        assert result["description"] == "From Hardcover"

    @pytest.mark.asyncio
    async def test_no_description_from_any_source(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should return 'none' when no source has description."""
        mock_abs_client._get_cached_library_items.return_value = []
        mock_hardcover_client.search_book_by_title.return_value = None

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["source"] == "none"
        assert result["description"] == ""


class TestDescriptionServiceCaching:
    """Test caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, description_service, mock_abs_client):
        """Should return cached result on second call."""
        # Mock ABS response
        mock_abs_client._get_cached_library_items.return_value = [
            {
                "id": "li_abc",
                "media": {
                    "metadata": {
                        "title": "Test Book",
                        "authorName": "Test Author",
                        "asin": "",
                        "isbn": ""
                    }
                }
            }
        ]
        mock_abs_client.fetch_item_details.return_value = {
            "description": "Cached description",
            "metadata": {}
        }

        # First call - should hit ABS
        result1 = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )
        assert result1["cached"] is False
        assert mock_abs_client.fetch_item_details.call_count == 1

        # Second call - should hit cache
        result2 = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )
        assert result2["cached"] is True
        assert result2["description"] == "Cached description"
        # Should not call ABS again
        assert mock_abs_client.fetch_item_details.call_count == 1

    @pytest.mark.asyncio
    async def test_force_refresh_skips_cache(self, description_service, mock_abs_client):
        """Should skip cache when force_refresh=True."""
        # Setup mock
        mock_abs_client._get_cached_library_items.return_value = [
            {
                "id": "li_abc",
                "media": {
                    "metadata": {
                        "title": "Test Book",
                        "authorName": "Test Author",
                        "asin": "",
                        "isbn": ""
                    }
                }
            }
        ]
        mock_abs_client.fetch_item_details.return_value = {
            "description": "Fresh description",
            "metadata": {}
        }

        # First call to populate cache
        await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        # Second call with force_refresh - should call ABS again
        result = await description_service.get_description(
            title="Test Book",
            author="Test Author",
            force_refresh=True
        )

        assert result["cached"] is False
        assert mock_abs_client.fetch_item_details.call_count == 2

    def test_clear_cache(self, description_service):
        """Should clear cache when requested."""
        # Manually add to cache
        description_service._cache["test_key"] = ({"description": "test"}, 12345)
        assert len(description_service._cache) == 1

        # Clear cache
        description_service.clear_cache()
        assert len(description_service._cache) == 0

    def test_cache_stats(self, description_service):
        """Should return cache statistics."""
        import time

        # Add some cached entries
        current_time = time.time()
        description_service._cache["key1"] = ({"description": "test1"}, current_time)
        description_service._cache["key2"] = ({"description": "test2"}, current_time - 100000)  # Expired

        stats = description_service.get_cache_stats()

        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 1  # Only one is not expired
        assert stats["cache_ttl"] == description_service.cache_ttl
        assert "fallback_enabled" in stats


class TestDescriptionServiceEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_title(self, description_service):
        """Should handle empty title gracefully."""
        result = await description_service.get_description(title="")

        assert result["source"] == "none"
        assert result["description"] == ""

    @pytest.mark.asyncio
    async def test_abs_exception(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should fallback to Hardcover if ABS raises exception."""
        # Mock ABS raising exception
        mock_abs_client._get_cached_library_items.side_effect = Exception("ABS error")

        # Mock Hardcover success
        mock_hardcover_client.search_book_by_title.return_value = {
            "description": "From Hardcover after ABS error",
            "book_id": 123,
            "title": "Test Book",
            "authors": ["Test Author"]
        }

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["source"] == "hardcover"
        assert result["description"] == "From Hardcover after ABS error"

    @pytest.mark.asyncio
    async def test_hardcover_exception(self, description_service, mock_abs_client, mock_hardcover_client):
        """Should handle Hardcover exception gracefully."""
        mock_abs_client._get_cached_library_items.return_value = []
        mock_hardcover_client.search_book_by_title.side_effect = Exception("Hardcover error")

        result = await description_service.get_description(
            title="Test Book",
            author="Test Author"
        )

        assert result["source"] == "none"
        assert result["description"] == ""
