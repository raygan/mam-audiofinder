# Backend Architecture

## Overview

MAM Audiobook Finder backend is built with:
- **FastAPI** - Async web framework
- **SQLite** - Two databases (history.db, covers.db)
- **httpx** - Async HTTP client for external APIs
- **Uvicorn** - ASGI server
- **Docker** - Containerized deployment

## Database Schemas

### history.db

Primary database tracking all searched and imported audiobooks.

```sql
CREATE TABLE history (
  id INTEGER PRIMARY KEY,
  mam_id TEXT,
  title TEXT,
  author TEXT,
  narrator TEXT,
  dl TEXT,
  added_at TEXT DEFAULT (datetime('now')),

  -- qBittorrent tracking
  qb_status TEXT,
  qb_hash TEXT,

  -- Import tracking
  imported_at TEXT,

  -- Audiobookshelf integration (Migration 004)
  abs_item_id TEXT,
  abs_cover_url TEXT,
  abs_cover_cached_at TEXT,

  -- Verification system (Migration 006)
  abs_verify_status TEXT,  -- 'verified', 'mismatch', 'not_found', 'unreachable', 'not_configured'
  abs_verify_note TEXT,    -- Diagnostic messages

  -- Descriptions (Migration 007)
  abs_description TEXT,
  abs_metadata TEXT,       -- JSON blob with full ABS metadata
  abs_description_source TEXT
);
```

**Migration History:**
- 001: Initial schema
- 002-003: Early additions
- 004: ABS integration columns
- 006: Verification columns
- 007: Description columns

### covers.db

Separate database for cover image caching and metadata.

```sql
CREATE TABLE covers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mam_id TEXT UNIQUE NOT NULL,
  title TEXT,
  author TEXT,
  cover_url TEXT NOT NULL,
  abs_item_id TEXT,
  local_file TEXT,
  file_size INTEGER,
  fetched_at TEXT DEFAULT (datetime('now')),

  -- Metadata integration (Migration 008)
  abs_description TEXT,
  abs_metadata TEXT,
  abs_metadata_fetched_at TEXT
);

CREATE INDEX idx_covers_mam_id ON covers(mam_id);
CREATE INDEX idx_covers_cover_url ON covers(cover_url);
```

**Migration History:**
- 005: Initial covers schema
- 008: Description and metadata columns

## Core Modules

### abs_client.py (~850 lines)

Audiobookshelf API client with comprehensive integration features.

**Key Methods:**

**`verify_import(title, author, library_path) -> dict`**
- Verifies imported audiobook appears in ABS library
- Implements retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)
- Scoring algorithm for fuzzy matching:
  - **ASIN match:** 200 points (highest priority)
  - **ISBN match:** 200 points (highest priority)
  - **Title exact match:** 100 points
  - **Title partial match:** 50 points
  - **Author exact match:** 50 points
  - **Author partial match:** 25 points
  - **Path matching bonus:** 25 points
- Thresholds: ≥100 = verified, 50-99 = mismatch, <50 = not_found
- Returns: `{"status": "verified|mismatch|not_found|unreachable", "note": "...", "abs_item_id": "..."}`

**`check_library_items(items: list) -> dict`**
- Batch checks if audiobooks exist in ABS library
- Accepts list of (title, author) tuples
- Returns dict mapping to boolean (in library or not)
- Uses in-memory caching with TTL (default 300s)
- Supports fuzzy matching similar to verification

**`fetch_item_details(item_id: str) -> dict`**
- Fetches full metadata from `/api/items/{id}?expanded=1`
- Extracts 20+ metadata fields (title, authors, narrators, series, genres, ASIN, ISBN, etc.)
- In-memory caching with TTL (300s default)
- Returns description + metadata object

**`_update_description_after_verification(abs_item_id, title, author)`**
- Automatically triggered when verification succeeds (score ≥100)
- Updates both covers.db and history.db with description/metadata
- Non-blocking: verification succeeds even if fetch fails
- Smart matching: updates by abs_item_id OR title/author combination

**Performance Features:**
- Connection pooling: Shared httpx.AsyncClient (max 50 connections)
- Request limiting: Semaphore limits concurrent ABS requests to 10
- Three cache layers: library (5min), metadata (5min), verification (in-flight)

### covers.py (~350 lines)

Cover image caching service with automatic management.

**CoverService Features:**
- Separate covers.db SQLite database
- Local storage in `/data/covers/`
- Connection pooling for concurrent fetches
- Deduplication by cover URL
- Auto-cleanup when exceeding MAX_COVERS_SIZE_MB
- Auto-healing for missing files
- Direct fetch mode (MAX_COVERS_SIZE_MB=0)

**Cache Management:**
- **Cleanup trigger:** Directory size exceeds MAX_COVERS_SIZE_MB
- **Strategy:** Delete oldest files first (by access time)
- **Auto-healing:** Detects missing local files in database, re-downloads from source

**Storage Pattern:**
- Filename: `{mam_id}_{hash}.jpg`
- Database tracks: local_file, file_size, fetched_at
- Concurrent fetch safety: File locks and deduplication

### torrent_helpers.py (~220 lines)

qBittorrent integration utilities.

**Key Functions:**

**`map_qb_state_to_display(state: str) -> str`**
- Maps qBittorrent internal states to user-friendly text
- Examples: "downloading" → "Downloading", "stalledDL" → "Stalled"

**`get_torrent_state(qb_client, torrent_hash) -> dict`**
- Fetches live torrent information from qBittorrent
- Returns: name, state, progress, size, save_path, category, tags

**`validate_torrent_path(torrent_path, expected_dl_dir) -> bool`**
- Validates torrent save path aligns with expected download directory
- Critical for path mapping between containers

**`extract_mam_id_from_tags(tags: str) -> str`**
- Extracts MAM ID from torrent tags
- Format: "mam-12345" → "12345"

**`match_torrent_to_history(torrents, history_items) -> dict`**
- Fuzzy matching of torrents to history entries
- Matching strategies: hash, mam_id from tags, title similarity

### utils.py (~110 lines)

General utility functions.

**Key Functions:**
- `sanitize(name)` - Sanitize filenames for filesystem safety
- `next_available(base_path)` - Find next available filename (base.mp3, base (2).mp3, etc.)
- `extract_disc_track(filename)` - Parse disc/track numbers from multi-disc audiobooks
- `try_hardlink(src, dst)` - Attempt hardlink, fall back to copy on error

## Import Workflow

Detailed flow when user clicks "Import" button:

```
1. User submits import form
   ├── Selected torrent hash
   ├── Destination path
   └── Flatten discs option

2. Backend validates request
   ├── Check torrent exists in qBittorrent
   ├── Validate source path exists
   └── Validate destination is within LIB_DIR

3. Analyze torrent file structure
   ├── Fetch file tree from qBittorrent
   ├── Detect multi-disc structure (Disc/Disk/CD/Part patterns)
   └── Filter audio files only (AUDIO_EXTS)

4. Copy/Link/Move files
   ├── If FLATTEN_DISCS enabled:
   │   ├── Extract disc/track numbers
   │   ├── Sort files across all discs
   │   └── Rename sequentially (Part 001.mp3, Part 002.mp3, ...)
   └── Otherwise: Preserve directory structure

5. Wait for ABS metadata.json
   ├── Poll destination directory (up to 6 attempts, 5s intervals)
   ├── Look for metadata.json created by ABS scanner
   └── Parse ASIN/ISBN for enhanced verification

6. Verify import (if ABS configured)
   ├── Call abs_client.verify_import()
   ├── Retry up to 3 times with exponential backoff
   ├── Score match based on ASIN/ISBN/title/author
   └── Store verification status in database

7. Fetch description (if verification succeeded)
   ├── Call abs_client._update_description_after_verification()
   ├── Fetch from /api/items/{id}?expanded=1
   ├── Update both covers.db and history.db
   └── Non-blocking: continues even if fetch fails

8. Update qBittorrent category (if configured)
   ├── Change category to QB_POSTIMPORT_CATEGORY
   └── Best-effort: doesn't fail import on error

9. Return success response
   └── Frontend updates UI with verification status
```

## Verification System Deep Dive

### Scoring Algorithm

The verification system uses a point-based scoring algorithm to fuzzy match imported audiobooks against the ABS library.

**Priority 1: Identifier Matching (200 points each)**
- ASIN match (exact)
- ISBN match (exact)

**Priority 2: Title Matching**
- Exact match: 100 points
- Partial match: 50 points
  - Normalized comparison (lowercase, no punctuation)
  - Substring matching in either direction

**Priority 3: Author Matching**
- Exact match: 50 points
- Partial match: 25 points
  - Case-insensitive comparison
  - Substring matching

**Priority 4: Path Bonus**
- Path contains expected library directory: +25 points

**Thresholds:**
- **≥100 points:** Status = `verified` (high confidence match)
- **50-99 points:** Status = `mismatch` (possible match, needs review)
- **<50 points:** Status = `not_found` (no match found)

**Special Statuses:**
- `unreachable`: ABS API not responding
- `not_configured`: ABS_BASE_URL or ABS_API_KEY not set

### Retry Logic

- **Attempts:** 3 total (initial + 2 retries)
- **Backoff:** Exponential (1s, 2s, 4s)
- **Timeout:** ABS_VERIFY_TIMEOUT per request (default 30s)
- **Conditions:** Retry on network errors, not on 404/validation failures

### When Verification Runs

**Automatically:**
- After successful import (triggered in import_route.py)

**Manually:**
- User clicks "🔄 Verify" button in history view
- API endpoint: POST `/api/history/{id}/verify`

**Not Triggered:**
- During search (no import occurred)
- When ABS not configured
- When verification previously succeeded (manual refresh only)

## Cover Caching System

### Storage Strategy

**Directory:** `/data/covers/` (inside container)

**Filename Pattern:** `{mam_id}_{hash}.jpg`
- Example: `12345_a1b2c3d4.jpg`
- Hash prevents collisions for same mam_id with different covers

**Database Tracking:**
- Record per cover with: mam_id, cover_url, local_file, file_size, fetched_at
- Indexes on mam_id and cover_url for fast lookups

### Fetch Workflow

```
1. Check covers.db for existing cache entry
   ├── If found and local_file exists: Return local path
   └── If found but local_file missing: Auto-heal (re-download)

2. Search Audiobookshelf library for title/author
   ├── If found in library:
   │   ├── Get cover URL from ABS metadata
   │   ├── Fetch description (if available)
   │   └── Store abs_item_id for future use
   └── If not found: Return MAM cover URL (external link)

3. Download cover to local storage
   ├── Create /data/covers/ if doesn't exist
   ├── Generate filename: {mam_id}_{hash}.jpg
   └── Save file with proper permissions (UMASK)

4. Save cache entry to covers.db
   ├── Store: mam_id, title, author, cover_url, abs_item_id
   ├── Store: local_file, file_size, fetched_at
   └── Store: abs_description, abs_metadata (if available)

5. Check if cleanup needed
   └── If directory size > MAX_COVERS_SIZE_MB: Trigger cleanup
```

### Auto-Cleanup

**Trigger:** Directory size exceeds MAX_COVERS_SIZE_MB

**Algorithm:**
1. Scan /data/covers/ directory
2. Get file sizes and access times
3. Sort by access time (oldest first)
4. Delete files until size drops below limit
5. Update database to remove deleted entries

**Safety:**
- Only deletes files tracked in database
- Preserves recently accessed covers
- Runs asynchronously (doesn't block requests)

### Auto-Healing

**Problem:** Database has cache entry but file is missing (manual deletion, corruption, etc.)

**Detection:** When serving cover, check if local_file exists

**Recovery:**
1. Re-download from original cover_url
2. Save to same local_file path
3. Update database with new file_size and fetched_at
4. Return healed cover

**Fallback:** If re-download fails, return external cover URL

### Direct Fetch Mode

**Configuration:** `MAX_COVERS_SIZE_MB=0`

**Behavior:**
- Skips local caching entirely
- Always returns external cover URLs
- Reduces disk usage but increases latency
- Not recommended for production use

## API Endpoints

### Search & Discovery

**POST /search**
- Searches MAM API for audiobooks
- Payload: title, author, narrator, category, format, freelech, limit
- Response: Array of search results with covers and library indicators
- Caching: 5 minutes (prevents duplicate MAM calls)

**GET /api/showcase**
- Grouped search results by normalized title
- Grouping logic: Removes articles (The, A, An), strips punctuation, lowercase
- Returns: groups with display_title, versions, cover, library status
- Use case: Browse by title with multiple editions/formats

### qBittorrent Integration

**POST /add**
- Adds torrent to qBittorrent
- Workflow: Fetch .torrent from MAM → Add to qBittorrent → Tag with mam_id → Save to DB
- Response: qBittorrent hash, save path, category

**GET /qb/torrents**
- Lists all torrents with live state from qBittorrent
- Filters: By category, by hash
- Response: Array of torrents with progress, state, size

**GET /qb/torrent/{hash}/tree**
- Returns file tree for specific torrent
- Detects multi-disc structure
- Response: File tree + multi_disc_detected boolean

### Import & Verification

**POST /import**
- Imports completed torrent into Audiobookshelf library
- Payload: torrent_hash, destination, flatten (optional)
- Workflow: Copy/link/move → Wait for metadata → Verify → Fetch description
- Response: Success + verification status

**POST /api/history/{id}/verify**
- Manually re-verifies an imported item
- Triggers full verification + description fetch
- Response: Updated verification status

### History & Logs

**GET /api/history**
- Returns all history entries with live torrent states
- Enriched with: qB progress, ABS verification status, covers
- Sorting: Most recent first

**DELETE /api/history/{id}**
- Removes history entry from database
- Does not delete files or torrents

**GET /api/logs**
- Returns application logs (last N lines)
- Supports filtering by log level
- Response: Array of log entries with timestamp, level, message

### Covers

**GET /covers/{filename}**
- Serves locally cached cover images
- Static file serving with proper MIME types
- Falls back to external URL if file missing

## Performance Optimizations

### Caching Layers

**MAM Search Cache:**
- Duration: 5 minutes
- Key: Full search payload (title, author, limit, etc.)
- Storage: In-memory dict with expiry timestamps
- Benefit: Prevents duplicate MAM API calls (e.g., browser refresh, back button)

**ABS Library Cache:**
- Duration: 300 seconds (configurable via ABS_LIBRARY_CACHE_TTL)
- Key: "library_items"
- Storage: In-memory dict in abs_client.py
- Benefit: Batch library checks for search results without repeated API calls

**ABS Metadata Cache:**
- Duration: 300 seconds
- Key: abs_item_id
- Storage: In-memory dict in abs_client.py
- Benefit: Reuses fetched descriptions across pages

**Cover Cache:**
- Duration: Persistent on disk
- Storage: covers.db + /data/covers/
- Benefit: Eliminates repeated downloads, faster page loads

### Connection Pooling

**httpx.AsyncClient:**
- Shared client instance for all ABS requests
- Max connections: 50
- Connection reuse: HTTP/1.1 keep-alive
- Benefit: Reduces TCP handshake overhead

**Semaphore Limiting:**
- Max concurrent ABS requests: 10
- Prevents overwhelming ABS server
- Queues excess requests

**SQLite Connection Pooling:**
- Separate engines for history.db and covers.db
- Connection reuse across requests
- Thread-safe with proper locking

### Batch Operations

**Library Checking:**
- Single ABS API call fetches entire library (or filtered subset)
- Checks all search results against cached library
- Avoids N+1 query problem

**Cover Fetching:**
- Progressive loading in frontend (only visible covers)
- Backend handles concurrent requests efficiently
- Deduplication prevents fetching same cover twice

## Multi-Disc Flattening

### Problem

Multi-disc audiobooks often have structure like:
```
Book Title/
├── Disc 01/
│   ├── Track 01.mp3
│   ├── Track 02.mp3
├── Disc 02/
│   ├── Track 01.mp3
│   └── Track 02.mp3
```

Audiobookshelf may treat these as separate books or fail to order correctly.

### Solution

When `FLATTEN_DISCS=true` (default), the import process flattens to:
```
Book Title/
├── Part 001.mp3
├── Part 002.mp3
├── Part 003.mp3
└── Part 004.mp3
```

### Detection Algorithm

**Pattern Matching:**
- Detects folders named: Disc, Disk, CD, Part (case-insensitive)
- Detects numbering: 01, 1, I, II, etc.
- Threshold: At least 2 disc folders

**File Analysis:**
- Scans for audio files (AUDIO_EXTS: .mp3, .m4b, .m4a, .flac, .ogg, .opus, .wav)
- Extracts disc number and track number from path/filename
- Ignores non-audio files

### Extraction Logic

**`extract_disc_track(filename)` in utils.py:**
- Parses patterns: "Disc 01", "Part 2", "CD 03"
- Extracts track numbers from: "Track 01.mp3", "Chapter 12.m4b", "01 - Title.mp3"
- Returns: (disc_num, track_num) or (None, None)

### Renaming Algorithm

```python
1. Collect all audio files across all discs
2. For each file:
   ├── Extract disc number and track number
   └── Store with sort key: (disc_num, track_num)
3. Sort files by sort key (maintains disc order, then track order)
4. Rename sequentially:
   ├── Part 001.mp3
   ├── Part 002.mp3
   └── ... (preserve original extension)
5. Copy/link/move to destination
```

### Edge Cases

- **No disc pattern detected:** Preserves original structure
- **Mixed numbered/unnumbered files:** Best-effort sorting, warns in logs
- **Duplicate disc/track combinations:** Uses original filename as tiebreaker
- **Non-audio files:** Copied to root level (cover.jpg, metadata.json, etc.)

## Configuration

### Environment Variables

**Required:**
- `MAM_COOKIE` - MAM session cookie (mam_id=...)
- `QB_URL` - qBittorrent WebUI URL
- `QB_USER` - qBittorrent username
- `QB_PASS` - qBittorrent password
- `MEDIA_ROOT` - Host path for media (must be mounted to both containers)

**Optional - Audiobookshelf:**
- `ABS_BASE_URL` - Audiobookshelf URL (e.g., http://audiobookshelf:13378)
- `ABS_API_KEY` - ABS API token for authentication
- `ABS_LIBRARY_ID` - Specific library ID (optional, searches all if not set)
- `ABS_VERIFY_TIMEOUT` - Verification timeout in seconds (default: 30)
- `ABS_CHECK_LIBRARY` - Enable library indicators (default: auto-enabled if ABS configured)
- `ABS_LIBRARY_CACHE_TTL` - Library cache duration in seconds (default: 300)

**Optional - Behavior:**
- `IMPORT_MODE` - Import method: link (default), copy, or move
- `FLATTEN_DISCS` - Flatten multi-disc audiobooks (default: true)
- `QB_CATEGORY` - Category for new torrents (default: mam-audiofinder)
- `QB_POSTIMPORT_CATEGORY` - Category after import (default: empty/none)
- `MAX_COVERS_SIZE_MB` - Cover cache size limit (default: 500, 0 = direct fetch)

**Optional - Container:**
- `APP_PORT` - Host port mapping (default: 8008)
- `DL_DIR` - In-container download path (default: /media/torrents)
- `LIB_DIR` - In-container library path (default: /media/Books/Audiobooks)
- `DATA_DIR` - Host path for app data (databases, covers, logs)
- `PUID` - Container user ID (default: 1000)
- `PGID` - Container group ID (default: 1000)
- `UMASK` - File creation mask (default: 0002)

**Optional - Logging:**
- `LOG_MAX_MB` - Max log file size before rotation (default: 5)
- `LOG_MAX_FILES` - Number of rotated logs to keep (default: 5)

### Path Mapping Critical Notes

**Problem:** This app and qBittorrent run in separate containers with different filesystem views.

**Solution:** `MEDIA_ROOT` must be mounted to BOTH containers at consistent paths.

**Example docker-compose.yml:**
```yaml
services:
  mam-audiofinder:
    volumes:
      - /mnt/storage:/media  # MEDIA_ROOT mapped to /media

  qbittorrent:
    volumes:
      - /mnt/storage/torrents:/media/torrents  # Same parent
      - /mnt/storage/Books:/media/Books        # Same parent
```

**Container Path Expectations:**
- qBittorrent saves to: `/media/torrents/Book Title/`
- App imports from: `/media/torrents/Book Title/`
- App copies to: `/media/Books/Audiobooks/Book Title/`

**Validation:**
- `validate_torrent_path()` checks alignment on import
- Logs warning if paths don't match expected structure
- Shows clear error messages to user

## Logging & Rotation

**Log Location:** `/data/logs/app.log` (inside container)

**Rotation Strategy:**
- **Trigger:** Log file reaches LOG_MAX_MB size (default 5MB)
- **Action:** Rename app.log → app.log.1, create new app.log
- **History:** Keep LOG_MAX_FILES rotated logs (default 5)
- **Cleanup:** Delete oldest (app.log.5) when limit exceeded

**Log Levels:**
- INFO: Normal operations (search, import, verification)
- WARNING: Recoverable issues (retry attempts, path mismatches)
- ERROR: Operation failures (ABS unreachable, import failed)
- DEBUG: Detailed debugging (disabled in production)

**Output Destinations:**
- **File:** /data/logs/app.log (persistent, timestamped)
- **stderr:** Docker logs (real-time, for `docker compose logs -f`)

**Log Format:**
```
2025-01-15 10:30:45,123 - INFO - Search completed: 42 results for "Ender's Game"
2025-01-15 10:31:02,456 - WARNING - Verification retry 2/3 for "Speaker for the Dead"
2025-01-15 10:31:15,789 - INFO - Import verified: "Foundation" (score: 225, ASIN match)
```

**Viewing Logs:**
```bash
# Real-time via Docker
docker compose logs -f

# On host filesystem
cat /path/to/DATA_DIR/logs/app.log
tail -f /path/to/DATA_DIR/logs/app.log

# Via web UI
Visit: http://localhost:8008/logs
```

## Testing

### Test Structure

**Location:** `app/tests/`

**Test Files:**
- `conftest.py` - Fixtures and test configuration (258 lines)
- `test_verification.py` - Verification logic, scoring, retry (66 tests)
- `test_covers.py` - Cover caching, cleanup, healing (48 tests)
- `test_description_fetch.py` - Description fetching workflows (12 tests)
- `test_search.py` - Search payload, parsing, format detection (42 tests)
- `test_helpers.py` - Utility functions (35 tests)
- `test_migration_syntax.py` - SQL migration validation (20 tests)

**Total:** 223 test functions across 2,293 lines of test code

### Test Infrastructure

**pytest Configuration:**
- In-memory SQLite for both history.db and covers.db
- Mock-based for external APIs (MAM, ABS, qBittorrent)
- Fixtures for common test data
- Parametrized tests for edge cases

**Key Fixtures (conftest.py):**
- `temp_dir` - Temporary directory for file operations
- `mock_db_engine` - In-memory history database
- `mock_covers_db_engine` - In-memory covers database
- `mock_httpx_client` - Mock HTTP client
- `sample_mam_search_result` - Realistic MAM API response
- `sample_abs_library_items` - Sample ABS library data
- `sample_file_tree` - Multi-disc file structure

### Test Coverage Areas

**Verification System:**
- ASIN/ISBN priority matching (200 points)
- Title/author fuzzy matching
- Score threshold logic (verified vs mismatch)
- Retry logic with exponential backoff
- Timeout handling
- Connection error recovery

**Cover Caching:**
- Cache hit/miss scenarios
- Concurrent fetch deduplication
- Auto-cleanup when exceeding size limit
- Auto-healing for missing files
- Direct fetch mode (MAX_COVERS_SIZE_MB=0)

**Description Fetching:**
- Post-verification description update
- Updates to both history.db and covers.db
- Cache hit scenarios
- Failure handling (non-blocking)

**Search:**
- MAM payload construction
- Format detection (M4B, MP3, etc.)
- Data flattening (nested arrays to flat structure)
- Cache key generation
- Response parsing

**Utilities:**
- `sanitize()` - Filename sanitization
- `extract_disc_track()` - Disc/track number parsing
- `next_available()` - Filename collision handling
- Path validation

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest app/tests/ -v

# Run specific test file
pytest app/tests/test_verification.py -v

# Run with coverage
pytest app/tests/ --cov=app --cov-report=html

# Run specific test function
pytest app/tests/test_verification.py::test_verification_asin_match -v
```

### Test Philosophy

- **Fast:** In-memory databases, mocked external APIs
- **Isolated:** Each test is independent
- **Realistic:** Test data mirrors production scenarios
- **Coverage:** Focus on critical paths and edge cases
- **Maintainable:** Clear test names, minimal setup, good fixtures

## Common Tasks

### Adding a New Endpoint

1. **Create route function** in `app/routes/my_feature.py`:
   ```python
   from fastapi import APIRouter, HTTPException

   router = APIRouter()

   @router.get("/api/my-endpoint")
   async def my_endpoint():
       return {"status": "success"}
   ```

2. **Register route** in `app/routes/__init__.py`:
   ```python
   from .my_feature import router as my_feature_router

   def register_routes(app):
       # ... existing routes ...
       app.include_router(my_feature_router)
   ```

3. **Add frontend call** in appropriate view (e.g., `app/static/js/views/myView.js`):
   ```javascript
   import { api } from '../core/api.js';

   const data = await api.get('/api/my-endpoint');
   ```

4. **Test** and commit

### Adding a Database Column

1. **Create migration** `app/db/migrations/009_add_my_column.sql`:
   ```sql
   -- Add new column to history table
   ALTER TABLE history ADD COLUMN my_field TEXT;
   ```

2. **Restart container** (migrations run automatically on startup):
   ```bash
   docker compose up -d --build
   ```

3. **Verify migration** in logs:
   ```
   INFO - Applying migration 009_add_my_column.sql to history.db
   ```

**Migration Tips:**
- Use idempotent SQL (IF NOT EXISTS for columns/indexes)
- Number sequentially (009, 010, etc.)
- Target correct database: history.db or covers.db
- Test on copy of production database first

### Adding an Environment Variable

1. **Add to `app/config.py`**:
   ```python
   MY_VAR = os.getenv("MY_VAR", "default_value")
   ```

2. **Add to `env.example`**:
   ```bash
   MY_VAR=example_value  # Description of what this does
   ```

3. **Add validation** in `validate_env.py` (if required):
   ```python
   if not MY_VAR:
       print("ERROR: MY_VAR is required")
       sys.exit(1)
   ```

4. **Document** in README.md if user-facing

### Debugging Import Issues

**Path not found:**
- Check MEDIA_ROOT mapping in docker-compose.yml
- Verify qBittorrent save_path matches DL_DIR
- Check `docker exec -it mam-audiofinder ls /media/torrents`

**Permission denied:**
- Check PUID/PGID match host user
- Verify UMASK allows read/write
- Check `docker exec -it mam-audiofinder ls -la /media`

**Files not copied:**
- Check AUDIO_EXTS includes file extension
- Check logs for sanitization warnings
- Verify source files exist in torrent

**Verification fails:**
- Check ABS_BASE_URL is reachable from container
- Verify ABS_API_KEY is valid
- Check metadata.json was created by ABS
- Review verification note in history UI

## Security Considerations

**⚠️ WARNING: This application has ZERO authentication**

**Safe Deployment Only:**
- Behind VPN (Tailscale, WireGuard, etc.)
- Behind authenticated reverse proxy (Authelia, Authentik, etc.)
- Trusted local network with firewall protection
- **NEVER** exposed to public internet

**Credential Handling:**
- MAM_COOKIE: Stored in env vars only, never logged
- QB_PASS: Stored in env vars only, never logged
- ABS_API_KEY: Stored in env vars only, never logged
- Passed to containers via docker-compose.yml (not hardcoded)

**Input Validation:**
- All user input sanitized via `sanitize()` before filesystem operations
- Path traversal prevention (.. blocked)
- SQL injection prevention (parameterized queries)
- XSS prevention (escapeHtml() in frontend)

**File Operations:**
- UMASK applied to all created files
- Operations restricted to DL_DIR and LIB_DIR
- No arbitrary command execution

**API Rate Limiting:**
- MAM search cache (5 min) prevents abuse
- ABS request limiting (semaphore) prevents DoS
- Connection pooling prevents resource exhaustion
