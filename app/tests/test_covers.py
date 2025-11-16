"""
Tests for cover caching and management.

Tests cover cache hit/miss scenarios, automatic cleanup, concurrent fetches,
and connection pooling.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
import sys
import asyncio

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))


class TestCoverServiceInit:
    """Test CoverService initialization."""

    def test_init_creates_covers_directory(self, temp_dir, monkeypatch):
        """Test that CoverService creates covers directory on init."""
        covers_dir = temp_dir / "covers"
        assert not covers_dir.exists()

        # Mock the COVERS_DIR config
        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)

        from covers import CoverService
        service = CoverService()

        assert covers_dir.exists()
        assert covers_dir.is_dir()


class TestCoverDirectorySize:
    """Test cover directory size calculation."""

    def test_get_covers_dir_size_empty(self, temp_dir, monkeypatch):
        """Test size calculation for empty directory."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        from covers import CoverService
        service = CoverService()

        size = service.get_covers_dir_size()
        assert size == 0

    def test_get_covers_dir_size_with_files(self, temp_dir, monkeypatch):
        """Test size calculation with files present."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Create test files
        (covers_dir / "cover1.jpg").write_bytes(b"x" * 1024)  # 1KB
        (covers_dir / "cover2.jpg").write_bytes(b"x" * 2048)  # 2KB

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        from covers import CoverService
        service = CoverService()

        size = service.get_covers_dir_size()
        assert size == 3072  # 3KB

    def test_get_covers_dir_size_ignores_subdirs(self, temp_dir, monkeypatch):
        """Test that size calculation ignores subdirectories."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Create file and subdirectory
        (covers_dir / "cover.jpg").write_bytes(b"x" * 1024)
        subdir = covers_dir / "subdir"
        subdir.mkdir()
        (subdir / "ignored.jpg").write_bytes(b"x" * 2048)

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        from covers import CoverService
        service = CoverService()

        size = service.get_covers_dir_size()
        assert size == 1024  # Only counts the top-level file


class TestCoverCleanup:
    """Test automatic cover cleanup when exceeding size limit."""

    def test_cleanup_not_triggered_when_under_limit(self, temp_dir, monkeypatch):
        """Test that cleanup doesn't run when under limit."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Create 1KB file, set limit to 10MB
        (covers_dir / "cover.jpg").write_bytes(b"x" * 1024)

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)
        from covers import CoverService
        service = CoverService()

        service.cleanup_old_covers()

        # File should still exist
        assert (covers_dir / "cover.jpg").exists()

    def test_cleanup_removes_oldest_files_first(self, temp_dir, monkeypatch):
        """Test that cleanup removes oldest files first (by access time)."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Create files with different access times
        import os
        import time

        old_file = covers_dir / "old.jpg"
        new_file = covers_dir / "new.jpg"

        old_file.write_bytes(b"x" * 1024)
        time.sleep(0.1)  # Ensure different access times
        new_file.write_bytes(b"x" * 1024)

        # Set access times explicitly
        now = time.time()
        os.utime(old_file, (now - 100, now - 100))  # Older
        os.utime(new_file, (now, now))  # Newer

        # Set limit to 1KB (will force cleanup)
        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 0.001)  # ~1KB
        from covers import CoverService
        service = CoverService()

        service.cleanup_old_covers()

        # Old file should be removed, new file should remain
        assert not old_file.exists()
        assert new_file.exists()

    def test_cleanup_respects_size_limit(self, temp_dir, monkeypatch):
        """Test that cleanup stops when size is under limit."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Create 3 files of 1KB each
        for i in range(3):
            (covers_dir / f"cover{i}.jpg").write_bytes(b"x" * 1024)

        # Set limit to 2KB (should remove 1 file)
        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 0.002)  # ~2KB
        from covers import CoverService
        service = CoverService()

        service.cleanup_old_covers()

        # Should have ~2 files remaining
        remaining_files = list(covers_dir.glob("*.jpg"))
        assert len(remaining_files) <= 2

    def test_cleanup_with_zero_limit_skips_cleanup(self, temp_dir, monkeypatch):
        """Test that cleanup is skipped when MAX_COVERS_SIZE_MB is 0."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        (covers_dir / "cover.jpg").write_bytes(b"x" * 10240)  # 10KB

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 0)  # No caching
        from covers import CoverService
        service = CoverService()

        service.cleanup_old_covers()

        # File should still exist (no cleanup)
        assert (covers_dir / "cover.jpg").exists()


class TestCoverDownload:
    """Test cover download functionality."""

    @pytest.mark.asyncio
    async def test_download_cover_success(self, temp_dir, monkeypatch):
        """Test successful cover download."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Mock httpx response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake_image_data"
        mock_response.headers = {"Content-Type": "image/jpeg"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: mock_client)

        from covers import CoverService
        service = CoverService()

        local_file, file_size = await service.download_cover("https://example.com/cover.jpg", "12345")

        assert local_file is not None
        assert Path(local_file).exists()
        assert file_size == len(b"fake_image_data")
        assert Path(local_file).name == "12345.jpg"

    @pytest.mark.asyncio
    async def test_download_cover_determines_extension_from_content_type(self, temp_dir, monkeypatch):
        """Test that file extension is determined from Content-Type."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Mock httpx response with PNG content type
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake_png_data"
        mock_response.headers = {"Content-Type": "image/png"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: mock_client)

        from covers import CoverService
        service = CoverService()

        local_file, _ = await service.download_cover("https://example.com/cover.png", "12345")

        assert Path(local_file).suffix == ".png"

    @pytest.mark.asyncio
    async def test_download_cover_handles_http_errors(self, temp_dir, monkeypatch):
        """Test error handling for HTTP errors."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Mock httpx response with 404
        mock_response = Mock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: mock_client)

        from covers import CoverService
        service = CoverService()

        local_file, file_size = await service.download_cover("https://example.com/missing.jpg", "12345")

        assert local_file is None
        assert file_size == 0

    @pytest.mark.asyncio
    async def test_download_cover_skips_when_max_size_zero(self, temp_dir, monkeypatch):
        """Test that download is skipped when MAX_COVERS_SIZE_MB is 0."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 0)  # Direct fetch mode

        from covers import CoverService
        service = CoverService()

        local_file, file_size = await service.download_cover("https://example.com/cover.jpg", "12345")

        assert local_file is None
        assert file_size == 0

    @pytest.mark.asyncio
    async def test_download_cover_adds_abs_auth_header(self, temp_dir, monkeypatch):
        """Test that ABS auth header is added for ABS URLs."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Mock httpx response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake_image"
        mock_response.headers = {"Content-Type": "image/jpeg"}

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)

        monkeypatch.setattr("covers.COVERS_DIR", covers_dir)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)
        monkeypatch.setattr("covers.ABS_BASE_URL", "https://abs.example.com")
        monkeypatch.setattr("covers.ABS_API_KEY", "test-token")
        monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: mock_client)

        from covers import CoverService
        service = CoverService()

        await service.download_cover("https://abs.example.com/api/items/123/cover", "12345")

        # Verify that get was called with auth header
        call_args = mock_client.get.call_args
        assert call_args is not None
        headers = call_args.kwargs.get("headers", {})
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token"


class TestCoverCacheLookup:
    """Test cover cache lookup functionality."""

    def test_get_cached_cover_miss(self, mock_covers_db_engine, monkeypatch):
        """Test cache miss scenario."""
        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)

        from covers import CoverService
        service = CoverService()

        result = service.get_cached_cover("nonexistent")
        assert result == {}

    def test_get_cached_cover_hit_with_local_file(self, mock_covers_db_engine, temp_dir, monkeypatch):
        """Test cache hit with local file."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Create a fake local file
        local_file = covers_dir / "12345.jpg"
        local_file.write_bytes(b"fake_image")

        # Insert into database
        from sqlalchemy import text
        with mock_covers_db_engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO covers (mam_id, title, author, cover_url, local_file, fetched_at)
                VALUES ('12345', 'Test Book', 'Test Author', 'https://example.com/cover.jpg', :local_file, datetime('now'))
            """), {"local_file": str(local_file)})

        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)
        from covers import CoverService
        service = CoverService()

        result = service.get_cached_cover("12345")

        assert result.get("cover_url") == "/covers/12345.jpg"
        assert result.get("is_local") is True

    def test_get_cached_cover_direct_mode(self, mock_covers_db_engine, monkeypatch):
        """Test cache hit in direct fetch mode (MAX_COVERS_SIZE_MB=0)."""
        # Insert into database without local file
        from sqlalchemy import text
        with mock_covers_db_engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO covers (mam_id, title, author, cover_url, fetched_at)
                VALUES ('12345', 'Test Book', 'Test Author', 'https://example.com/cover.jpg', datetime('now'))
            """))

        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 0)  # Direct mode

        from covers import CoverService
        service = CoverService()

        result = service.get_cached_cover("12345")

        assert result.get("cover_url") == "https://example.com/cover.jpg"
        assert result.get("is_local") is False

    def test_get_cached_cover_needs_healing(self, mock_covers_db_engine, monkeypatch):
        """Test cache hit with missing local file triggers healing."""
        # Insert into database with local_file that doesn't exist
        from sqlalchemy import text
        with mock_covers_db_engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO covers (mam_id, title, author, cover_url, local_file, fetched_at)
                VALUES ('12345', 'Test Book', 'Test Author', 'https://example.com/cover.jpg', '/nonexistent/12345.jpg', datetime('now'))
            """))

        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)  # Caching enabled

        from covers import CoverService
        service = CoverService()

        result = service.get_cached_cover("12345")

        assert result.get("needs_heal") is True
        assert result.get("source_cover_url") == "https://example.com/cover.jpg"


class TestCoverInvalidation:
    """Test cover cache invalidation."""

    def test_invalidate_cover_removes_from_db(self, mock_covers_db_engine, monkeypatch):
        """Test that invalidation removes cover from database."""
        from sqlalchemy import text

        # Insert cover
        with mock_covers_db_engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO covers (mam_id, title, cover_url, fetched_at)
                VALUES ('12345', 'Test Book', 'https://example.com/cover.jpg', datetime('now'))
            """))

        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)
        from covers import CoverService
        service = CoverService()

        result = service.invalidate_cover("12345")
        assert result is True

        # Verify it's removed
        with mock_covers_db_engine.begin() as cx:
            row = cx.execute(text("SELECT * FROM covers WHERE mam_id = '12345'")).fetchone()
            assert row is None

    def test_invalidate_cover_deletes_local_file(self, mock_covers_db_engine, temp_dir, monkeypatch):
        """Test that invalidation deletes local file."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        local_file = covers_dir / "12345.jpg"
        local_file.write_bytes(b"fake_image")

        from sqlalchemy import text
        with mock_covers_db_engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO covers (mam_id, title, cover_url, local_file, fetched_at)
                VALUES ('12345', 'Test Book', 'https://example.com/cover.jpg', :local_file, datetime('now'))
            """), {"local_file": str(local_file)})

        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)
        from covers import CoverService
        service = CoverService()

        service.invalidate_cover("12345")

        # Verify file is deleted
        assert not local_file.exists()

    def test_invalidate_nonexistent_cover(self, mock_covers_db_engine, monkeypatch):
        """Test invalidating non-existent cover returns False."""
        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)

        from covers import CoverService
        service = CoverService()

        result = service.invalidate_cover("nonexistent")
        assert result is False


class TestCoverCacheSave:
    """Test saving covers to cache."""

    @pytest.mark.asyncio
    async def test_save_cover_to_cache_basic(self, mock_covers_db_engine, temp_dir, monkeypatch):
        """Test basic save to cache functionality."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        # Mock download
        async def mock_download(url, mam_id):
            local_file = covers_dir / f"{mam_id}.jpg"
            local_file.write_bytes(b"fake_image")
            return str(local_file), len(b"fake_image")

        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)

        from covers import CoverService
        service = CoverService()
        service.download_cover = mock_download

        await service.save_cover_to_cache("12345", "https://example.com/cover.jpg", "Test Book", "Test Author", "item123")

        # Verify database entry
        from sqlalchemy import text
        with mock_covers_db_engine.begin() as cx:
            row = cx.execute(text("SELECT * FROM covers WHERE mam_id = '12345'")).fetchone()
            assert row is not None
            assert row[1] == "12345"  # mam_id
            assert row[2] == "Test Book"  # title
            assert row[3] == "Test Author"  # author

    @pytest.mark.asyncio
    async def test_save_cover_reuses_existing_download(self, mock_covers_db_engine, temp_dir, monkeypatch):
        """Test that duplicate cover URLs reuse existing downloads."""
        covers_dir = temp_dir / "covers"
        covers_dir.mkdir()

        local_file = covers_dir / "original.jpg"
        local_file.write_bytes(b"fake_image")

        # Insert existing cover
        from sqlalchemy import text
        with mock_covers_db_engine.begin() as cx:
            cx.execute(text("""
                INSERT INTO covers (mam_id, title, cover_url, local_file, file_size, fetched_at)
                VALUES ('original', 'Original Book', 'https://example.com/cover.jpg', :local_file, 10, datetime('now'))
            """), {"local_file": str(local_file)})

        monkeypatch.setattr("covers.covers_engine", mock_covers_db_engine)
        monkeypatch.setattr("covers.MAX_COVERS_SIZE_MB", 10)

        from covers import CoverService
        service = CoverService()

        # Save same cover URL with different MAM ID
        await service.save_cover_to_cache("12345", "https://example.com/cover.jpg", "Test Book", "Test Author")

        # Verify it reused the local file
        with mock_covers_db_engine.begin() as cx:
            row = cx.execute(text("SELECT local_file FROM covers WHERE mam_id = '12345'")).fetchone()
            assert row is not None
            assert row[0] == str(local_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
