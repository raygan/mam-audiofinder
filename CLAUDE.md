# CLAUDE.md - AI Assistant Guide for MAM Audiobook Finder

## Project Overview

**MAM Audiobook Finder** is a lightweight web application for searching MyAnonamouse audiobooks, adding them to qBittorrent, and importing completed downloads into Audiobookshelf. Personal use tool with zero authentication - Docker-first deployment, multi-page web app with modular ES6 JavaScript.

## Tech Stack

**Backend:** Python 3.12, FastAPI, Uvicorn, SQLite, httpx, Jinja2
**Frontend:** Vanilla JavaScript ES6 modules, HTML5, minimal CSS
**Infrastructure:** Docker, Docker Compose
**Testing:** pytest (223 test functions)

## Codebase Structure

```
mam-audiofinder/
├── app/
│   ├── main.py                 # FastAPI bootstrap
│   ├── config.py               # Environment configuration
│   ├── db/
│   │   ├── db.py              # Database engines and migrations
│   │   └── migrations/        # SQL migration files (001-011)
│   ├── abs_client.py          # Audiobookshelf API client (~850 lines)
│   ├── description_service.py # Unified description service (~330 lines)
│   ├── hardcover_client.py    # Hardcover GraphQL API client (~920 lines)
│   ├── covers.py              # CoverService class (~350 lines)
│   ├── qb_client.py           # qBittorrent API helpers
│   ├── torrent_helpers.py     # Torrent state and matching
│   ├── utils.py               # Utility functions
│   ├── routes/
│   │   ├── basic.py           # Health, config, page endpoints
│   │   ├── search.py          # MAM search
│   │   ├── history.py         # History CRUD
│   │   ├── qbittorrent.py     # qBittorrent operations
│   │   ├── import_route.py    # Import logic
│   │   ├── showcase.py        # Grouped search results
│   │   ├── series.py          # Hardcover series discovery
│   │   ├── description_route.py # Unified description API
│   │   ├── covers_route.py    # Cover serving
│   │   └── logs_route.py      # Logs endpoint
│   ├── static/
│   │   ├── js/
│   │   │   ├── core/          # api.js, router.js, utils.js
│   │   │   ├── services/      # coverLoader.js
│   │   │   ├── views/         # searchView, historyView, showcaseView, logsView
│   │   │   ├── components/    # importForm.js, libraryIndicator.js
│   │   │   └── pages/         # Entry scripts per page
│   │   └── css/               # Stylesheets
│   ├── templates/
│   │   └── *.html             # Jinja2 templates (base, search, history, showcase, logs)
│   └── demo_description_fetch.py # Live demo script for description service
├── tests/                     # 250+ test functions across 7 files
│   ├── conftest.py           # Fixtures and configuration
│   ├── test_search.py
│   ├── test_covers.py
│   ├── test_verification.py
│   ├── test_description_fetch.py
│   ├── test_description_service.py # 30+ tests for unified service
│   ├── test_helpers.py
│   └── test_migration_syntax.py
├── BACKEND.md                 # Technical implementation details
├── FRONTEND.md                # UI architecture documentation
├── README.md                  # User-facing documentation
├── TESTING.md                 # Testing guide
├── CLAUDE.md                  # AI assistant guide (this file)
├── env.example
├── Dockerfile
└── docker-compose.yml
```

## Architecture & Data Flow

### Request Flow
1. **Frontend:** Jinja2 templates + page-specific scripts (pages/*.js)
2. **Backend:** FastAPI endpoints (routes/)
3. **External Services:** MAM API, qBittorrent WebUI, Audiobookshelf API
4. **Storage:** SQLite (history.db, covers.db), filesystem (imports, covers)

### Key Workflows

**Search:** User Input → POST /search → MAM API (5min cache) → ABS Cover Fetch → Library Check → Display

**Add:** User Click → POST /add → Fetch .torrent → qBittorrent API → Tag with MAM ID → Save to DB

**Import:** POST /import → Validate Paths → Analyze Structure → Copy/Link/Move → Wait for metadata.json → **Verify (3 retries)** → **Fetch Description** → Update DB

**Verification:** Check ABS library → Score match (ASIN/ISBN=200pts, Title=100pts, Author=50pts) → Return verified/mismatch/not_found

**Cover Cache:** Check covers.db → If miss: ABS API → Download → Save to /data/covers/ → Auto-cleanup/healing

For detailed workflows, see [BACKEND.md](BACKEND.md).

## Key Modules

### Backend Core

**`main.py`:** Logging setup, DB init, FastAPI app creation, route registration

**`config.py`:** Environment variables with defaults

**`db/db.py`:** SQLAlchemy engines (history.db, covers.db), migration system

**`abs_client.py` (~850 lines):** Key methods:
- `verify_import()` - ASIN/ISBN matching, retry logic, scoring algorithm
- `check_library_items()` - Batch library checking with caching
- `fetch_item_details()` - Description/metadata fetching
- `_update_description_after_verification()` - Post-verification description fetch

**`description_service.py` (~330 lines):** Unified description fetching with cascading fallback:
- `get_description()` - ABS → Hardcover fallback with caching
- Smart matching: ASIN/ISBN (200pts), Title (100pts), Author (50pts)
- In-memory cache with 24hr TTL
- Source tracking ('abs', 'hardcover', 'none')

**`hardcover_client.py` (~920 lines):** Hardcover GraphQL API client:
- `search_series()` - Series discovery with caching
- `list_series_books()` - Book listings per series
- `search_book_by_title()` - Book search for description fallback
- Rate limiting (60 req/min) and retry logic

**`covers.py`:** CoverService with local caching, auto-cleanup, auto-healing

**`torrent_helpers.py`:** State mapping, path validation, MAM ID extraction, fuzzy matching

**`utils.py`:** sanitize(), next_available(), extract_disc_track(), try_hardlink()

### Routes

- `basic.py` - Page rendering (/, /history, /showcase, /logs), /health, /config
- `search.py` - POST /search, cover fetching
- `history.py` - GET /api/history, DELETE /api/history/{id}, POST /api/history/{id}/verify
- `qbittorrent.py` - GET /qb/torrents, GET /qb/torrent/{hash}/tree, POST /add
- `import_route.py` - POST /import (with verification + description fetch)
- `showcase.py` - GET /api/showcase (grouped search results)
- `series.py` - POST /api/series/search, GET /api/series/{id}/books (Hardcover integration)
- `description_route.py` - POST /api/description/fetch, GET /api/description/stats (unified description service)
- `covers_route.py` - GET /covers/{filename}
- `logs_route.py` - GET /api/logs

### Frontend Architecture

**Multi-page app:** Each route is separate HTML page with own entry script

**Core (~315 lines):** api.js (13 methods), router.js (URL state), utils.js

**Services:** coverLoader.js (lazy loading with IntersectionObserver)

**Views (~1,220 lines):** searchView, historyView, showcaseView, logsView

**Components:** importForm.js (multi-disc detection), libraryIndicator.js (badges)

**Patterns:** Event-driven, dependency injection, no build step

For detailed frontend architecture, see [FRONTEND.md](FRONTEND.md).

## Database Schemas

### history.db

```sql
CREATE TABLE history (
  id INTEGER PRIMARY KEY,
  mam_id TEXT, title TEXT, author TEXT, narrator TEXT, dl TEXT,
  added_at TEXT DEFAULT (datetime('now')),

  -- qBittorrent tracking
  qb_status TEXT, qb_hash TEXT,

  -- Import tracking
  imported_at TEXT,

  -- Audiobookshelf integration (Migration 004)
  abs_item_id TEXT,
  abs_cover_url TEXT,
  abs_cover_cached_at TEXT,

  -- Verification system (Migration 006)
  abs_verify_status TEXT,  -- 'verified', 'mismatch', 'not_found', 'unreachable', 'not_configured'
  abs_verify_note TEXT,

  -- Descriptions (Migration 007)
  abs_description TEXT,
  abs_metadata TEXT,       -- JSON blob
  abs_description_source TEXT
);
```

**Migrations:** 001-004 (initial + ABS), 006 (verification), 007 (descriptions)

### covers.db

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
```

**Migrations:** 005 (initial schema), 008 (descriptions)

## Key Features

### Import Verification
- Automatic verification after import (if ABS configured)
- ASIN/ISBN priority matching (200 points), fuzzy title/author matching
- 3 retry attempts with exponential backoff (1s, 2s, 4s)
- Status badges in UI: ✓ verified, ⚠ mismatch, ✗ not_found, ? unreachable
- Manual re-verification via "🔄 Verify" button

### Library Visibility
- Green checkmark badges on search/showcase for items already in library
- Batch checking with 5-minute cache (configurable via ABS_LIBRARY_CACHE_TTL)
- Auto-enabled when ABS is configured (or set ABS_CHECK_LIBRARY explicitly)

### Description Fetching
- Automatically fetched post-verification (score ≥100)
- Updates both history.db and covers.db
- Displayed in showcase view with expand/collapse
- 5-minute cache to avoid redundant API calls

### Showcase View
- Groups search results by normalized title (removes articles, punctuation)
- Card-based grid layout with covers
- Detail view shows all versions/editions per title
- URL state management (?detail=title-slug)

### Multi-Disc Flattening
- Auto-detects Disc/Disk/CD/Part patterns
- Flattens to sequential files (Part 001.mp3, Part 002.mp3, ...)
- Frontend shows before/after preview
- Controlled by FLATTEN_DISCS env var (default true)

### Cover Caching
- Separate covers.db database
- Local storage in /data/covers/
- Auto-cleanup when exceeding MAX_COVERS_SIZE_MB
- Auto-healing for missing files
- Progressive loading with lazy loading (IntersectionObserver)

### Hardcover Series Discovery
- Optional integration with Hardcover API for series metadata
- GraphQL API with rate limiting (60 req/min) and caching (5 min TTL)
- Limit parameter controls result count (configurable via HARDCOVER_SERIES_LIMIT, default: 20)
- **Note:** Pagination (offset/page) removed - non-functional in Hardcover API
- Frontend methods: `api.searchSeries()`, `api.getSeriesBooks()`

## Environment Configuration

See `env.example` for full list with comments.

**Required:** MAM_COOKIE, QB_URL/USER/PASS, MEDIA_ROOT, DATA_DIR

**Optional (ABS):** ABS_BASE_URL, ABS_API_KEY, ABS_LIBRARY_ID, ABS_VERIFY_TIMEOUT, ABS_CHECK_LIBRARY, ABS_LIBRARY_CACHE_TTL, MAX_COVERS_SIZE_MB

**Optional (Hardcover):** HARDCOVER_API_TOKEN, HARDCOVER_CACHE_TTL, HARDCOVER_RATE_LIMIT, HARDCOVER_SERIES_LIMIT

**Optional (Behavior):** IMPORT_MODE (link/copy/move), FLATTEN_DISCS, QB_CATEGORY, QB_POSTIMPORT_CATEGORY

**Optional (Container):** APP_PORT, DL_DIR, LIB_DIR, PUID, PGID, UMASK, LOG_MAX_MB, LOG_MAX_FILES

**Critical:** `MEDIA_ROOT` must be mounted to BOTH this app and qBittorrent containers at consistent paths.

## Development

### Setup

```bash
cp env.example .env          # Configure
docker compose up -d --build # Build and run
docker compose logs -f       # View logs
```

### Making Changes

**Backend:** Edit files → `docker compose up -d --build` → Check logs
**Frontend:** Edit JS/HTML/CSS → Rebuild → Hard refresh browser (Ctrl+Shift+R)
**Environment:** Edit .env → `docker compose up -d --force-recreate`

### Testing

**Two testing modes available - same test suite (223 tests), different environments:**

**Local Testing** (fast iteration, development):
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
make test-backend                          # Run all backend tests
make test-coverage                         # With coverage report
pytest app/tests/test_verification.py -v   # Specific file
```

**Container Testing** (integration, docker networking, can reach ABS):
```bash
make docker-test-build                     # Build test container (first time)
make docker-test-run                       # Run full test suite in container
make docker-test-backend                   # Backend tests only
make docker-test-frontend                  # Frontend tests (integrated Selenium)
make docker-test-shell                     # Debug in container
```

**Test Coverage:** Verification logic, cover caching, description fetch, search, helpers, migrations, frontend workflows

**Key Improvements:**
- Database paths now configurable via `DATA_DIR`, `HISTORY_DB_PATH`, `COVERS_DB_PATH` env vars
- Multi-stage Dockerfile: production stage (lean, ~200MB) + testing stage (with pytest, selenium, make, chromium)
- Integrated Selenium browser in test container (no separate 2GB selenium container needed)
- Isolated test data (`/data/test-data/`) doesn't interfere with production
- Live code mounting for rapid iteration in container tests

See [TESTING.md](TESTING.md) for comprehensive testing guide and troubleshooting.

## Important Patterns

### Error Handling

**Validate early, fail fast:**
```python
if not src_root.exists():
    raise HTTPException(status_code=404, detail=f"Source path not found: {src_root}")
```

**Best-effort for non-critical:**
```python
try:
    # ... category change ...
except Exception:
    pass  # Don't fail import
```

### Async/Await

- All FastAPI endpoints are async with httpx
- Database operations use sync SQLAlchemy

### Data Sanitization

**Backend:** Always use `sanitize()` before filesystem operations
**Frontend:** Always use `escapeHtml()` for user input

### Database Migrations

1. Create `app/db/migrations/009_my_change.sql` (next available number)
2. Write idempotent SQL (use IF NOT EXISTS)
3. Runs automatically on next startup
4. Smart routing: history table changes → history.db, covers table changes → covers.db
5. Current: 001-007 (history.db), 005,008 (covers.db)

## Common Tasks

### Add Endpoint

1. Create route in `app/routes/my_feature.py`
2. Register in `app/routes/__init__.py`
3. Add frontend call in appropriate view
4. Test and commit

### Add Environment Variable

1. Add to `env.example`
2. Add to `config.py` with default
3. Add validation in `validate_env.py` if required
4. Document in README.md if user-facing

### Add Database Column

Create `app/db/migrations/009_add_field.sql`:
```sql
ALTER TABLE history ADD COLUMN new_field TEXT;
```

Restart container - migration runs automatically.

### Debug Import Issues

**Path not found:** Check MEDIA_ROOT mapping, verify qB save_path matches DL_DIR
**Permission denied:** Check PUID/PGID, verify UMASK
**Files not copied:** Check AUDIO_EXTS filter, add logging
**Verification fails:** Check ABS_BASE_URL reachable, verify API key, check metadata.json created

## Debugging

```bash
# Logs
docker compose logs -f

# Container access
docker exec -it mam-audiofinder bash

# Permissions
docker exec -it mam-audiofinder ls -la /media /data

# Database
docker exec -it mam-audiofinder sqlite3 /data/history.db
sqlite> .schema history
sqlite> SELECT * FROM history LIMIT 5;
```

**Frontend:** DevTools (F12) → Console for errors, Network for API calls

## Security

**⚠️ WARNING: ZERO authentication**

**Safe Usage Only:**
- Behind VPN (Tailscale, WireGuard)
- Behind authenticated reverse proxy
- Trusted local network only
- NEVER public internet

**Credentials:** MAM_COOKIE and qB credentials in env vars only

## Code Style

**Python:** PEP 8, async endpoints, HTTPException for errors, minimal docstrings
**JavaScript:** ES6+, async/await, camelCase, no frameworks
**HTML/CSS:** Minimal classes, basic flexbox, dark theme with maroon accents

## AI Assistant Guidelines

### Making Changes
1. Read existing code first to understand patterns
2. Follow existing conventions
3. Test thoroughly (automated + manual)
4. Write descriptive commits ("why" not "what")
5. Update documentation if architecture changes

### Adding Features
1. Check if new env vars needed
2. Update README.md for user-facing features
3. Sanitize all user input
4. Provide clear error messages
5. Test edge cases

### Debugging
1. Check logs first
2. Verify path mappings
3. Check PUID/PGID permissions
4. Test API directly with curl
5. Inspect SQLite database

### Refactoring
1. Keep changes small and focused
2. Preserve existing behavior
3. Verify no regressions
4. Document architecture changes

## Project Philosophy

**Design Principles:**
- Simplicity over features
- Personal use over production
- Clear errors over silent failures
- Pragmatic over perfect

**Non-Goals:**
- Enterprise deployment
- Multi-tenancy
- High availability
- Public API exposure
- Advanced auth

**Maintenance:** Focus on bug fixes over features, preserve functionality, avoid over-engineering.

---

**Technical Details:** See [BACKEND.md](BACKEND.md) for implementation details, [FRONTEND.md](FRONTEND.md) for UI architecture.

*Update this document when making significant architecture or functionality changes.*
