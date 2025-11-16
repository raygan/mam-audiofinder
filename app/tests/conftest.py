"""
Pytest configuration and shared fixtures for MAM Audiobook Finder tests.

This module provides common test fixtures and configuration for all test modules.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock
import pytest
from sqlalchemy import create_engine, text

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine("sqlite:///:memory:")

    # Create history table schema
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE history (
                id INTEGER PRIMARY KEY,
                mam_id TEXT,
                title TEXT,
                author TEXT,
                narrator TEXT,
                dl TEXT,
                added_at TEXT DEFAULT (datetime('now')),
                qb_status TEXT,
                qb_hash TEXT,
                imported_at TEXT,
                abs_item_id TEXT,
                abs_cover_url TEXT,
                abs_cover_cached_at TEXT,
                abs_verify_status TEXT,
                abs_verify_note TEXT
            )
        """))

    yield engine
    engine.dispose()


@pytest.fixture
def mock_covers_db_engine():
    """Create an in-memory SQLite database engine for covers testing."""
    engine = create_engine("sqlite:///:memory:")

    # Create covers table schema
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE covers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mam_id TEXT UNIQUE NOT NULL,
                title TEXT,
                author TEXT,
                cover_url TEXT NOT NULL,
                abs_item_id TEXT,
                local_file TEXT,
                file_size INTEGER,
                fetched_at TEXT DEFAULT (datetime('now'))
            )
        """))

    yield engine
    engine.dispose()


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient for testing HTTP requests."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_config():
    """Provide mock configuration values for testing."""
    return {
        'MAM_COOKIE': 'mam_id=test123; session=abc456',
        'QB_URL': 'http://test-qbittorrent:8080',
        'QB_USER': 'admin',
        'QB_PASS': 'testpass',
        'DL_DIR': '/media/torrents',
        'LIB_DIR': '/media/Books/Audiobooks',
        'IMPORT_MODE': 'link',
        'FLATTEN_DISCS': True,
        'QB_CATEGORY': 'mam-audiofinder',
        'QB_POSTIMPORT_CATEGORY': '',
        'ABS_URL': 'http://test-abs:13378',
        'ABS_TOKEN': 'test-token-123',
        'ABS_VERIFY_TIMEOUT': 10,
        'COVERS_DIR': '/data/covers',
        'MAX_COVERS_SIZE_MB': 500,
    }


@pytest.fixture
def sample_mam_search_result():
    """Provide a sample MAM search result for testing."""
    return {
        'data': [
            {
                'id': '12345',
                'title': 'The Hobbit',
                'author_info': {
                    'author': 'J.R.R. Tolkien',
                    'narrator': 'Rob Inglis'
                },
                'torrent': {
                    'download_link': 'https://mam/download/12345'
                },
                'size': '536870912',  # 512 MB
                'seeders': 10,
                'leechers': 2,
                'format': 'M4B'
            },
            {
                'id': '67890',
                'title': 'The Fellowship of the Ring',
                'author_info': {
                    'author': 'J.R.R. Tolkien',
                    'narrator': 'Rob Inglis'
                },
                'torrent': {
                    'download_link': 'https://mam/download/67890'
                },
                'size': '1073741824',  # 1 GB
                'seeders': 15,
                'leechers': 3,
                'format': 'MP3'
            }
        ]
    }


@pytest.fixture
def sample_abs_cover_response():
    """Provide a sample Audiobookshelf cover fetch response."""
    return {
        'results': [
            {
                'title': 'The Hobbit',
                'author': 'J.R.R. Tolkien',
                'cover': 'https://abs-server/api/items/item123/cover',
                'id': 'item123'
            }
        ]
    }


@pytest.fixture
def sample_abs_library_items():
    """Provide a sample Audiobookshelf library items response."""
    return {
        'results': [
            {
                'id': 'lib-item-1',
                'media': {
                    'metadata': {
                        'title': 'The Hobbit',
                        'authorName': 'J.R.R. Tolkien',
                        'narratorName': 'Rob Inglis'
                    }
                },
                'path': '/audiobooks/Tolkien, J.R.R/The Hobbit'
            },
            {
                'id': 'lib-item-2',
                'media': {
                    'metadata': {
                        'title': 'The Fellowship of the Ring',
                        'authorName': 'J.R.R. Tolkien',
                        'narratorName': 'Rob Inglis'
                    }
                },
                'path': '/audiobooks/Tolkien, J.R.R/The Fellowship of the Ring'
            }
        ],
        'total': 2
    }


@pytest.fixture
def sample_qb_torrent_info():
    """Provide a sample qBittorrent torrent info response."""
    return {
        'hash': 'abc123def456',
        'name': 'The Hobbit',
        'state': 'pausedUP',
        'progress': 1.0,
        'dlspeed': 0,
        'upspeed': 1024,
        'downloaded': 536870912,
        'uploaded': 1073741824,
        'size': 536870912,
        'save_path': '/downloads/The Hobbit',
        'content_path': '/downloads/The Hobbit',
        'category': 'mam-audiofinder',
        'tags': 'mam-12345'
    }


@pytest.fixture
def sample_file_tree():
    """Provide a sample multi-disc file tree structure."""
    return {
        'Disc 01': [
            'Track 01.mp3',
            'Track 02.mp3',
            'Track 03.mp3'
        ],
        'Disc 02': [
            'Track 01.mp3',
            'Track 02.mp3'
        ],
        'cover.jpg': None
    }


@pytest.fixture
def mock_abs_client():
    """Create a mock AudiobookshelfClient for testing."""
    client = Mock()
    client.test_connection = Mock(return_value=(True, "Connection successful"))
    client.fetch_cover = Mock(return_value=None)
    client.verify_import = Mock(return_value={
        'status': 'verified',
        'note': 'Found in library',
        'abs_item_id': 'item123'
    })
    return client


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment variables before each test."""
    # Store original env
    original_env = os.environ.copy()

    yield

    # Restore original env after test
    os.environ.clear()
    os.environ.update(original_env)
