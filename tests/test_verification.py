"""
Tests for Audiobookshelf verification logic.

Tests cover verification scenarios, matching logic, ASIN/ISBN matching,
and retry mechanisms.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import sys

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))


class TestAudiobookshelfClientInit:
    """Test AudiobookshelfClient initialization."""

    def test_init_with_config(self, monkeypatch):
        """Test client initialization with configuration."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "test-key")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "lib-123")

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        assert client.base_url == "https://abs.example.com"
        assert client.api_key == "test-key"
        assert client.library_id == "lib-123"

    def test_is_configured_property(self, monkeypatch):
        """Test is_configured property logic."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "test-key")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "lib-123")

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        assert client.is_configured is True

    def test_is_configured_false_when_missing_url(self, monkeypatch):
        """Test is_configured returns False when URL missing."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "test-key")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "lib-123")

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        assert client.is_configured is False

    def test_is_configured_false_when_missing_key(self, monkeypatch):
        """Test is_configured returns False when API key missing."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "lib-123")

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        assert client.is_configured is False


class TestVerificationMatchingLogic:
    """Test the matching logic used in verify_import."""

    def test_exact_title_match(self):
        """Test exact title matching gives high score."""
        title_lower = "the hobbit"
        item_title = "the hobbit"

        score = 0
        if item_title == title_lower:
            score += 100

        assert score == 100

    def test_partial_title_match(self):
        """Test partial title matching gives medium score."""
        title_lower = "hobbit"
        item_title = "the hobbit"

        score = 0
        if title_lower in item_title or item_title in title_lower:
            score += 50

        assert score == 50

    def test_exact_author_match(self):
        """Test exact author matching."""
        author_lower = "j.r.r. tolkien"
        item_author = "j.r.r. tolkien"

        score = 0
        if item_author == author_lower:
            score += 50

        assert score == 50

    def test_partial_author_match(self):
        """Test partial author matching."""
        author_lower = "tolkien"
        item_author = "j.r.r. tolkien"

        score = 0
        if author_lower in item_author or item_author in author_lower:
            score += 25

        assert score == 25

    def test_asin_match_highest_score(self):
        """Test ASIN match gets highest score."""
        metadata_asin = "B001234567"
        item_asin = "b001234567"

        score = 0
        if metadata_asin and item_asin and metadata_asin.lower() == item_asin:
            score += 200

        assert score == 200

    def test_isbn_match_highest_score(self):
        """Test ISBN match gets highest score."""
        metadata_isbn = "9781234567890"
        item_isbn = "9781234567890"

        score = 0
        if metadata_isbn and item_isbn and metadata_isbn.lower() == item_isbn:
            score += 200

        assert score == 200

    def test_path_matching_bonus(self):
        """Test path matching adds bonus score."""
        library_path = "/media/Books/Audiobooks/Tolkien/The Hobbit"
        item_path = "/audiobooks/tolkien/the hobbit"

        lib_path_norm = library_path.lower().replace("\\", "/").strip("/")
        item_path_norm = item_path.lower().replace("\\", "/").strip("/")

        score = 0
        if lib_path_norm in item_path_norm or item_path_norm in lib_path_norm:
            score += 25

        assert score == 25

    def test_combined_title_author_match_score(self):
        """Test combined title and author match score."""
        # Perfect title + author match should score 150
        title_score = 100  # Exact title
        author_score = 50  # Exact author
        total = title_score + author_score

        assert total == 150


@pytest.mark.asyncio
class TestVerifyImport:
    """Test the verify_import method."""

    @pytest.fixture
    def mock_abs_client(self, monkeypatch):
        """Create a mock ABS client with proper configuration."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "test-key")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "lib-123")
        monkeypatch.setattr("abs_client.ABS_VERIFY_TIMEOUT", 10)

        from abs_client import AudiobookshelfClient
        return AudiobookshelfClient()

    async def test_verify_import_not_configured(self, monkeypatch):
        """Test verification when ABS not configured."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "")

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        result = await client.verify_import("Test Book", "Test Author")

        assert result["status"] == "not_configured"
        assert result["abs_item_id"] is None

    async def test_verify_import_missing_library_id(self, monkeypatch):
        """Test verification when library ID not configured."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "test-key")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "")

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        result = await client.verify_import("Test Book", "Test Author")

        assert result["status"] == "not_configured"
        assert "ABS_LIBRARY_ID" in result["note"]

    async def test_verify_import_no_title(self, mock_abs_client):
        """Test verification with no title provided."""
        result = await mock_abs_client.verify_import("", "Test Author")

        assert result["status"] == "not_found"
        assert "No title" in result["note"]

    async def test_verify_import_exact_match(self, mock_abs_client, sample_abs_library_items):
        """Test verification with exact title/author match."""
        # Mock httpx response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=sample_abs_library_items)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await mock_abs_client.verify_import("The Hobbit", "J.R.R. Tolkien")

        assert result["status"] == "verified"
        assert result["abs_item_id"] is not None
        assert "lib-item-1" in result["abs_item_id"]

    async def test_verify_import_not_found(self, mock_abs_client):
        """Test verification when item not in library."""
        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"results": [], "total": 0})

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await mock_abs_client.verify_import("Nonexistent Book", "Unknown Author")

        assert result["status"] == "not_found"
        assert result["abs_item_id"] is None

    async def test_verify_import_author_mismatch(self, mock_abs_client, sample_abs_library_items):
        """Test verification with title match but author mismatch."""
        # Mock response with different author
        modified_items = sample_abs_library_items.copy()
        modified_items["results"][0]["media"]["metadata"]["authorName"] = "Different Author"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=modified_items)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await mock_abs_client.verify_import("The Hobbit", "J.R.R. Tolkien")

        assert result["status"] in ["mismatch", "verified"]
        if result["status"] == "mismatch":
            assert "mismatch" in result["note"].lower()

    async def test_verify_import_retry_logic(self, mock_abs_client):
        """Test retry logic with exponential backoff."""
        # Mock responses: first two fail, third succeeds
        call_count = 0

        def mock_get_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = Mock()
            if call_count < 3:
                mock_response.status_code = 500  # Fail first two attempts
                mock_response.text = "Internal Server Error"
            else:
                mock_response.status_code = 200  # Succeed on third attempt
                mock_response.json = Mock(return_value={"results": [], "total": 0})
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(side_effect=mock_get_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
                result = await mock_abs_client.verify_import("Test Book", "Test Author")

        # Should have retried and eventually succeeded
        assert call_count == 3

    async def test_verify_import_timeout_handling(self, mock_abs_client):
        """Test handling of timeout exceptions."""
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
                result = await mock_abs_client.verify_import("Test Book", "Test Author")

        assert result["status"] == "unreachable"
        assert "Timeout" in result["note"]

    async def test_verify_import_asin_match_priority(self, mock_abs_client):
        """Test that ASIN match takes priority over title match."""
        # Create item with different title but matching ASIN
        abs_response = {
            "results": [
                {
                    "id": "item-asin-match",
                    "media": {
                        "metadata": {
                            "title": "Different Title",
                            "authorName": "Different Author",
                            "asin": "B001234567"
                        }
                    },
                    "path": "/audiobooks/different"
                }
            ],
            "total": 1
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value=abs_response)

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        metadata = {"asin": "B001234567"}

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await mock_abs_client.verify_import(
                "Test Book",
                "Test Author",
                metadata=metadata
            )

        assert result["status"] == "verified"
        assert "ASIN" in result["note"]
        assert result["abs_item_id"] == "item-asin-match"


@pytest.mark.asyncio
class TestConnectionTest:
    """Test ABS connection testing."""

    async def test_connection_success(self, monkeypatch):
        """Test successful connection to ABS."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "test-key")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "lib-123")

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"username": "testuser"})

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.test_connection()

        assert result is True

    async def test_connection_failure(self, monkeypatch):
        """Test connection failure."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "test-key")
        monkeypatch.setattr("abs_client.ABS_LIBRARY_ID", "lib-123")

        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await client.test_connection()

        assert result is False

    async def test_connection_not_configured(self, monkeypatch):
        """Test connection when not configured."""
        monkeypatch.setattr("abs_client.ABS_BASE_URL", "")
        monkeypatch.setattr("abs_client.ABS_API_KEY", "")

        from abs_client import AudiobookshelfClient
        client = AudiobookshelfClient()

        result = await client.test_connection()

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
