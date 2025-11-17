"""
Tests for multi-book import functionality.

Tests cover importing multiple books from a single torrent, per-book verification,
database integrity, disc flattening within multi-book torrents, and edge cases.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from sqlalchemy import create_engine, text
import sys
import json

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from routes.import_route import insert_torrent_book, BookPayload, MultiBookImportBody


class TestInsertTorrentBook:
    """Test the insert_torrent_book() database helper function."""

    @pytest.fixture
    def mock_engine(self):
        """Create an in-memory database with torrent_books table."""
        engine = create_engine("sqlite:///:memory:")

        # Create history table (referenced by foreign key)
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE history (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    author TEXT
                )
            """))
            conn.execute(text("INSERT INTO history (id, title, author) VALUES (1, 'Test Book', 'Test Author')"))

        # Create torrent_books table
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE torrent_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    torrent_hash TEXT NOT NULL,
                    history_id INTEGER NOT NULL,
                    position INTEGER,
                    subdirectory TEXT,
                    book_title TEXT,
                    book_author TEXT,
                    series_name TEXT,
                    imported_at TEXT DEFAULT (datetime('now')),
                    abs_item_id TEXT,
                    abs_verify_status TEXT,
                    abs_verify_note TEXT,
                    FOREIGN KEY(history_id) REFERENCES history(id) ON DELETE CASCADE
                )
            """))

        yield engine
        engine.dispose()

    def test_insert_torrent_book_basic(self, mock_engine):
        """Test inserting a basic torrent_books record."""
        # Patch the global engine
        with patch('routes.import_route.engine', mock_engine):
            torrent_book_id = insert_torrent_book(
                torrent_hash="abc123",
                history_id=1,
                book_title="Book One",
                book_author="Author One",
                position=1,
                subdirectory="Book 1",
                series_name="Test Series",
                abs_item_id="abs-item-123",
                abs_verify_status="verified",
                abs_verify_note="Match found",
            )

        # Verify the record was inserted
        assert torrent_book_id == 1

        with mock_engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM torrent_books WHERE id = 1")).fetchone()
            assert result is not None
            assert result[1] == "abc123"  # torrent_hash
            assert result[2] == 1  # history_id
            assert result[3] == 1  # position
            assert result[4] == "Book 1"  # subdirectory
            assert result[5] == "Book One"  # book_title
            assert result[6] == "Author One"  # book_author
            assert result[7] == "Test Series"  # series_name

    def test_insert_torrent_book_multiple_books(self, mock_engine):
        """Test inserting multiple books from same torrent."""
        with patch('routes.import_route.engine', mock_engine):
            id1 = insert_torrent_book(
                torrent_hash="abc123",
                history_id=1,
                book_title="Book One",
                book_author="Author One",
                position=1,
                subdirectory="Book 1",
                series_name="Test Series",
            )
            id2 = insert_torrent_book(
                torrent_hash="abc123",
                history_id=1,
                book_title="Book Two",
                book_author="Author One",
                position=2,
                subdirectory="Book 2",
                series_name="Test Series",
            )

        # Verify both records exist with same torrent_hash
        with mock_engine.begin() as conn:
            results = conn.execute(
                text("SELECT * FROM torrent_books WHERE torrent_hash = 'abc123' ORDER BY position")
            ).fetchall()
            assert len(results) == 2
            assert results[0][5] == "Book One"
            assert results[1][5] == "Book Two"

    def test_insert_torrent_book_nullable_fields(self, mock_engine):
        """Test inserting record with nullable fields as None."""
        with patch('routes.import_route.engine', mock_engine):
            torrent_book_id = insert_torrent_book(
                torrent_hash="abc123",
                history_id=1,
                book_title="Book One",
                book_author="Author One",
                position=None,  # nullable
                subdirectory="Book 1",
                series_name=None,  # nullable
            )

        # Verify the record was inserted with NULL values
        with mock_engine.begin() as conn:
            result = conn.execute(text("SELECT position, series_name FROM torrent_books WHERE id = :id"), {"id": torrent_book_id}).fetchone()
            assert result[0] is None  # position
            assert result[1] is None  # series_name


class TestMultiBookImportEndpoint:
    """Test the /import/multi-book endpoint."""

    @pytest.fixture
    def temp_torrent_structure(self, tmp_path):
        """Create a mock multi-book torrent directory structure."""
        torrent_root = tmp_path / "Test Series Complete"

        # Book 1 with multi-disc structure
        book1_dir = torrent_root / "Book 1 - First Title"
        (book1_dir / "Disc 1").mkdir(parents=True)
        (book1_dir / "Disc 2").mkdir(parents=True)
        (book1_dir / "Disc 1" / "Track 01.mp3").write_text("audio1")
        (book1_dir / "Disc 1" / "Track 02.mp3").write_text("audio2")
        (book1_dir / "Disc 2" / "Track 01.mp3").write_text("audio3")

        # Book 2 without discs
        book2_dir = torrent_root / "Book 2 - Second Title"
        book2_dir.mkdir(parents=True)
        (book2_dir / "Chapter 01.mp3").write_text("audio1")
        (book2_dir / "Chapter 02.mp3").write_text("audio2")

        return {
            "root": torrent_root,
            "book1_dir": book1_dir,
            "book2_dir": book2_dir,
        }

    @pytest.fixture
    def mock_qb_response(self):
        """Create mock qBittorrent API responses."""
        return {
            "info": [{
                "hash": "abc123",
                "name": "Test Series Complete",
                "content_path": "/downloads/Test Series Complete",
                "save_path": "/downloads",
            }]
        }

    @pytest.fixture
    def mock_httpx_context_manager(self, mock_qb_response):
        """Create properly configured httpx.Client context manager mock."""
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value.status_code = 200
        mock_client_instance.get.return_value.json.return_value = mock_qb_response["info"]
        mock_client_instance.post.return_value.status_code = 200

        mock_client = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_client_instance
        mock_client.return_value.__exit__.return_value = None

        return mock_client

    @pytest.mark.asyncio
    async def test_multi_book_import_two_books(self, temp_torrent_structure, mock_httpx_context_manager, tmp_path):
        """Test importing two books from a single torrent."""
        # Setup
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()

        # Create mock database
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE history (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    qb_status TEXT,
                    imported_at TEXT
                )
            """))
            conn.execute(text("INSERT INTO history (id, title) VALUES (1, 'Test Series')"))

            conn.execute(text("""
                CREATE TABLE torrent_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    torrent_hash TEXT NOT NULL,
                    history_id INTEGER NOT NULL,
                    position INTEGER,
                    subdirectory TEXT,
                    book_title TEXT,
                    book_author TEXT,
                    series_name TEXT,
                    imported_at TEXT DEFAULT (datetime('now')),
                    abs_item_id TEXT,
                    abs_verify_status TEXT,
                    abs_verify_note TEXT
                )
            """))

        # Mock ABS client
        mock_abs_verify = AsyncMock(return_value={
            "status": "verified",
            "note": "Match found",
            "abs_item_id": "abs-123",
        })

        # Prepare request body
        body = MultiBookImportBody(
            torrent_hash="abc123",
            history_id=1,
            books=[
                BookPayload(
                    title="First Title",
                    author="Test Author",
                    subdirectory="Book 1 - First Title",
                    position=1,
                    series_name="Test Series",
                ),
                BookPayload(
                    title="Second Title",
                    author="Test Author",
                    subdirectory="Book 2 - Second Title",
                    position=2,
                    series_name="Test Series",
                ),
            ],
            flatten=True,
        )

        # Patch all dependencies
        with patch('routes.import_route.httpx.Client', mock_httpx_context_manager), \
             patch('routes.import_route.qb_login_sync'), \
             patch('routes.import_route.engine', engine), \
             patch('routes.import_route.abs_client.verify_import', mock_abs_verify), \
             patch('routes.import_route.read_metadata_json', return_value={}), \
             patch('routes.import_route.LIB_DIR', str(lib_dir)), \
             patch('routes.import_route.DL_DIR', str(temp_torrent_structure["root"].parent)), \
             patch('routes.import_route.QB_INNER_DL_PREFIX', "/downloads"):

            from routes.import_route import do_multi_book_import

            # Execute
            result = await do_multi_book_import(body)

            # Assert
            assert result["ok"] is True
            assert result["books_processed"] == 2
            assert result["books_succeeded"] == 2
            assert result["books_failed"] == 0
            assert len(result["results"]) == 2

            # Verify individual book results
            book1_result = result["results"][0]
            assert book1_result["ok"] is True
            assert book1_result["book_title"] == "First Title"
            assert book1_result["files_copied"] > 0

            book2_result = result["results"][1]
            assert book2_result["ok"] is True
            assert book2_result["book_title"] == "Second Title"

    @pytest.mark.asyncio
    async def test_multi_book_import_disc_flattening(self, temp_torrent_structure, tmp_path):
        """Test that disc flattening works correctly within each book."""
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()

        # Create mock database
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE history (id INTEGER PRIMARY KEY, title TEXT, qb_status TEXT, imported_at TEXT)
            """))
            conn.execute(text("INSERT INTO history (id, title) VALUES (1, 'Test')"))
            conn.execute(text("""
                CREATE TABLE torrent_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    torrent_hash TEXT, history_id INTEGER, position INTEGER,
                    subdirectory TEXT, book_title TEXT, book_author TEXT,
                    series_name TEXT, imported_at TEXT, abs_item_id TEXT,
                    abs_verify_status TEXT, abs_verify_note TEXT
                )
            """))

        # Create properly mocked httpx client for this test
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value.status_code = 200
        mock_client_instance.get.return_value.json.return_value = [{
            "content_path": str(temp_torrent_structure["root"])
        }]

        mock_httpx_client = MagicMock()
        mock_httpx_client.return_value.__enter__.return_value = mock_client_instance
        mock_httpx_client.return_value.__exit__.return_value = None

        body = MultiBookImportBody(
            torrent_hash="abc123",
            history_id=1,
            books=[
                BookPayload(
                    title="First Title",
                    author="Test Author",
                    subdirectory="Book 1 - First Title",
                    position=1,
                ),
            ],
            flatten=True,
        )

        with patch('routes.import_route.httpx.Client', mock_httpx_client), \
             patch('routes.import_route.qb_login_sync'), \
             patch('routes.import_route.engine', engine), \
             patch('routes.import_route.abs_client.verify_import', AsyncMock(return_value={"status": "verified", "note": "Match"})), \
             patch('routes.import_route.read_metadata_json', return_value={}), \
             patch('routes.import_route.LIB_DIR', str(lib_dir)), \
             patch('routes.import_route.QB_INNER_DL_PREFIX', "/downloads"):

            from routes.import_route import do_multi_book_import

            result = await do_multi_book_import(body)

            # Verify flattening occurred
            assert result["ok"] is True
            assert result["flatten_applied"] is True

            # Check that files were flattened in destination
            book1_result = result["results"][0]
            dest_path = Path(book1_result["dest"])
            if dest_path.exists():
                audio_files = sorted(dest_path.glob("Part *.mp3"))
                assert len(audio_files) == 3  # 3 files from 2 discs
                assert audio_files[0].name == "Part 001.mp3"
                assert audio_files[1].name == "Part 002.mp3"
                assert audio_files[2].name == "Part 003.mp3"

    @pytest.mark.asyncio
    async def test_multi_book_import_subdirectory_not_found(self, temp_torrent_structure, tmp_path):
        """Test handling of missing subdirectory in multi-book import."""
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()

        # Create mock database
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE history (id INTEGER PRIMARY KEY, title TEXT, qb_status TEXT, imported_at TEXT)"))
            conn.execute(text("INSERT INTO history (id, title) VALUES (1, 'Test')"))
            conn.execute(text("""
                CREATE TABLE torrent_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    torrent_hash TEXT, history_id INTEGER, position INTEGER,
                    subdirectory TEXT, book_title TEXT, book_author TEXT,
                    series_name TEXT, imported_at TEXT, abs_item_id TEXT,
                    abs_verify_status TEXT, abs_verify_note TEXT
                )
            """))

        mock_httpx_client = MagicMock()
        mock_httpx_client.get.return_value.status_code = 200
        mock_httpx_client.get.return_value.json.return_value = [{
            "content_path": str(temp_torrent_structure["root"])
        }]

        body = MultiBookImportBody(
            torrent_hash="abc123",
            history_id=1,
            books=[
                BookPayload(
                    title="NonExistent Book",
                    author="Test Author",
                    subdirectory="Book 99 - Does Not Exist",  # This directory doesn't exist
                    position=1,
                ),
            ],
            flatten=True,
        )

        with patch('routes.import_route.httpx.Client', mock_httpx_client), \
             patch('routes.import_route.qb_login_sync'), \
             patch('routes.import_route.engine', engine), \
             patch('routes.import_route.LIB_DIR', str(lib_dir)), \
             patch('routes.import_route.QB_INNER_DL_PREFIX', "/downloads"):

            from routes.import_route import do_multi_book_import

            result = await do_multi_book_import(body)

            # Should not raise exception, but report error in results
            assert result["ok"] is True
            assert result["books_processed"] == 1
            assert result["books_failed"] == 1
            assert result["results"][0]["ok"] is False
            assert "not found" in result["results"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_multi_book_import_partial_verification(self, temp_torrent_structure, tmp_path):
        """Test multi-book import where one book verifies and one mismatches."""
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()

        # Create mock database
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE history (id INTEGER PRIMARY KEY, title TEXT, qb_status TEXT, imported_at TEXT)"))
            conn.execute(text("INSERT INTO history (id, title) VALUES (1, 'Test')"))
            conn.execute(text("""
                CREATE TABLE torrent_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    torrent_hash TEXT, history_id INTEGER, position INTEGER,
                    subdirectory TEXT, book_title TEXT, book_author TEXT,
                    series_name TEXT, imported_at TEXT, abs_item_id TEXT,
                    abs_verify_status TEXT, abs_verify_note TEXT
                )
            """))

        mock_httpx_client = MagicMock()
        mock_httpx_client.get.return_value.status_code = 200
        mock_httpx_client.get.return_value.json.return_value = [{
            "content_path": str(temp_torrent_structure["root"])
        }]

        # Mock ABS verification with different results per book
        verify_calls = [
            {"status": "verified", "note": "Match found", "abs_item_id": "abs-1"},
            {"status": "mismatch", "note": "Different author", "abs_item_id": "abs-2"},
        ]
        mock_abs_verify = AsyncMock(side_effect=verify_calls)

        body = MultiBookImportBody(
            torrent_hash="abc123",
            history_id=1,
            books=[
                BookPayload(title="First Title", author="Test Author", subdirectory="Book 1 - First Title", position=1),
                BookPayload(title="Second Title", author="Test Author", subdirectory="Book 2 - Second Title", position=2),
            ],
            flatten=True,
        )

        with patch('routes.import_route.httpx.Client', mock_httpx_client), \
             patch('routes.import_route.qb_login_sync'), \
             patch('routes.import_route.engine', engine), \
             patch('routes.import_route.abs_client.verify_import', mock_abs_verify), \
             patch('routes.import_route.read_metadata_json', return_value={}), \
             patch('routes.import_route.LIB_DIR', str(lib_dir)), \
             patch('routes.import_route.QB_INNER_DL_PREFIX', "/downloads"):

            from routes.import_route import do_multi_book_import

            result = await do_multi_book_import(body)

            # Both books should import successfully despite different verification statuses
            assert result["ok"] is True
            assert result["books_succeeded"] == 2
            assert result["results"][0]["verification"]["status"] == "verified"
            assert result["results"][1]["verification"]["status"] == "mismatch"

    @pytest.mark.asyncio
    async def test_multi_book_import_database_integrity(self, temp_torrent_structure, tmp_path):
        """Test that torrent_books database records are created correctly."""
        lib_dir = tmp_path / "library"
        lib_dir.mkdir()

        # Create mock database
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE history (id INTEGER PRIMARY KEY, title TEXT, qb_status TEXT, imported_at TEXT)"))
            conn.execute(text("INSERT INTO history (id, title) VALUES (1, 'Test Series')"))
            conn.execute(text("""
                CREATE TABLE torrent_books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    torrent_hash TEXT, history_id INTEGER, position INTEGER,
                    subdirectory TEXT, book_title TEXT, book_author TEXT,
                    series_name TEXT, imported_at TEXT, abs_item_id TEXT,
                    abs_verify_status TEXT, abs_verify_note TEXT
                )
            """))

        mock_httpx_client = MagicMock()
        mock_httpx_client.get.return_value.status_code = 200
        mock_httpx_client.get.return_value.json.return_value = [{
            "content_path": str(temp_torrent_structure["root"])
        }]

        body = MultiBookImportBody(
            torrent_hash="abc123",
            history_id=1,
            books=[
                BookPayload(title="First Title", author="Test Author", subdirectory="Book 1 - First Title", position=1, series_name="Test Series"),
                BookPayload(title="Second Title", author="Test Author", subdirectory="Book 2 - Second Title", position=2, series_name="Test Series"),
            ],
            flatten=True,
        )

        with patch('routes.import_route.httpx.Client', mock_httpx_client), \
             patch('routes.import_route.qb_login_sync'), \
             patch('routes.import_route.engine', engine), \
             patch('routes.import_route.abs_client.verify_import', AsyncMock(return_value={"status": "verified", "note": "Match", "abs_item_id": "abs-123"})), \
             patch('routes.import_route.read_metadata_json', return_value={}), \
             patch('routes.import_route.LIB_DIR', str(lib_dir)), \
             patch('routes.import_route.QB_INNER_DL_PREFIX', "/downloads"):

            from routes.import_route import do_multi_book_import

            result = await do_multi_book_import(body)

            # Verify database records
            with engine.begin() as conn:
                records = conn.execute(text("SELECT * FROM torrent_books ORDER BY position")).fetchall()
                assert len(records) == 2

                # Check first book record
                assert records[0][1] == "abc123"  # torrent_hash
                assert records[0][2] == 1  # history_id
                assert records[0][3] == 1  # position
                assert records[0][4] == "Book 1 - First Title"  # subdirectory
                assert records[0][5] == "First Title"  # book_title
                assert records[0][7] == "Test Series"  # series_name

                # Check second book record
                assert records[1][3] == 2  # position
                assert records[1][5] == "Second Title"  # book_title
