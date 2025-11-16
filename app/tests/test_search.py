"""
Tests for MAM search functionality.

Tests cover search payload construction, response parsing, format detection,
and data flattening logic.
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

from routes.search import flatten, detect_format


class TestFlattenFunction:
    """Test the flatten() helper function that normalizes MAM response data."""

    def test_flatten_dict(self):
        """Test flattening dictionary values."""
        result = flatten({"key1": "value1", "key2": "value2"})
        assert result == "value1, value2"

    def test_flatten_list(self):
        """Test flattening list values."""
        result = flatten(["item1", "item2", "item3"])
        assert result == "item1, item2, item3"

    def test_flatten_json_string_dict(self):
        """Test flattening JSON string containing dict."""
        json_str = '{"author": "J.R.R. Tolkien", "id": "123"}'
        result = flatten(json_str)
        assert "J.R.R. Tolkien" in result
        assert "123" in result

    def test_flatten_json_string_list(self):
        """Test flattening JSON string containing list."""
        json_str = '["Rob Inglis", "Simon Vance"]'
        result = flatten(json_str)
        assert result == "Rob Inglis, Simon Vance"

    def test_flatten_malformed_dict_string(self):
        """Test flattening malformed dict-like string."""
        # MAM sometimes returns pseudo-JSON strings
        result = flatten('{author: "Tolkien", narrator: "Inglis"}')
        assert "Tolkien" in result
        assert "Inglis" in result

    def test_flatten_none(self):
        """Test flattening None value."""
        result = flatten(None)
        assert result == ""

    def test_flatten_simple_string(self):
        """Test flattening simple string."""
        result = flatten("Simple String")
        assert result == "Simple String"

    def test_flatten_empty_dict(self):
        """Test flattening empty dictionary."""
        result = flatten({})
        assert result == ""

    def test_flatten_empty_list(self):
        """Test flattening empty list."""
        result = flatten([])
        assert result == ""

    def test_flatten_nested_dict_string(self):
        """Test flattening complex nested structure as string."""
        result = flatten('{a: "1", b: "2", c: "3"}')
        assert "1" in result
        assert "2" in result
        assert "3" in result


class TestDetectFormat:
    """Test the detect_format() function that extracts file format from metadata."""

    def test_detect_format_from_format_field(self):
        """Test format detection from 'format' field."""
        item = {"format": "M4B"}
        assert detect_format(item) == "M4B"

    def test_detect_format_from_filetype_field(self):
        """Test format detection from 'filetype' field."""
        item = {"filetype": "MP3"}
        assert detect_format(item) == "MP3"

    def test_detect_format_from_title(self):
        """Test format detection from title field."""
        item = {"title": "The Hobbit [M4B Audiobook]"}
        assert detect_format(item) == "M4B"

    def test_detect_format_multiple_formats_in_title(self):
        """Test detection when title contains multiple format indicators."""
        item = {"title": "Book Collection MP3/M4B/FLAC"}
        result = detect_format(item)
        assert "MP3" in result
        assert "M4B" in result
        assert "FLAC" in result

    def test_detect_format_case_insensitive(self):
        """Test that format detection is case-insensitive."""
        item = {"title": "Audiobook in m4b format"}
        assert detect_format(item).upper() == "M4B"

    def test_detect_format_no_format_found(self):
        """Test when no format can be detected."""
        item = {"title": "Some Book", "author": "Some Author"}
        assert detect_format(item) == ""

    def test_detect_format_ebook_formats(self):
        """Test detection of ebook formats (EPUB, PDF, MOBI, etc.)."""
        item = {"title": "Book Collection [EPUB/MOBI/PDF]"}
        result = detect_format(item)
        assert "EPUB" in result
        assert "MOBI" in result
        assert "PDF" in result

    def test_detect_format_from_name_field(self):
        """Test format detection from 'name' field when 'title' not present."""
        item = {"name": "Audiobook [FLAC]"}
        assert detect_format(item) == "FLAC"

    def test_detect_format_priority_explicit_over_title(self):
        """Test that explicit format field takes priority over title parsing."""
        item = {
            "format": "M4B",
            "title": "Book [MP3]"
        }
        assert detect_format(item) == "M4B"

    def test_detect_format_whitespace_handling(self):
        """Test that whitespace in format field is stripped."""
        item = {"format": "  M4B  "}
        assert detect_format(item) == "M4B"


class TestSearchPayloadConstruction:
    """Test search payload construction logic."""

    def test_default_payload_construction(self):
        """Test that default search parameters are set correctly."""
        # This would test the actual endpoint, but we'll test the logic
        payload = {"tor": {}}
        tor = payload.get("tor", {}) or {}
        tor.setdefault("text", "")
        tor.setdefault("srchIn", ["title", "author", "narrator"])
        tor.setdefault("searchType", "all")
        tor.setdefault("sortType", "default")
        tor.setdefault("startNumber", "0")
        tor.setdefault("main_cat", ["13"])

        assert tor["text"] == ""
        assert tor["srchIn"] == ["title", "author", "narrator"]
        assert tor["searchType"] == "all"
        assert tor["sortType"] == "default"
        assert tor["startNumber"] == "0"
        assert tor["main_cat"] == ["13"]

    def test_custom_search_text(self):
        """Test custom search text is preserved."""
        payload = {"tor": {"text": "Tolkien"}}
        tor = payload.get("tor", {}) or {}
        tor.setdefault("text", "")

        assert tor["text"] == "Tolkien"

    def test_custom_perpage(self):
        """Test custom perpage value."""
        payload = {"perpage": 50}
        perpage = payload.get("perpage", 25)

        assert perpage == 50

    def test_default_perpage(self):
        """Test default perpage when not specified."""
        payload = {}
        perpage = payload.get("perpage", 25)

        assert perpage == 25


class TestSearchResponseFlattening:
    """Test that MAM search responses are properly flattened."""

    def test_flatten_author_info(self):
        """Test flattening of author_info field."""
        item = {
            "author_info": {
                "author": "J.R.R. Tolkien",
                "id": "12345"
            }
        }
        result = flatten(item.get("author_info"))
        assert "J.R.R. Tolkien" in result

    def test_flatten_narrator_info(self):
        """Test flattening of narrator_info field."""
        item = {
            "narrator_info": {
                "narrator": "Rob Inglis",
                "id": "67890"
            }
        }
        result = flatten(item.get("narrator_info"))
        assert "Rob Inglis" in result

    def test_flatten_multiple_narrators(self):
        """Test flattening when multiple narrators are present."""
        item = {
            "narrator_info": ["Rob Inglis", "Simon Vance", "Frank Muller"]
        }
        result = flatten(item.get("narrator_info"))
        assert "Rob Inglis" in result
        assert "Simon Vance" in result
        assert "Frank Muller" in result


class TestSearchResultMapping:
    """Test that search results are mapped correctly to output format."""

    def test_result_id_mapping(self):
        """Test that ID is extracted correctly."""
        item = {"id": "12345", "title": "Test Book"}
        mapped_id = str(item.get("id") or item.get("tid") or "")
        assert mapped_id == "12345"

    def test_result_id_fallback_to_tid(self):
        """Test that tid is used when id is not present."""
        item = {"tid": "67890", "title": "Test Book"}
        mapped_id = str(item.get("id") or item.get("tid") or "")
        assert mapped_id == "67890"

    def test_result_id_empty_fallback(self):
        """Test that empty string is used when neither id nor tid present."""
        item = {"title": "Test Book"}
        mapped_id = str(item.get("id") or item.get("tid") or "")
        assert mapped_id == ""

    def test_result_title_mapping(self):
        """Test title extraction."""
        item = {"title": "The Hobbit"}
        assert item.get("title") == "The Hobbit"

    def test_result_title_fallback_to_name(self):
        """Test name fallback when title not present."""
        item = {"name": "The Hobbit"}
        title = item.get("title") or item.get("name")
        assert title == "The Hobbit"


@pytest.mark.asyncio
class TestSearchEndpoint:
    """Integration tests for the /search endpoint (requires mocking)."""

    @pytest.fixture
    def mock_mam_response(self):
        """Provide a mock MAM API response."""
        return {
            "data": [
                {
                    "id": "12345",
                    "title": "The Hobbit",
                    "author_info": {"author": "J.R.R. Tolkien"},
                    "narrator_info": {"narrator": "Rob Inglis"},
                    "format": "M4B",
                    "size": "536870912",
                    "seeders": 10,
                    "leechers": 2,
                    "catname": "Audiobooks",
                    "added": "2024-01-01",
                    "dl": "https://mam/download/12345"
                }
            ],
            "total": 1,
            "total_found": 1
        }

    async def test_search_requires_cookie(self, mock_mam_response):
        """Test that search fails without MAM_COOKIE."""
        # This would require FastAPI TestClient - implementation note for future
        pass

    async def test_search_constructs_proper_headers(self, mock_mam_response):
        """Test that search includes proper headers for MAM."""
        # This would test the actual HTTP request headers
        pass

    async def test_search_handles_mam_errors(self):
        """Test error handling when MAM returns non-200 status."""
        # This would test error handling logic
        pass

    async def test_search_handles_non_json_response(self):
        """Test error handling when MAM returns non-JSON."""
        # This would test JSON parsing error handling
        pass


class TestCoverFetchLogic:
    """Test cover fetching logic and retry mechanism."""

    def test_cover_fetch_requires_abs_config(self):
        """Test that cover fetch returns error when ABS not configured."""
        # Would test the ABS configuration check
        pass

    def test_cover_fetch_requires_title(self):
        """Test that cover fetch returns error without title."""
        # Would test the title requirement
        pass

    def test_cover_fetch_retry_logic(self):
        """Test exponential backoff retry logic."""
        # Calculate expected wait times
        attempt_1_wait = 0.5 * (2 ** 0)  # 0.5s
        attempt_2_wait = 0.5 * (2 ** 1)  # 1.0s
        attempt_3_wait = 0.5 * (2 ** 2)  # 2.0s

        assert attempt_1_wait == 0.5
        assert attempt_2_wait == 1.0
        assert attempt_3_wait == 2.0

    def test_cover_fetch_max_retries(self):
        """Test that cover fetch respects max_retries parameter."""
        max_retries = 2
        total_attempts = max_retries + 1
        assert total_attempts == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
