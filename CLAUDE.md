# CLAUDE.md - AI Assistant Guide for MAM Audiobook Finder

## Project Overview

**MAM Audiobook Finder** is a lightweight web application that enables users to search MyAnonamouse (MAM) for audiobooks, add them to qBittorrent, and import completed downloads into an Audiobookshelf library. The project prioritizes simplicity and practical functionality for personal use.

**Key Characteristics:**
- Personal use tool (NOT designed for public/production deployment)
- No authentication layer (requires private network/VPN)
- Focus on user-friendly workflow for audiobook management
- Docker-first deployment strategy

## Tech Stack

### Backend
- **Language:** Python 3.12
- **Framework:** FastAPI (async web framework)
- **Server:** Uvicorn (ASGI server)
- **Database:** SQLite (via SQLAlchemy)
- **HTTP Client:** httpx (async HTTP client)
- **Templates:** Jinja2

### Frontend
- **Vanilla JavaScript** with ES6 modules (no frameworks)
- **HTML5** with minimal CSS
- **Single-page application** pattern
- **Modular architecture** - Organized into core, services, views, and components

### Infrastructure
- **Docker** (containerization)
- **Docker Compose** (orchestration)

## Codebase Structure

```
mam-audiofinder/
├── app/
│   ├── main.py                 # FastAPI application bootstrap
│   ├── config.py               # Configuration and env vars
│   ├── db/
│   │   ├── __init__.py        # Database module exports
│   │   ├── db.py              # Database engines and migrations
│   │   └── migrations/        # SQL migration files
│   │       ├── 001_initial_schema.sql
│   │       ├── 002_add_author_narrator.sql
│   │       ├── 003_add_imported_at.sql
│   │       ├── 004_add_abs_columns.sql
│   │       └── 005_create_covers_table.sql
│   ├── abs_client.py          # Audiobookshelf API client
│   ├── covers.py              # CoverService class
│   ├── qb_client.py           # qBittorrent API helpers
│   ├── torrent_helpers.py     # Torrent state and matching helpers
│   ├── utils.py               # Utility functions
│   ├── routes/
│   │   ├── __init__.py        # Routes aggregation
│   │   ├── basic.py           # Health and config endpoints
│   │   ├── search.py          # MAM search endpoint
│   │   ├── history.py         # History CRUD endpoints
│   │   ├── qbittorrent.py     # qBittorrent and add endpoints
│   │   ├── import_route.py    # Import endpoint
│   │   ├── covers_route.py    # Cover serving endpoint
│   │   └── logs_route.py      # Logs viewing endpoint
│   ├── static/
│   │   ├── app.js             # Frontend entry point (ES6 modules)
│   │   ├── js/                # Modular JavaScript architecture
│   │   │   ├── core/          # Core infrastructure
│   │   │   │   ├── api.js     # API client
│   │   │   │   ├── router.js  # URL routing and navigation
│   │   │   │   └── utils.js   # Utility functions
│   │   │   ├── services/      # Shared services
│   │   │   │   └── coverLoader.js # Cover lazy loading service
│   │   │   ├── views/         # View modules
│   │   │   │   ├── searchView.js   # Search functionality
│   │   │   │   ├── historyView.js  # History and imports
│   │   │   │   ├── showcaseView.js # Showcase grid/detail
│   │   │   │   └── logsView.js     # Logs viewer
│   │   │   └── components/    # Reusable components
│   │   │       └── importForm.js   # Import workflow
│   │   ├── css/               # Stylesheets (dark theme)
│   │   ├── favicon*.png       # Icons
│   │   └── screenshots/       # README images
│   └── templates/
│       └── index.html         # Single-page UI
├── validate_env.py            # Startup validation script
├── Dockerfile                 # Container image definition
├── docker-compose.yml         # Service orchestration
├── requirements.txt           # Python dependencies
├── env.example               # Environment template
├── README.md                 # User documentation
└── .gitignore               # Git ignore rules
```

## Architecture & Data Flow

### Request Flow
1. **User Interface** (index.html + app.js) → Frontend
2. **FastAPI Endpoints** (routes/) → Backend API
3. **External Services:**
   - MAM API (search, torrent download)
   - qBittorrent WebUI API (torrent management)
   - Audiobookshelf API (cover fetching, verification)
4. **SQLite Databases:**
   - history.db (torrent history, imports)
   - covers.db (cover cache metadata)
5. **Filesystem Operations:**
   - Import/copy/link files
   - Cover image caching

### Key Workflows

#### 1. Search Workflow
```
User Input → POST /search → MAM API → Parse Results → ABS Cover Fetch (async) → Display with Progressive Loading
```

#### 2. Add to qBittorrent Workflow
```
User Click → POST /add → Fetch .torrent → qBittorrent API → Tag with MAM ID → Save to DB
```

#### 3. Import Workflow
```
User Import → POST /import → Match Torrent (hash/tag/fuzzy) → Validate Paths → Analyze Structure → Copy/Link/Move Files → Update Category → Mark Complete
```

#### 4. Cover Caching Workflow
```
Cover Request → Check covers.db → If Miss: ABS API → Download Image → Save to /data/covers/ → Store Metadata → Return Local URL
```

#### 5. Torrent State Tracking
```
History View → GET /history → Fetch Live States (torrent_helpers) → Match to History Items → Display Status/Progress
```

## Key Files & Modules

### `/app/main.py` (~70 lines)

**Application bootstrap file:**
- Logging configuration setup
- Database initialization via migrations
- FastAPI app creation
- Static file mounting
- Route registration
- Startup event handlers

### `/app/config.py` (~70 lines)

**Configuration module:**
- Environment variable loading and parsing
- MAM cookie building
- qBittorrent connection settings
- Audiobookshelf configuration
- Import behavior settings (link/copy/move)
- UMASK application

### `/app/db/db.py` (~130 lines)

**Database management module:**
- SQLAlchemy engine creation (history.db and covers.db)
- Migration system implementation
- SQL migration file execution
- Connection pool configuration for concurrent operations

### `/app/db/migrations/*.sql`

**SQL migration files:**
- `001_initial_schema.sql` - Initial history table
- `002_add_author_narrator.sql` - Author/narrator columns
- `003_add_imported_at.sql` - Import tracking
- `004_add_abs_columns.sql` - Audiobookshelf integration
- `005_create_covers_table.sql` - Cover caching system

### `/app/abs_client.py` (~170 lines)

**Audiobookshelf API client class:**
- `AudiobookshelfClient` class with connection testing
- Cover fetching from ABS `/api/search/covers` endpoint
- Library item search for cover URLs
- Integration with CoverService for caching

### `/app/covers.py` (~350 lines)

**Cover management service:**
- `CoverService` class for cover operations
- Cover caching to local filesystem
- Automatic cleanup when exceeding MAX_COVERS_SIZE_MB
- Cover download with proper authentication
- Database integration for cache lookups
- Auto-healing for missing local files (redownload and relink)

### `/app/qb_client.py` (~20 lines)

**qBittorrent API helpers:**
- Async and sync login functions
- Session management

### `/app/torrent_helpers.py` (~220 lines)

**Torrent state management and matching helpers:**
- `map_qb_state_to_display()` - Convert qBittorrent state codes to user-friendly display text with color codes
- `get_torrent_state()` - Fetch live torrent info from qBittorrent (state, progress, paths, etc.)
- `validate_torrent_path()` - Check if torrent paths align with DL_DIR configuration
- `extract_mam_id_from_tags()` - Extract MAM ID from qBittorrent tags for matching
- `match_torrent_to_history()` - Find matching torrent for history item using hash, mam_id, or fuzzy title matching

### `/app/utils.py` (~110 lines)

**Utility functions:**
- `sanitize()` - Filename sanitization
- `next_available()` - Find non-conflicting paths
- `extract_disc_track()` - Parse disc/track numbers
- `try_hardlink()` - Attempt hardlink creation

### `/app/routes/` Package

**Modular route definitions:**

#### `routes/basic.py`
- `GET /` - Serve main UI
- `GET /health` - Health check
- `GET /config` - Return app configuration

#### `routes/search.py`
- `POST /search` - Search MAM for audiobooks
- Helper functions: `flatten()`, `detect_format()`

#### `routes/history.py`
- `GET /history` - Get torrent history
- `DELETE /history/{row_id}` - Delete history entry

#### `routes/qbittorrent.py`
- `GET /qb/torrents` - List completed torrents
- `POST /add` - Add torrent to qBittorrent

#### `routes/import_route.py`
- `POST /import` - Import torrent to library
- Helper function: `copy_one()`

#### `routes/covers_route.py`
- `GET /covers/{filename}` - Serve cached cover images

#### `routes/logs_route.py`
- `GET /api/logs` - Read application logs with filtering by level and line count

## API Endpoints

| Route | Method | Purpose | Module |
|-------|--------|---------|--------|
| `/` | GET | Serve UI | routes/basic.py |
| `/health` | GET | Health check | routes/basic.py |
| `/config` | GET | Return config | routes/basic.py |
| `/search` | POST | Search MAM | routes/search.py |
| `/add` | POST | Add to qBittorrent | routes/qbittorrent.py |
| `/history` | GET | Fetch history | routes/history.py |
| `/history/{id}` | DELETE | Remove history item | routes/history.py |
| `/qb/torrents` | GET | List completed torrents | routes/qbittorrent.py |
| `/qb/torrent/{hash}/tree` | GET | Get torrent file tree with multi-disc detection | routes/qbittorrent.py |
| `/import` | POST | Import to library | routes/import_route.py |
| `/covers/{filename}` | GET | Serve cover image | routes/covers_route.py |
| `/api/logs` | GET | Read application logs with filtering | routes/logs_route.py |

## Database Schemas

### History Table
```sql
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
  abs_cover_cached_at TEXT
)
```

### Covers Cache Table
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
  fetched_at TEXT DEFAULT (datetime('now'))
)
```

## Key Features & Implementations

### FLATTEN_DISCS Feature with UI Controls

**Problem:** Multi-disc audiobooks have structure like:
```
Book/Disc 01/Track 01.mp3
Book/Disc 02/Track 01.mp3
```

**Solution:** Flatten to sequential files:
```
Book/Part 001.mp3
Book/Part 002.mp3
```

**Implementation:**

#### Backend (routes/import_route.py)
1. Accept per-request `flatten` parameter (overrides global `FLATTEN_DISCS`)
2. Extract disc/track numbers from all files using `extract_disc_track()`
3. Sort by (disc_num, track_num)
4. Rename sequentially as "Part 001.mp3", "Part 002.mp3", etc.

#### Chapter Detector (routes/qbittorrent.py)
New endpoint `/qb/torrent/{hash}/tree` provides:
- File structure analysis
- Multi-disc pattern detection (Disc/Disk/CD/Part + numbered tracks)
- Automatic recommendation when 2+ discs detected
- Fallback to filesystem if qBittorrent API data unavailable

**Detection Patterns:**
- Directories: `Disc \d+`, `Disk \d+`, `CD \d+`, `Part \d+`
- Files: `Track \d+`, `Chapter \d+`, `^\d+`

#### Frontend UI (app.js)
Import form now includes:
1. **Flatten Checkbox:** User can enable/disable per-import
2. **Auto-Detection:** Checkbox auto-checked when multi-disc detected
3. **Tree View Button:** "📁 View Files" shows file structure
4. **Preview Panel:** Shows before/after comparison when flatten enabled
5. **Detection Hints:** Visual feedback about disc count and recommendation

**User Flow:**
1. Click "Import" on history item → form expands
2. Select torrent from dropdown
3. Backend automatically analyzes file structure
4. Flatten checkbox auto-checks if multi-disc detected
5. User can click "View Files" to see structure and preview
6. User can manually toggle flatten checkbox
7. Import proceeds with chosen setting

### Cover Caching System
**Architecture:**
- Separate `covers.db` database for caching
- Local file storage in `/data/covers/`
- Automatic cleanup when exceeding MAX_COVERS_SIZE_MB
- Connection pooling for concurrent fetches

**Implementation** (in `covers.py`):
1. Check cache by MAM ID
2. If miss, fetch from Audiobookshelf API
3. Download and save image locally
4. Store metadata in covers database
5. Return local URL (`/covers/{filename}`) or remote URL

### Frontend Architecture - Modular JavaScript (ES6)

**Overview:** The frontend has been refactored from a monolithic 1,448-line `app.js` into a clean modular architecture totaling ~2,400 lines across focused modules.

#### `/app/static/app.js` (~240 lines)

**Main Application Entry Point:**
- `App` class that orchestrates all view modules
- DOM element collection and initialization
- View instantiation with dependency injection
- Navigation handler setup (search, history, showcase, logs)
- Router event handling for browser back/forward
- Health check integration with visual indicator
- URL state restoration on page load
- Uses ES6 `type="module"` for native browser module loading

#### `/app/static/js/core/` - Core Infrastructure (~371 lines)

**`api.js` (~180 lines):**
- Centralized API client for all backend endpoints
- 11 methods covering: health, config, search, addTorrent, getHistory, deleteHistoryItem, getCompletedTorrents, getTorrentTree, importTorrent, getLogs, fetchCover, getShowcase
- Cache-busting headers for live data (no-cache)
- Consistent error handling with detailed messages
- JSDoc documentation for all methods

**`router.js` (~130 lines):**
- Router class for URL state and navigation management
- `getStateFromURL()` - Parse URL query parameters
- `updateURL()` - Update browser history with new state
- `getCurrentState()` - Extract current UI state
- `handlePopState()` - Browser back/forward navigation
- `navigateTo()` - Programmatic view switching
- `showView()` - Show/hide view cards with smooth scrolling
- Custom events: `routerStateChange`, `routerViewChange`

**`utils.js` (~30 lines):**
- `escapeHtml()` - XSS protection for user input
- `formatSize()` - Human-readable file sizes (B, KB, MB, GB, TB)
- Pure utility functions with no side effects

#### `/app/static/js/services/` - Shared Services (~180 lines)

**`coverLoader.js` (~180 lines):**
- CoverLoader service for lazy-loading cover images
- IntersectionObserver integration for progressive loading
- Row state management for tracking cover metadata
- `init()` - Initialize observer with 50px margin
- `observe(element)` - Observe element for lazy loading
- `fetchCoverForItem()` - Fetch and render cover with error handling
- `createCoverContainer()` - Create skeleton placeholders
- Prevents duplicate fetches by unobserving after trigger

#### `/app/static/js/views/` - View Modules (~1,220 lines)

**`searchView.js` (~230 lines):**
- Search form submission and execution
- Results rendering with lazy-loaded covers
- Add to qBittorrent functionality
- URL state management integration
- Emits `torrentAdded` event for cross-view communication

**`historyView.js` (~180 lines):**
- History table rendering with live torrent states
- Empty state handling
- Import button with expandable forms
- Remove item functionality
- Listens for `torrentAdded` and `importCompleted` events
- Updates status display after import

**`showcaseView.js` (~330 lines):**
- Grid view with lazy-loaded covers
- Detail view with versions table
- Search and filtering controls
- Add to qBittorrent from showcase
- Cover loading for both grid and detail views
- Click handlers for card expansion

**`logsView.js` (~80 lines):**
- Log fetching with level filtering (INFO, WARNING, ERROR)
- Syntax highlighting for log levels
- Auto-scroll option
- Refresh and filter controls
- Configurable line count (50-1000)

#### `/app/static/js/components/` - Reusable Components (~400 lines)

**`importForm.js` (~400 lines):**
- Complex import workflow management
- Torrent selection and matching (hash, MAM ID, fuzzy title)
- Multi-disc auto-detection via `/qb/torrent/{hash}/tree`
- File tree visualization (original and flattened preview)
- Flatten checkbox with recommendations
- Import execution with progress tracking
- Path validation warnings
- Emits `importCompleted` event on success
- Recursive tree rendering for hierarchical file structure

#### Key Architecture Patterns

**Event-Driven Communication:**
- Views don't directly call each other
- Custom events: `torrentAdded`, `importCompleted`, `routerStateChange`, `routerViewChange`
- Loose coupling between modules

**Dependency Injection:**
- Views receive DOM element references via constructor
- Router passed to views that need navigation
- No global state (except `window.app`)

**Module Organization:**
- **Core:** Infrastructure (API, routing, utilities)
- **Services:** Shared functionality (cover loading)
- **Views:** Feature-specific logic (search, history, showcase, logs)
- **Components:** Complex reusable widgets (import form)

**No Build Step Required:**
- Native ES6 modules work in modern browsers
- `import`/`export` syntax throughout
- Loaded via `<script type="module">`
- Better browser caching (each module cached separately)

### `/validate_env.py` (60 lines)

**Startup Validation Script:**
- Checks for common configuration errors
- Validates PUID/PGID combination
- Validates UMASK format (octal)
- Warns about missing MAM_COOKIE
- Prevents container startup on critical errors

**Common Error Checks:**
- GUID vs PGID typo
- PUID set without PGID
- Invalid UMASK format

### `/Dockerfile` (34 lines)

**Build Arguments:**
- `PUID` (default: 1000) - User ID
- `PGID` (default: 1000) - Group ID

**Build Process:**
1. Base image: `python:3.12-slim`
2. Install system dependencies (curl, ca-certificates)
3. Create user/group with specified IDs
4. Install Python dependencies
5. Copy application files
6. Set ownership to appuser
7. Run as non-root user

**Important:** If PUID/PGID changes, container MUST be rebuilt:
```bash
docker compose up -d --build
```

### `/docker-compose.yml` (21 lines)

**Service Configuration:**
- Builds with PUID/PGID args
- Maps APP_PORT to container port 8080
- Mounts DATA_DIR and MEDIA_ROOT volumes
- Sets restart policy: unless-stopped
- Runs as specified user (PUID:PGID)

## Development Workflows

### Local Development Setup

**Prerequisites:**
1. Python 3.12+
2. Docker & Docker Compose
3. Access to qBittorrent instance
4. MAM account with session cookie

**Steps:**
```bash
# 1. Clone repository
git clone <repo-url>
cd mam-audiofinder

# 2. Configure environment
cp env.example .env
# Edit .env with your credentials

# 3. Build and run
docker compose up -d --build

# 4. View logs
docker compose logs -f

# 5. Access UI
open http://localhost:8008
```

### Making Code Changes

#### Backend Changes (main.py)
```bash
# 1. Edit app/main.py
# 2. Rebuild container
docker compose up -d --build

# 3. Check logs for errors
docker compose logs -f
```

#### Frontend Changes (JavaScript modules, HTML, CSS)
```bash
# 1. Edit files in app/static/js/, app/static/, or app/templates/
#    - Core modules: app/static/js/core/*.js
#    - Services: app/static/js/services/*.js
#    - Views: app/static/js/views/*.js
#    - Components: app/static/js/components/*.js
#    - Entry point: app/static/app.js
#    - HTML: app/templates/index.html
#    - CSS: app/static/css/*.css

# 2. Rebuild container (FastAPI serves static files)
docker compose up -d --build

# 3. Hard refresh browser (Ctrl+Shift+R) to clear module cache
#    Or open DevTools and disable cache while DevTools is open
```

#### Environment Changes
```bash
# 1. Edit .env
# 2. Recreate container
docker compose up -d --force-recreate

# 3. If PUID/PGID changed:
docker compose up -d --build
```

### Git Workflow

**Branch Naming Convention:**
- All development branches MUST start with `claude/`
- Example: `claude/fix-import-bug-<session-id>`

**Commit Guidelines:**
- Use descriptive commit messages
- Follow conventional commit style when possible
- Focus on "why" rather than "what"

**Example:**
```bash
git add .
git commit -m "Fix import validation to handle missing source paths

The import would silently fail when qBittorrent's content_path didn't
match the container's filesystem. Added validation and clear error
messages to help users debug path mapping issues."
```

### Testing Changes

**Manual Testing Checklist:**
1. Search functionality (various queries)
2. Add to qBittorrent (check category, tags)
3. Import workflow (single-file and multi-disc)
4. History view (add, import, remove)
5. Error handling (invalid paths, missing files)
6. UI responsiveness (mobile/desktop)

**Common Test Scenarios:**
- Single-file torrent import
- Multi-disc audiobook with FLATTEN_DISCS=true
- Multi-disc audiobook with FLATTEN_DISCS=false
- Path mapping issues (qBittorrent vs container paths)
- Permission errors (PUID/PGID mismatch)

## Environment Configuration

### Required Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `MAM_COOKIE` | `mam_id=abc123...` | MAM session cookie (ASN-locked recommended) |
| `QB_URL` | `http://qbittorrent:8080` | qBittorrent WebUI URL |
| `QB_USER` | `admin` | qBittorrent username |
| `QB_PASS` | `password123` | qBittorrent password |
| `MEDIA_ROOT` | `/mnt/media` | Host path containing both torrents and library |
| `DATA_DIR` | `/path/to/data` | Host path for app database |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | `8008` | Host port for web UI |
| `DL_DIR` | `/media/torrents` | Container path for downloads |
| `LIB_DIR` | `/media/Books/Audiobooks` | Container path for library |
| `IMPORT_MODE` | `link` | Import method: link, copy, or move |
| `FLATTEN_DISCS` | `true` | Flatten multi-disc audiobooks |
| `QB_CATEGORY` | `mam-audiofinder` | Category for new torrents |
| `QB_POSTIMPORT_CATEGORY` | `` | Category after import (empty = clear) |
| `PUID` | `1000` | Container user ID |
| `PGID` | `1000` | Container group ID |
| `UMASK` | `0002` | File creation mask |
| `LOG_MAX_MB` | `5` | Max size per log file in MB before rotation |
| `LOG_MAX_FILES` | `5` | Number of rotated log files to keep |

### Logging Configuration

**Location:** `/data/logs/app.log` (inside container)

**Features:**
- **Automatic Rotation:** When `app.log` reaches `LOG_MAX_MB` (default 5MB), it's rotated to `app.log.1`
- **History Management:** Keeps up to `LOG_MAX_FILES` (default 5) rotated logs, oldest are automatically deleted
- **Dual Output:** Logs go to both file (with timestamps) and stderr (for Docker logs)
- **Directory Creation:** `/data/logs` directory is created automatically on startup

**Log Levels Used:**
- `logger.info()` - Normal operations, status updates
- `logger.warning()` - Non-critical issues, fallback behavior
- `logger.error()` - Errors that don't stop execution
- `logger.exception()` - Errors with full traceback

**Implementation Details:**
- Uses Python's `logging` module with `RotatingFileHandler`
- Console handler uses simple format (just message) for Docker compatibility
- File handler uses timestamped format: `%(asctime)s - %(levelname)s - %(message)s`
- Logger name: `mam-audiofinder`

**Accessing Logs:**
```bash
# Via Docker
docker compose logs -f

# Via file on host (if DATA_DIR=/path/to/data)
cat /path/to/data/logs/app.log
cat /path/to/data/logs/app.log.1  # Previous rotation
```

### Path Mapping Concepts

**Critical Understanding:**
- qBittorrent runs in its own container with its own filesystem view
- This app runs in a separate container with a different filesystem view
- `MEDIA_ROOT` must be mounted to BOTH containers at consistent paths

**Example Setup:**
```yaml
# docker-compose.yml (this app)
volumes:
  - /mnt/storage:/media

# docker-compose.yml (qbittorrent)
volumes:
  - /mnt/storage/torrents:/downloads
  - /mnt/storage/Books:/books
```

**Path Mapping Logic** (in `routes/import_route.py`):
```python
def map_qb_path(p: str) -> str:
    # qB returns /downloads/Book
    # This app needs /media/torrents/Book
    prefix = QB_INNER_DL_PREFIX.rstrip("/")
    if p == prefix or p.startswith(prefix + "/"):
        return p.replace(QB_INNER_DL_PREFIX, DL_DIR, 1)
    if p.startswith("/media/"):
        return p
    p = p.replace("/mnt/user/media", "/media", 1)
    p = p.replace("/mnt/media", "/media", 1)
    return p
```

## Important Patterns & Conventions

### Error Handling

**Pattern: Validate Early, Fail Fast**
```python
# Example from /import endpoint (lines 529-533)
if not src_root.exists():
    raise HTTPException(
        status_code=404,
        detail=f"Source path not found: {src_root}"
    )
```

**Pattern: Best-Effort Non-Critical Operations**
```python
# Example: Category change after import (lines 607-623)
try:
    # ... change category ...
except Exception as _e:
    # Don't fail import if this errors
    pass
```

### Async/Await Patterns

**All FastAPI endpoints are async:**
```python
@app.post("/search")
async def search(payload: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(...)
```

**Exception: Database operations use sync SQLAlchemy:**
```python
with engine.begin() as cx:
    cx.execute(text("INSERT INTO ..."))
```

### Data Sanitization

**Always sanitize user input before filesystem operations:**
```python
def sanitize(name: str) -> str:
    s = name.strip().replace(":", " -").replace("\\", "﹨").replace("/", "﹨")
    return re.sub(r"\s+", " ", s)[:200] or "Unknown"
```

**Always escape HTML in frontend:**
```javascript
function escapeHtml(s) {
  return (s || '').toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}
```

### File Operations

**Pattern: Check before copy, provide fallback**
```python
def copy_one(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)  # Ensure parent exists
    if IMPORT_MODE == "link":
        if try_hardlink(src, dst):
            return "linked"
        else:
            shutil.copy2(src, dst)  # Fallback to copy
            return "copied"
```

### Database Migrations

**New Migration System:**
Migrations are now stored in SQL files in `app/db/migrations/` and executed at startup by `db/db.py`:

**Adding a new migration:**
1. Create a new file: `app/db/migrations/006_my_change.sql`
2. Write idempotent SQL (use `IF NOT EXISTS` or expect errors for duplicates)
3. Migration runs automatically on next app startup

**Example migration file:**
```sql
-- 006_add_new_column.sql
ALTER TABLE history ADD COLUMN my_column TEXT;
```

**Migration execution:**
- Migrations run in numerical order (001, 002, 003...)
- Each statement executed independently
- Errors are logged but don't stop other migrations (allows idempotency)
- Migrations 001-004 target `history.db`, 005+ target `covers.db`

## Recent Development History

### Recent Features & Fixes

1. **Frontend Modular Refactor** (2025-11-16)
   - Refactored 1,448-line monolithic `app.js` into modular ES6 architecture
   - Created 9 focused modules totaling ~2,400 well-structured lines
   - **Core modules** (371 lines): api.js, router.js, utils.js
   - **Services** (180 lines): coverLoader.js with IntersectionObserver
   - **Views** (1,220 lines): searchView, historyView, showcaseView, logsView
   - **Components** (400 lines): importForm with complex workflow logic
   - **App entry point** (240 lines): orchestration and dependency injection
   - Benefits: improved maintainability, testability, reusability, debugging
   - Event-driven architecture: torrentAdded, importCompleted, routerStateChange
   - No build step required - native ES6 modules in modern browsers
   - Better browser caching (each module cached separately)
   - Clear separation of concerns (core, services, views, components)
   - JSDoc documentation throughout all modules
   - Cache-busting headers added to prevent stale data issues
   - Fixed qBittorrent state update bug with improved error logging

2. **Top-Level Task Bar with Logs View**
   - Added persistent navigation task bar at top of page
   - Quick access buttons for Search, History, and Logs views
   - Integrated health status indicator in task bar
   - New `/api/logs` endpoint to read application logs
   - Logs view with filtering by log level (INFO, WARNING, ERROR)
   - Configurable log display (50-1000 lines)
   - Auto-scroll option for logs
   - Syntax highlighting for log levels
   - URL state management for all views (search, history, logs)
   - View switching helper function for clean navigation
   - Sticky task bar with maroon accent styling
   - Responsive design for mobile/desktop

2. **Live Torrent State Tracking & Smart Import Matching**
   - Created `torrent_helpers.py` module with state management functions
   - Real-time torrent status display in history view (downloading, seeding, progress %)
   - User-friendly state mapping with color-coded indicators
   - Smart torrent matching: by hash, MAM ID tags, or fuzzy title matching
   - Path validation to detect mismatched qBittorrent/container paths
   - Improved import reliability with better torrent identification

2. **Shareable Search/History URLs** (commit 616a566)
   - URL state management using browser History API
   - Search parameters persist in URL query string
   - Support for ?q=search&view=history to restore app state
   - Shareable links for specific searches and history views
   - Back/forward navigation respects URL state

3. **Flatten UI with Tree View & Chapter Detector**
   - Added per-import flatten checkbox with auto-detection
   - New `/qb/torrent/{hash}/tree` endpoint for file structure analysis
   - Chapter detector automatically identifies multi-disc audiobooks
   - Tree view shows file structure with before/after preview
   - Smart detection of disc patterns (Disc/Disk/CD/Part + tracks)
   - Fallback to filesystem if qBittorrent data unavailable
   - Visual hints show disc count and recommendation
   - Import endpoint accepts per-request `flatten` parameter

4. **Code Refactoring & Modularization** (v0.4.0)
   - Split monolithic main.py into modular components
   - Created dedicated modules: config.py, db/, covers.py, abs_client.py, utils.py, qb_client.py, torrent_helpers.py
   - Organized routes into routes/ package with separate files per domain
   - Implemented SQL migration system in db/migrations/
   - Wrapped cover logic in CoverService class
   - Improved code maintainability and testability

5. **Audiobookshelf Cover Integration & Caching**
   - Separate covers.db database for cover cache metadata
   - Local filesystem caching in /data/covers/
   - Progressive cover loading with skeleton placeholders
   - Automatic cleanup when exceeding MAX_COVERS_SIZE_MB
   - Auto-healing for missing local files (redownload and relink)
   - Connection pooling for concurrent cover fetches

6. **Centralized Log Rotation**
   - Python logging module with RotatingFileHandler
   - Configurable via LOG_MAX_FILES (default 5) and LOG_MAX_MB (default 5)
   - Logs stored in /data/logs/app.log with automatic rotation
   - Dual output to file (with timestamps) and stderr (for Docker)

7. **Dark Theme with Maroon Accents**
   - Complete UI redesign with dark gradient backgrounds
   - Maroon accent colors for buttons and focus states
   - Improved contrast and WCAG AA compliance
   - Translucent panels with subtle borders
   - Centralized CSS with utility classes

8. **Hardlink Verification & Display** (commit 32616c9)
   - Added visual feedback showing whether files were hardlinked vs copied
   - Improved transparency in import process

9. **Import Validation** (commit 7c6e1c9)
   - Fixed silent failures during import
   - Added clear error messages for missing paths
   - Validates source exists before attempting copy

10. **Docker Permission Fixes** (commits 7a78a96, 041243d)
    - Implemented proper PUID/PGID support
    - Added startup validation for common errors
    - Fixed GUID vs PGID typo issues

### Known Limitations

1. **No Authentication**
   - Intentional design choice
   - MUST run behind VPN/private network
   - NOT suitable for public deployment

2. **Single User**
   - No user management
   - All operations share same MAM/qBittorrent credentials

3. **Limited Error Recovery**
   - Failed imports don't automatically retry
   - Manual intervention required for edge cases

4. **Path Mapping Complexity**
   - Requires understanding of Docker volume mapping
   - Different path perspectives between containers can confuse users

## Common Tasks for AI Assistants

### Adding a New Endpoint

```python
# 1. Create route in appropriate file (or new file in app/routes/)
# Example: app/routes/my_feature.py
from fastapi import APIRouter

router = APIRouter()

@router.post("/new-feature")
async def new_feature(body: dict):
    # Implementation
    return {"ok": True}

# 2. Register router in app/routes/__init__.py
from .my_feature import router as my_feature_router
main_router.include_router(my_feature_router)

# 3. Add frontend call in app.js
async function callNewFeature() {
    const r = await fetch('/new-feature', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({...})
    });
    return r.json();
}

# 4. Test manually
# 5. Commit with descriptive message
```

### Adding Environment Variable

```python
# 1. Add to env.example
NEW_SETTING=default_value

# 2. Add to app/config.py
NEW_SETTING = os.getenv("NEW_SETTING", "default_value")

# 3. Import in modules that need it
from config import NEW_SETTING

# 4. Add validation in validate_env.py if needed
if not os.getenv("NEW_SETTING"):
    warnings.append("WARNING: NEW_SETTING not set...")

# 5. Document in README.md
# 6. Update CLAUDE.md environment table
```

### Debugging Import Issues

**Common Issues:**
1. **Path not found**
   - Check MEDIA_ROOT mapping
   - Verify qBittorrent's save_path matches DL_DIR
   - Add logging: `print(f"Source: {src_root}, exists: {src_root.exists()}")`

2. **Permission denied**
   - Check PUID/PGID matches host user
   - Verify UMASK is correct
   - Test: `docker exec -it mam-audiofinder ls -la /media`

3. **Files not copied**
   - Check AUDIO_EXTS filter (currently None = all files except .cue)
   - Verify files aren't .cue only
   - Add logging in copy_one()

### Improving Error Messages

**Pattern:**
```python
# Bad
raise HTTPException(status_code=404, detail="Not found")

# Good
raise HTTPException(
    status_code=404,
    detail=f"Source path not found: {src_root}. "
           f"content_path from qB: {content_path}. "
           f"Check MEDIA_ROOT mapping in docker-compose.yml"
)
```

### Adding Database Column

```sql
# 1. Create a new migration file
# app/db/migrations/006_add_new_field.sql

-- Add new column to history table
ALTER TABLE history ADD COLUMN new_field TEXT;

-- (Optional) Create index if needed
CREATE INDEX IF NOT EXISTS idx_history_new_field ON history(new_field);
```

**Notes:**
- Use the next available number (001, 002, 003, etc.)
- Migration runs automatically on next container restart
- SQL will error if column exists, but migration system handles this gracefully
- For covers table, use migration number >= 005

## Security Considerations

### Current Security Posture

**⚠️ WARNING: This app has ZERO authentication**

**Safe Usage:**
- Behind VPN (Tailscale, WireGuard)
- Behind authenticated proxy (Cloudflare Access)
- On trusted local network only
- NEVER exposed to public internet

**Credentials Handling:**
- MAM_COOKIE in environment variable (not in code)
- qBittorrent credentials in environment variable
- SQLite database contains torrent history (no passwords)

### Potential Security Improvements (NOT IMPLEMENTED)

If forking for production use, consider:
1. Add authentication (OAuth, basic auth, API keys)
2. Input validation on all endpoints
3. Rate limiting
4. CSRF protection
5. Content Security Policy headers
6. SQL parameterization (already done via SQLAlchemy)
7. HTML escaping (already done in frontend)

## Debugging Tips

### View Container Logs
```bash
docker compose logs -f
```

### Execute Commands in Container
```bash
docker exec -it mam-audiofinder bash
```

### Check File Permissions
```bash
docker exec -it mam-audiofinder ls -la /media
docker exec -it mam-audiofinder ls -la /data
```

### Test API Endpoints
```bash
# Health check
curl http://localhost:8008/health

# Config
curl http://localhost:8008/config

# Search (requires MAM_COOKIE)
curl -X POST http://localhost:8008/search \
  -H 'Content-Type: application/json' \
  -d '{"tor":{"text":"test"},"perpage":5}'
```

### Check Database
```bash
docker exec -it mam-audiofinder sqlite3 /data/history.db
sqlite> .schema history
sqlite> SELECT * FROM history LIMIT 5;
sqlite> .quit
```

### Frontend Debugging
- Open browser DevTools (F12)
- Check Console for JavaScript errors
- Check Network tab for API calls
- Check failed requests for error messages

## Code Style & Conventions

### Python (main.py, validate_env.py)
- **PEP 8** generally followed
- **Line length:** No strict limit (some lines >100 chars)
- **Imports:** Standard library, then third-party, then local
- **Type hints:** Used for function signatures (Pydantic models, type unions)
- **Docstrings:** Sparse (minimal documentation)
- **Error handling:** HTTPException for API errors, try/except for optional operations

### JavaScript (app.js)
- **Style:** Modern ES6+
- **Async:** async/await pattern throughout
- **DOM:** Direct DOM manipulation (no jQuery)
- **Error handling:** try/catch with console.error
- **Naming:** camelCase for variables/functions
- **Comments:** Sectioned with `// ----------`

### HTML/CSS (index.html)
- **Style:** Inline styles in `<style>` tag
- **Classes:** Minimal, semantic names (.card, .row, .muted)
- **Responsiveness:** Basic flexbox, no media queries
- **Accessibility:** Minimal (no ARIA attributes)

## AI Assistant Best Practices

### When Making Changes

1. **Read before write:** Always read existing code to understand patterns
2. **Follow conventions:** Match existing code style
3. **Test thoroughly:** Manual testing is required (no automated tests)
4. **Document in commits:** Explain "why" in commit messages
5. **Update CLAUDE.md:** Keep this file current with changes

### When Adding Features

1. **Check environment:** Does it need new env vars?
2. **Update README:** User-facing features need documentation
3. **Validate inputs:** Always sanitize user input
4. **Handle errors:** Provide clear error messages
5. **Test edge cases:** Single-file, multi-disc, missing files, etc.

### When Debugging

1. **Check logs first:** `docker compose logs -f`
2. **Verify paths:** Most issues are path mapping problems
3. **Check permissions:** PUID/PGID must match host
4. **Test API directly:** Use curl to isolate frontend vs backend
5. **Inspect database:** SQLite is easy to query directly

### When Refactoring

1. **Small changes:** This is a personal project, avoid major rewrites
2. **Preserve behavior:** Don't break existing workflows
3. **Test regressions:** Verify all features still work
4. **Document changes:** Update this file if architecture changes

## Project Philosophy

### Design Principles

1. **Simplicity over features:** Minimal, focused functionality
2. **Personal use over production:** No enterprise requirements
3. **Clear errors over silent failures:** Users should know what went wrong
4. **Pragmatic over perfect:** "Vibe-coded" origin, functional over elegant

### Non-Goals

- Enterprise-scale deployment
- Multi-tenancy
- High availability
- Comprehensive test coverage
- Public API exposure
- Advanced authentication/authorization

### Maintenance Expectations

**From README:**
> "This project was created to scratch a personal itch, and was almost entirely vibe-coded with ChatGPT. I will probably not be developing it further, looking at issues, or accepting pull requests."

**Implications for AI Assistants:**
- Focus on bug fixes over new features
- Preserve working functionality
- Keep changes minimal and focused
- Don't over-engineer solutions
- Prioritize clarity and debuggability

---

## Revision History

- **2025-11-15 (Update):** Architecture documentation update
  - Added torrent_helpers.py module documentation (~220 lines)
  - Updated line counts for evolved modules (db.py, covers.py, utils.py, app.js)
  - Enhanced Architecture & Data Flow with new workflows (cover caching, torrent state tracking)
  - Added recent features: live torrent state tracking, shareable URLs, cover integration, log rotation, dark theme
  - Updated codebase structure to reflect current modular organization
  - Documented torrent matching strategies (hash, MAM ID tags, fuzzy matching)

- **2025-11-15:** Initial CLAUDE.md creation based on codebase analysis
  - Documented all major components and workflows
  - Added recent development history from git log
  - Included debugging tips and common tasks
  - Established conventions and best practices

---

*This document should be updated whenever significant changes are made to the codebase structure, architecture, or conventions.*
