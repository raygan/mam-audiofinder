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
1. `[SEQ]` Create a Series tab entry in the top-level navigation routed to a new template using the card helper components.
2. `[CON]` Display Hardcover search matches as a list/grid with lazy-loaded covers and include metadata chips (book count, avg length, match score).
3. `[CON]` When a series row is clicked, fetch `list_series_books` and render book cards (reuse existing card helper) while preserving the originating search query for breadcrumbs.
4. `[SEQ]` Handle empty/error states (rate limit hit, missing data) with reusable toasts and log entries.

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
