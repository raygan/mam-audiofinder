# Series Tab Integration Roadmap

This roadmap enumerates the concurrent-ready tasks AI assistants can execute to ship the Series tab, richer card-driven discovery, Hardcover API integration, and safe multi-book imports.

## Legend
- `[SEQ]` — Must be completed in presented order within the phase.
- `[CON]` — Can run concurrently with other `[CON]` tasks in the same phase.

## Phase 0 — Research & Guardrails
1. `[SEQ]` Review `documentation/hardcover-api-ref.md` and confirm current request/response schemas, auth headers, and rate-limit notes (target: summary + open questions).
2. `[CON]` Capture explicit Hardcover API rate limits (per key, per endpoint) and document throttle strategy (retry/backoff policy doc stub in `documentation/hardcover-api-ref.md`).
3. `[CON]` Inventory data the Series tab must display (series title, position, release data, cover URL) and map to existing UI helpers (esp. `card_helper`).

## Phase 1 — Unified Title Search Controls
1. `[SEQ]` Extend the card helper context so every rendered search/history card includes the normalized "unified title" and card GUID.
2. `[CON]` Add a "Series Search" icon/button on each card; clicking dispatches a frontend event carrying the unified title.
3. `[SEQ]` Build a backend endpoint `/api/series/search` that accepts `title`, `author`, falls back to normalized card title, and fans out to MAM + Hardcover queries.
4. `[CON]` Update the search results reducer so Series-search-triggered payloads render adjacent to the original card stack without clobbering pagination caches.

## Phase 2 — Hardcover API Series Data
1. `[SEQ]` Add a dedicated Hardcover client module encapsulating base URL, auth token, and shared headers; reuse rate-limit values from Phase 0.
2. `[CON]` Implement a `search_series(title, author)` call returning normalized series metadata (id, name, match confidence, book counts).
3. `[CON]` Implement `list_series_books(series_id)` that returns book records ready for `card_helper` consumption (title, narrators, cover, torrent refs when present).
4. `[SEQ]` Define cache + persistence strategy (SQLite table or in-memory TTL store) so repeated UI clicks avoid exceeding rate limits.

## Phase 3 — Series Tab & Card Rendering

### Task 12: Route + Template `[SEQ]`
1. Add `/series` route to the page router in `app/routes/basic.py` to serve new `app/templates/series.html` mirroring existing search/showcase scaffolding.
2. Update nav bar in `app/templates/base.html` with "📚 Series" link pointing to `/series`.
3. Point template at `/static/pages/series.js` for bootstrap script.
4. Create `app/static/pages/series.js` to bootstrap `SeriesView`, mirroring how `search.js` wires `SearchView` (`app/static/pages/search.js:17-67`).
5. Wire page controller to listen for `series-search` event (already emitted by `app/static/js/components/seriesSearchButton.js`) to pre-populate the new tab or open series modal with originating card metadata.

### Task 13: Search Table + Limit Selector `[CON]`
1. Build `app/static/js/views/seriesView.js` that renders Hardcover matches in a `<table>` before cards are shown.
2. Call `api.searchSeries()` (`app/static/js/core/api.js:234-254`) and display columns: Series, Author, Book Count, Readers, plus "View books" affordance.
3. Surface author filter + "Search #" selector with values `5,10,20,30,40,50` bound to backend limit in `SeriesSearchRequest` (`app/routes/series.py:19-41`).
4. Default selector to `hardcover_series_limit` from `/config` (`app/routes/basic.py:34-52`).
5. Keep state in Router so `/series?q=stormlight&limit=20` deep-links work.
6. When `series-search` event arrives from search/showcase card, reuse same `SeriesView` instance to run lookup and focus/highlight the originating row.

### Task 14: Detail Cards via CardHelper `[CON]`
1. On row click, fetch `/api/series/{id}/books` (`app/routes/series.py:77-140`).
2. Render each book using `createBookCard()` (`app/static/js/components/cardHelper.js:27-121`) for consistent markup, normalized titles, and card GUIDs.
3. Show book cards in flex grid under table with breadcrumbs back to table.
4. Extend backend response so each book includes `mam_match` metadata by calling existing `/search` logic (`app/routes/search.py:34-124`) with book title/author.
5. Bubble `in_abs_library` flag through to `cardHelper` so `addLibraryIndicator()` can render availability badge.
6. Lazy covers work automatically via `cardHelper`'s `<img loading="lazy">`; supplement with `IntersectionObserver` if extra skeletons needed.

### Task 15: Rate-Limit Toasts + Modal Flow `[SEQ]`
1. Create lightweight toast component (`app/static/js/components/toast.js` + styles in `app/static/css/main.css`).
2. `SeriesView` calls toast whenever `api.searchSeries` or `api.getSeriesBooks` rejects with HTTP 429/503.
3. Surface messages like "Hardcover rate limit hit, retry in 30s" and log via `console.warn` for backend correlation.
4. Reuse toast helper anywhere else transient status is needed.
5. For modal/slide requirement: mount same `SeriesView` DOM (table + detail panel) inside hidden drawer on search page.
6. When `seriesSearchButton` fires, slide drawer in, run `loadSeries` with card's normalized title.
7. Reset triggering button via `setSeriesSearchButtonSuccess/Error()` once results arrive.
8. Ensure modal/drawer can be dismissed or retried without page refresh.

### Search # ↔ Backend Limit Coupling `[CON]`
1. Update per-page selector in `app/templates/search.html:9-20` so `<select id="perpage">` options are exactly `5,10,20,30,40,50`.
2. Have `SearchPage` (`app/static/pages/search.js:38-74`) default to `20` when no state exists.
3. Keep Router updates in sync so bookmarks reflect new values.
4. On server, clamp and validate `perpage` inside `/search` (`app/routes/search.py:37-55`) against same list (fallback to `20` if invalid).
5. Mirror same allowed set for Hardcover series limit: make `SeriesSearchRequest.limit` a constrained int (`Field(ge=5, le=50)`) or explicit whitelist.
6. Drive both `/series` page select and search overlay select from shared constant so UX + API never drift.
7. Keep MAM and Hardcover queries under rate limits and reduce cache churn (cache keys already include `perpage`).

## Phase 4 — Multi-Book Download & Import Pipeline
1. `[SEQ]` Extend import planning logic to accept multiple book payloads per torrent without altering the disk-flattening helper contracts.
2. `[CON]` Update database schema/migrations if additional linkage tables (torrent -> multiple books) are required; keep migrations idempotent.
3. `[SEQ]` Modify the worker/import route to enqueue per-book ABS verification while ensuring a single torrent download fan-outs into multiple library imports safely.
4. `[CON]` Add regression tests that simulate multi-book torrents and verify flattening rules remain untouched (see `tests/` import suites).

## Phase 5 — Validation & Telemetry
1. `[SEQ]` Create integration tests (pytest + httpx mocks) covering the new `/api/series/search` and Hardcover client methods, including rate-limit fallbacks.
2. `[CON]` Instrument logging/tracing (structured logs) around Hardcover requests to surface latency, retries, and throttled calls.
3. `[SEQ]` Update `README.md`/`FRONTEND.md` with Series tab usage instructions, new env vars (Hardcover API key/URL), and deployment notes.
4. `[CON]` Run manual UX verification: card buttons, Series tab flows, multi-book download scenarios, and ensure Audiobookshelf imports complete without flattening regressions.
