# CLAUDE.md - AI Assistant Guide for MAM Audiobook Finder

## Project Overview

**MAM Audiobook Finder** is a lightweight web application that enables users to search MyAnonamouse (MAM) for audiobooks, add them to qBittorrent, and import completed downloads into an Audiobookshelf library.

**Key Characteristics:**
- Personal use tool (NOT for public deployment)
- No authentication (requires private network/VPN)
- Docker-first deployment strategy
- Multi-page web application with modular ES6 JavaScript

## Tech Stack

**Backend:** Python 3.12, FastAPI, Uvicorn, SQLite, httpx, Jinja2
**Frontend:** Vanilla JavaScript ES6 modules, HTML5, minimal CSS
**Infrastructure:** Docker, Docker Compose

## Codebase Structure

```
mam-audiofinder/
├── app/
│   ├── main.py                 # FastAPI bootstrap
│   ├── config.py               # Environment configuration
│   ├── db/
│   │   ├── db.py              # Database engines and migrations
│   │   └── migrations/        # SQL migration files (001-005)
│   ├── abs_client.py          # Audiobookshelf API client
│   ├── covers.py              # CoverService class
│   ├── qb_client.py           # qBittorrent API helpers
│   ├── torrent_helpers.py     # Torrent state and matching
│   ├── utils.py               # Utility functions
│   ├── routes/
│   │   ├── basic.py           # Health, config, page endpoints
│   │   ├── search.py          # MAM search
│   │   ├── history.py         # History CRUD
│   │   ├── qbittorrent.py     # qBittorrent operations
│   │   ├── import_route.py    # Import logic
│   │   ├── covers_route.py    # Cover serving
│   │   └── logs_route.py      # Logs endpoint
│   ├── static/
│   │   ├── js/
│   │   │   ├── core/          # api.js, router.js, utils.js
│   │   │   ├── services/      # coverLoader.js
│   │   │   ├── views/         # searchView, historyView, showcaseView, logsView
│   │   │   └── components/    # importForm.js
│   │   ├── pages/             # search.js, history.js, showcase.js, logs.js
│   │   └── css/               # Stylesheets
│   └── templates/
│       ├── base.html          # Base template with nav
│       ├── search.html        # Search page
│       ├── history.html       # History page
│       ├── showcase.html      # Showcase page
│       └── logs.html          # Logs page
├── tests/                     # Pytest suite (120 tests)
│   ├── conftest.py           # Fixtures and configuration
│   ├── test_search.py        # Search tests
│   ├── test_covers.py        # Cover caching tests
│   ├── test_verification.py  # ABS verification tests
│   └── test_helpers.py       # Utility tests
├── validate_env.py            # Startup validation
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

## Architecture & Data Flow

### Request Flow
1. **Frontend:** Jinja2 templates + page-specific scripts (pages/*.js)
2. **Backend:** FastAPI endpoints (routes/)
3. **External Services:** MAM API, qBittorrent WebUI, Audiobookshelf API
4. **Storage:** SQLite (history.db, covers.db), filesystem (imports, covers)

### Key Workflows

**Search:** User Input → POST /search → MAM API → ABS Cover Fetch → Display with Progressive Loading

**Add:** User Click → POST /add → Fetch .torrent → qBittorrent API → Tag with MAM ID → Save to DB

**Import:** POST /import → Match Torrent (hash/tag/fuzzy) → Validate Paths → Analyze Structure → Copy/Link/Move → Update Category

**Cover Cache:** Check covers.db → If miss: ABS API → Download → Save to /data/covers/ → Return Local URL

**State Tracking:** GET /history → Fetch Live States → Match to History → Display Status/Progress

## Key Modules

### Backend Core

**`main.py` (~70 lines):** Logging setup, DB init, FastAPI app creation, route registration

**`config.py` (~70 lines):** Environment variables, MAM cookie, qBittorrent/ABS config, UMASK

**`db/db.py` (~130 lines):** SQLAlchemy engines, migration system, connection pooling

**`abs_client.py` (~170 lines):** AudiobookshelfClient class, cover fetching, library search

**`covers.py` (~350 lines):** CoverService, local caching, auto-cleanup, auto-healing

**`torrent_helpers.py` (~220 lines):**
- `map_qb_state_to_display()` - State codes to user-friendly text
- `get_torrent_state()` - Fetch live torrent info
- `validate_torrent_path()` - Path alignment validation
- `extract_mam_id_from_tags()` - Extract MAM ID from tags
- `match_torrent_to_history()` - Match by hash/mam_id/fuzzy title

**`utils.py` (~110 lines):** sanitize(), next_available(), extract_disc_track(), try_hardlink()

### Routes

**basic.py:** GET / /history /showcase /logs (pages), GET /health /config
**search.py:** POST /search
**history.py:** GET /api/history, DELETE /api/history/{id}
**qbittorrent.py:** GET /qb/torrents, GET /qb/torrent/{hash}/tree, POST /add
**import_route.py:** POST /import
**covers_route.py:** GET /covers/{filename}
**logs_route.py:** GET /api/logs

### Frontend Architecture (Multi-Page ES6 Modules)

**Core (~315 lines):**
- `api.js` (~180): Centralized API client, 11 methods, cache-busting headers
- `router.js` (~115): URL state management, query parameter parsing, navigation
- `utils.js` (~30): escapeHtml(), formatSize()

**Services (~180 lines):**
- `coverLoader.js`: Lazy-loading with IntersectionObserver

**Views (~1,220 lines):**
- `searchView.js` (~230): Search form, results rendering, add to qB
- `historyView.js` (~180): History table, live states, import forms
- `showcaseView.js` (~405): Grid view, detail view, filtering
- `logsView.js` (~80): Log fetching, level filtering, syntax highlighting

**Components (~400 lines):**
- `importForm.js`: Torrent selection, multi-disc detection, tree visualization, flatten preview

**Pages (~500 lines):**
- Entry scripts for each page (search.js, history.js, showcase.js, logs.js)
- URL parameter restoration, view initialization, health checks

**Architecture Patterns:**
- Multi-page: Each page is separate route with own entry script
- Event-driven: Custom events (torrentAdded, importCompleted, routerStateChange)
- Dependency injection: DOM refs via constructor
- No build step: Native ES6 modules

## Database Schemas

### History Table
```sql
CREATE TABLE history (
  id INTEGER PRIMARY KEY,
  mam_id TEXT, title TEXT, author TEXT, narrator TEXT, dl TEXT,
  added_at TEXT DEFAULT (datetime('now')),
  qb_status TEXT, qb_hash TEXT, imported_at TEXT,
  abs_item_id TEXT, abs_cover_url TEXT, abs_cover_cached_at TEXT
)
```

### Covers Cache Table
```sql
CREATE TABLE covers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mam_id TEXT UNIQUE NOT NULL, title TEXT, author TEXT,
  cover_url TEXT NOT NULL, abs_item_id TEXT,
  local_file TEXT, file_size INTEGER,
  fetched_at TEXT DEFAULT (datetime('now'))
)
```

## Key Features

### FLATTEN_DISCS with Auto-Detection

**Problem:** Multi-disc audiobooks (Book/Disc 01/Track 01.mp3, Book/Disc 02/Track 01.mp3)
**Solution:** Flatten to sequential (Book/Part 001.mp3, Book/Part 002.mp3)

**Backend:** Per-request `flatten` parameter, extract_disc_track(), sequential renaming
**Detector:** `/qb/torrent/{hash}/tree` endpoint analyzes structure, detects Disc/Disk/CD/Part patterns
**Frontend:** Auto-checked checkbox when multi-disc detected, tree view, before/after preview

### Cover Caching System

- Separate covers.db database
- Local storage in /data/covers/
- Auto-cleanup when exceeding MAX_COVERS_SIZE_MB
- Connection pooling for concurrent fetches
- Auto-healing for missing files

### Testing Framework

**120 test cases** in pytest suite:
- Search payload construction and parsing
- Cover caching, cleanup, healing
- ABS verification and retry logic
- Utility functions (sanitize, paths, disc extraction)
- Mock-based for external APIs
- In-memory SQLite for DB tests

```bash
pytest tests/ -v                           # Run all
pytest tests/test_search.py -v             # Specific file
pytest tests/ --cov=app --cov-report=html  # Coverage
```

### Logging with Rotation

- Location: /data/logs/app.log
- Auto-rotation at LOG_MAX_MB (default 5MB)
- Keeps LOG_MAX_FILES (default 5) rotated logs
- Dual output: file (timestamped) + stderr (Docker)
- Python RotatingFileHandler

## Environment Configuration

### Required Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `MAM_COOKIE` | `mam_id=abc123...` | MAM session cookie |
| `QB_URL` | `http://qbittorrent:8080` | qBittorrent WebUI URL |
| `QB_USER` | `admin` | qBittorrent username |
| `QB_PASS` | `password123` | qBittorrent password |
| `MEDIA_ROOT` | `/mnt/media` | Host path for torrents and library |
| `DATA_DIR` | `/path/to/data` | Host path for database |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | `8008` | Host port |
| `DL_DIR` | `/media/torrents` | Container download path |
| `LIB_DIR` | `/media/Books/Audiobooks` | Container library path |
| `IMPORT_MODE` | `link` | Import method: link, copy, or move |
| `FLATTEN_DISCS` | `true` | Flatten multi-disc audiobooks |
| `QB_CATEGORY` | `mam-audiofinder` | Category for new torrents |
| `QB_POSTIMPORT_CATEGORY` | `` | Category after import |
| `PUID` | `1000` | Container user ID |
| `PGID` | `1000` | Container group ID |
| `UMASK` | `0002` | File creation mask |
| `LOG_MAX_MB` | `5` | Max log file size |
| `LOG_MAX_FILES` | `5` | Rotated logs to keep |

### Path Mapping

**Critical:** qBittorrent and this app run in separate containers with different filesystem views. `MEDIA_ROOT` must be mounted to BOTH containers at consistent paths.

**Example:**
```yaml
# This app
volumes:
  - /mnt/storage:/media

# qBittorrent
volumes:
  - /mnt/storage/torrents:/downloads
  - /mnt/storage/Books:/books
```

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
**Environment:** Edit .env → `docker compose up -d --force-recreate` (or `--build` if PUID/PGID changed)

### Git Workflow

- Branch naming: Must start with `claude/` (e.g., `claude/fix-bug-<session-id>`)
- Commits: Descriptive messages, focus on "why"

### Testing

**Automated:**
```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

**Manual Checklist:**
- Search, add to qB, import (single/multi-disc)
- History view, cover loading, logs
- Error handling (invalid paths, permissions)
- Path mapping issues

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

1. Create `app/db/migrations/006_my_change.sql`
2. Write idempotent SQL (use IF NOT EXISTS)
3. Runs automatically on next startup
4. Migrations 001-004 target history.db, 005+ target covers.db

## Common Tasks

### Add Endpoint

1. Create route in `app/routes/my_feature.py`
2. Register in `app/routes/__init__.py`
3. Add frontend call in appropriate view
4. Test and commit

### Add Environment Variable

1. Add to env.example
2. Add to config.py with default
3. Add validation in validate_env.py if needed
4. Document in README.md and this file

### Add Database Column

Create `app/db/migrations/006_add_field.sql`:
```sql
ALTER TABLE history ADD COLUMN new_field TEXT;
```

### Debug Import Issues

**Path not found:** Check MEDIA_ROOT mapping, verify qB save_path matches DL_DIR
**Permission denied:** Check PUID/PGID, verify UMASK
**Files not copied:** Check AUDIO_EXTS filter, add logging

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
- Behind authenticated proxy
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
5. Update CLAUDE.md if architecture changes

### Adding Features
1. Check if new env vars needed
2. Update README for user-facing features
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

*Update this document when making significant architecture or functionality changes.*
