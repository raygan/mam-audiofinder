# Targeted UI & Cover Update Plan

## 1. Dark Background With Maroon Accents
- [x] Define new palette tokens in `app/static/css/main.css`: `--bg-primary` (deep charcoal), `--bg-panel` (slightly lighter), `--accent-maroon`, `--accent-hover`.
- [x] Update `body`/`.app-shell` styles for dark gradient background and sufficient padding.
- [x] Restyle panels/cards (search, history, import modal) with translucent backgrounds, subtle borders, and maroon focus accents.
- [x] Adjust typography colors (headings, paragraphs, muted labels) for contrast on dark surfaces; verify WCAG AA levels.
- [x] Refresh button styles: primary buttons use maroon gradient, secondary buttons adopt charcoal outlines; ensure hover/focus states are visibly distinct.
- [x] Update templates to apply new utility classes (`text-subtle`, `panel`, etc.) so markup references centralized styles.
- [ ] Capture before/after screenshots and confirm no bright background flashes remain.

## 2. Audiobookshelf Cover Fetch & Caching
- [x] Add env vars to `.env.example`/`README.md` (`ABS_BASE_URL`, `ABS_API_KEY`, optional library ID) and extend `validate_env.py` with helpful warnings when missing.
- [x] Implement `fetch_abs_cover(title, author)` helper in `app/main.py` (or new module) that queries ABS API for closest match, returning cover URL + ABS book id.
- [x] Extend SQLite `history` table with nullable columns (`abs_item_id`, `abs_cover_url`, `abs_cover_cached_at`); ensure migration is idempotent.
- [x] Surface ABS cover metadata (URL + item id) from the progressive fetch flow back into each search row so Add-to-qB posts can include it.
- [x] Cache successful lookups in DB to avoid repeated API calls; consider storing small cover thumbnails in `/data/covers` if ABS hosting disallows hotlinking.
- [x] Ensure `/api/covers/fetch` + `CoverService` expose item ids/cover paths to the client state so history rows store the freshly fetched art without another lookup.
- [x] Add `/covers/refresh/{mam_id}` endpoint or background task to refresh stale entries (e.g., older than 30 days).
- [x] Fix repeated “Cache HIT but local file missing” cases by auto-healing rows whose shared cover file was purged (redownload once and relink all MAM IDs).

## 3. Centralized Log Rotation (Default 5 Files)
- [x] Decide on log destination (e.g., `/data/logs/app.log`) and ensure directory exists/mounted in Docker.
- [x] Replace ad-hoc `print` statements with Python's `logging` module; create logger in `app/main.py` configured with `RotatingFileHandler`.
- [x] Set default `LOG_MAX_FILES=5` and `LOG_MAX_MB=5` via env vars (`.env.example`, `validate_env.py`) while allowing overrides.
- [x] Ensure console logging still works for Docker (attach `StreamHandler`) and that rotation is shared across background tasks.
- [x] Document rotation behavior in README + AGENTS and CLAUDE, including instructions for log collection in container setups.

## 4. Sharable Search/History URLs
- [x] Define URL schema (e.g., `?q=term&sort=seedersDesc&view=history`) supporting search query, filters, and optional history view toggle.
- [x] Update `app/static/app.js` to push state using `history.replaceState`/`pushState` after searches or when History is opened.
- [x] On page load, parse `location.search` to pre-populate inputs, auto-run search if `q` exists, and auto-open history if `view=history`.
- [x] Handle back/forward navigation by listening to `popstate` and re-running searches/history toggles so the URL stays authoritative.
- [x] Reflect additional filters (when grouping arrives) in the query string to keep shared links accurate.

## 5. Display Covers With Grouped Searches (Alternate “Showcase” Mode)
- [ ] Add a results mode selector (default “List” = current table, alternate “Showcase” = grouped layout) and persist the choice in the URL params.
- [ ] Update frontend search rendering for Showcase mode to group torrents by normalized title (strip format tags, trim whitespace, casefold).
- [ ] For each Showcase group, render a single cover (prefer ABS cover, else fallback art) alongside group metadata (author, narrator).
- [ ] Within each group, list individual torrent options (format, size, seeder counts) as rows or cards beneath the shared cover.
- [ ] Ensure the Showcase layout remains responsive; on mobile stack cover above options, desktop uses side-by-side layout.
- [ ] Add lazy-loading + placeholder shimmer for showcase covers while requests resolve; display simple icon if no cover available.
- [ ] Propagate cover URLs/history ids through “Add to qBittorrent” actions so modals/cards show consistent imagery across both List and Showcase modes.

## 6. Code Cleanup & Progressive Search Rendering
- [x] Split `app/main.py` into smaller modules: `config.py` for env parsing, `db.py` for engine + migrations, `abs_client.py` for Audiobookshelf requests, `covers.py` for caching, and a `routes/` package for FastAPI endpoints. Keep `main.py` focused on bootstrapping.
- [x] Move schema-altering SQL out of runtime blocks and into simple migration scripts (e.g., `db/migrations/001_add_history_columns.sql`) executed at startup; document how to add new migrations.
- [x] Replace `print` debugging with the standard `logging` module plus rotating handlers so background tasks, cover services, and routes share consistent log formatting.
- [x] Wrap cover logic inside a `CoverService` class that exposes `get_cover`, `cache_cover`, and `refresh_cover` methods; inject it where needed to improve testability and avoid global state.
- [x] Improve search UX by rendering textual rows immediately, showing skeleton placeholders for covers, then loading cover images asynchronously (IntersectionObserver + progressive updates) so users see results faster even on slow ABS responses.

## 7. Metadata & Testing Prep
- [ ] Add a migration for `abs_description` (plus optional `abs_description_source`) and plumb it through `/search` + `/history` responses.
- [ ] Extend `AudiobookshelfClient` to fetch description/synopsis fields (e.g., `/api/items/{id}`) so the stretch goal has raw data available.
- [ ] Introduce a `tests/` package with coverage for search payload construction and cover caching to keep regressions visible.
- [ ] Document the progressive cover workflow in `README.md` so future contributors understand how metadata flows from ABS → cache → UI.

## 8. ABS Import Verification
- [ ] Review `abs-api-agents.md` for the canonical import verification flow (endpoints, payloads, expected responses) so we align with existing automation.
- [ ] Add `abs_verify_status` + `abs_verify_note` columns via migration to record Audiobookshelf verification outcomes.
- [ ] Implement an ABS client helper (`verify_import`) that cross-checks imported titles/authors against `/api/items` (or the specific endpoint noted in `abs-api-agents.md`) and validates duration/file counts.
- [ ] Update the import route to call the verification helper post-import and persist the verdict (`verified imported` vs `mismatch`) along with any diagnostic note.
- [ ] Surface the verification state in `/history` output and update the frontend to display a green “Verified import” badge or a warning if ABS reports a mismatch.
- [ ] Add regression coverage/mocking around the verification call so failures don’t break imports when ABS is unreachable.

## 9. ABS Metadata Delivery Strategy
- [ ] Prototype feeding Audiobookshelf book metadata via a generated `metadata.json` alongside imported files; validate what fields ABS honors.
- [ ] Compare that with calling the ABS upload endpoint directly for metadata injection to determine which path keeps data fresher and simpler.
- [ ] Document the chosen approach (and trade-offs) so future ABS uploads keep descriptions, narrators, and cover hints in sync.
- [ ] Read the Audiobookshelf upload API (`POST /api/upload`) docs to understand required headers, JSON, and multipart fields.
- [ ] Add `.env` fields for `ABS_UPLOAD_LIBRARY_ID` and optional `ABS_PATH_MAP` (format `local:/abs`) so we can translate qBittorrent save paths into ABS-accessible paths.
- [ ] Implement path translation helper that maps a local filesystem path (e.g., `/media/torrents/book`) to the ABS server path (`/audiobooks/book`) using the map or defaults.
- [ ] Create a FastAPI endpoint or background job that, after import completion, calls the ABS upload API with the final file/folder, library ID, and metadata. Handle failures with retries and structured logging.
- [ ] Store upload response (ABS item id/status) in the history table to avoid duplicate uploads and power UI indicators.
- [ ] Document the new feature (env config, ABS permissions, expected behavior) in README/AGENTS so users can enable it safely.

## 10. Top-Level Task Bar
- [ ] Add a persistent task bar/nav strip at the top of the app that exposes quick toggles for History and a new Logs panel.
- [ ] Design the Logs view hook so it can surface recent rotating log entries (or link out) without overwhelming the main screen.
- [ ] Evaluate whether other destinations (Settings, Covers cache status, ABS health) belong in the task bar and document the final scope.

## Stretch Goal: Book Descriptions & Enhanced Search Options
- [ ] When fetching ABS data, request synopsis/description fields; store them in DB (`abs_description`) and include in `/search` responses.
- [ ] If ABS lacks descriptions, optionally query Audible (existing helper or new minimal fetch) for fallback blurbs; clearly label source.
- [ ] Display description text beneath grouped results with collapse/expand behavior to avoid overly tall cards; respect dark theme readability.
- [ ] Add searchable filters below description area (format tags, narrator, min seeders) so users can refine within the grouped context.
- [ ] Document new capabilities in `README.md` and update screenshots once descriptions and grouped covers ship.
