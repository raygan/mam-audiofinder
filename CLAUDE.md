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
- **Vanilla JavaScript** (no frameworks)
- **HTML5** with minimal CSS
- **Single-page application** pattern

### Infrastructure
- **Docker** (containerization)
- **Docker Compose** (orchestration)

## Codebase Structure

```
mam-audiofinder/
├── app/
│   ├── main.py                 # FastAPI application (core logic)
│   ├── static/
│   │   ├── app.js             # Frontend JavaScript
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
2. **FastAPI Endpoints** (main.py) → Backend API
3. **External Services:**
   - MAM API (search, torrent download)
   - qBittorrent WebUI API (torrent management)
4. **SQLite Database** (history.db) → Persistent storage
5. **Filesystem Operations** → Import/copy/link files

### Key Workflows

#### 1. Search Workflow
```
User Input → POST /search → MAM API → Parse Results → Display
```

#### 2. Add to qBittorrent Workflow
```
User Click → POST /add → Fetch .torrent → qBittorrent API → Save to DB
```

#### 3. Import Workflow
```
User Import → POST /import → Validate Paths → Copy/Link/Move Files → Update Category → Mark Complete
```

## Key Files & Modules

### `/app/main.py` (646 lines)

**Primary application file containing:**

#### Configuration (lines 11-48)
- Environment variable loading
- MAM cookie handling
- qBittorrent connection settings
- Import behavior settings (link/copy/move)
- UMASK application

#### Database Schema (lines 50-78)
```sql
CREATE TABLE history (
  id INTEGER PRIMARY KEY,
  mam_id TEXT,
  title TEXT,
  author TEXT,
  narrator TEXT,
  dl TEXT,
  added_at TEXT,
  qb_status TEXT,
  qb_hash TEXT,
  imported_at TEXT
)
```

#### Endpoints

| Route | Method | Purpose | Lines |
|-------|--------|---------|-------|
| `/` | GET | Serve UI | 97-99 |
| `/health` | GET | Health check | 86-88 |
| `/config` | GET | Return config | 90-95 |
| `/search` | POST | Search MAM | 102-199 |
| `/add` | POST | Add to qBittorrent | 217-331 |
| `/history` | GET | Fetch history | 334-343 |
| `/history/{id}` | DELETE | Remove history item | 345-349 |
| `/qb/torrents` | GET | List completed torrents | 352-386 |
| `/import` | POST | Import to library | 479-646 |

#### Core Functions

**`flatten(v)` (lines 142-165)**
- Normalizes MAM API response data (handles dicts, lists, JSON strings)
- Converts author/narrator info to comma-separated strings

**`detect_format(item)` (lines 167-177)**
- Extracts file format from torrent metadata
- Uses regex to find audio formats (MP3, M4B, FLAC, etc.)

**`qb_login(client)` (lines 202-207)**
- Authenticates with qBittorrent WebUI
- Returns session cookie for subsequent requests

**`sanitize(name)` (lines 395-397)**
- Cleans filenames for filesystem compatibility
- Replaces colons, slashes, backslashes

**`next_available(path)` (lines 399-407)**
- Finds non-conflicting path by appending (2), (3), etc.
- Prevents overwriting existing files/folders

**`extract_disc_track(path, root)` (lines 409-445)**
- Parses disc/track numbers from file paths
- Supports patterns: "Disc 01", "Track 01", "Chapter 01", etc.
- Returns (disc_num, track_num, extension) tuple

**`try_hardlink(src, dst)` (lines 447-452)**
- Attempts to create hardlink
- Falls back gracefully on failure (returns False)

**`copy_one(src, dst)` (lines 454-471)**
- Implements copy/link/move based on IMPORT_MODE
- Returns action taken: "linked", "copied", or "moved"

#### FLATTEN_DISCS Feature (lines 564-587)
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
1. Extract disc/track numbers from all files
2. Sort by (disc_num, track_num)
3. Rename sequentially as "Part 001.mp3", "Part 002.mp3", etc.

### `/app/static/app.js` (375 lines)

**Frontend Logic:**

#### Key Functions

**`runSearch()` (lines 44-136)**
- Collects form inputs
- POSTs to `/search`
- Renders results table
- Handles Add button functionality

**`loadHistory()` (lines 156-375)**
- Fetches `/history`
- Renders history table
- Creates expandable import forms
- Handles Import and Remove buttons

**`escapeHtml(s)` (lines 139-144)**
- Prevents XSS by escaping HTML characters

**`formatSize(sz)` (lines 146-154)**
- Converts bytes to human-readable format (KB, MB, GB)

#### Import Form Logic (lines 232-368)
- Dynamically loads completed torrents from `/qb/torrents`
- Allows editing author/title before import
- Shows import statistics (files copied/linked/moved)
- Updates UI status after successful import

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

#### Frontend Changes (app.js, index.html)
```bash
# 1. Edit files in app/static/ or app/templates/
# 2. Rebuild container (FastAPI serves static files)
docker compose up -d --build

# 3. Hard refresh browser (Ctrl+Shift+R)
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

**Path Mapping Logic (main.py:516-524):**
```python
def map_qb_path(p: str) -> str:
    # qB returns /downloads/Book
    # This app needs /media/torrents/Book
    if p.startswith("/downloads"):
        return p.replace("/downloads", "/media/torrents", 1)
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

**Pattern: Idempotent ALTER TABLE**
```python
# Add columns if missing (lines 66-78)
for ddl in (
    "ALTER TABLE history ADD COLUMN author TEXT",
    "ALTER TABLE history ADD COLUMN narrator TEXT"
):
    try:
        cx.execute(text(ddl))
    except Exception:
        pass  # Column already exists
```

## Recent Development History

### Recent Features & Fixes

1. **Hardlink Verification & Display** (commit 32616c9)
   - Added visual feedback showing whether files were hardlinked vs copied
   - Improved transparency in import process

2. **FLATTEN_DISCS Feature** (commit 6dcdd84)
   - Automatically reorganizes multi-disc audiobooks
   - Solves Audiobookshelf compatibility issues
   - Default enabled, configurable via env var

3. **Import Validation** (commit 7c6e1c9)
   - Fixed silent failures during import
   - Added clear error messages for missing paths
   - Validates source exists before attempting copy

4. **Docker Permission Fixes** (commits 7a78a96, 041243d)
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
# 1. Define endpoint in main.py
@app.post("/new-feature")
async def new_feature(body: dict):
    # Implementation
    return {"ok": True}

# 2. Add frontend call in app.js
async function callNewFeature() {
    const r = await fetch('/new-feature', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({...})
    });
    return r.json();
}

# 3. Test manually
# 4. Commit with descriptive message
```

### Adding Environment Variable

```python
# 1. Add to env.example
NEW_SETTING=default_value

# 2. Load in main.py config section
NEW_SETTING = os.getenv("NEW_SETTING", "default_value")

# 3. Add validation in validate_env.py if needed
if not os.getenv("NEW_SETTING"):
    warnings.append("WARNING: NEW_SETTING not set...")

# 4. Document in README.md
# 5. Update CLAUDE.md environment table
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

```python
# Use idempotent pattern
with engine.begin() as cx:
    try:
        cx.execute(text("ALTER TABLE history ADD COLUMN new_field TEXT"))
    except Exception:
        pass  # Column already exists
```

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

- **2025-11-15:** Initial CLAUDE.md creation based on codebase analysis
  - Documented all major components and workflows
  - Added recent development history from git log
  - Included debugging tips and common tasks
  - Established conventions and best practices

---

*This document should be updated whenever significant changes are made to the codebase structure, architecture, or conventions.*
