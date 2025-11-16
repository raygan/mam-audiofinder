# Targeted UI & Cover Update Plan

## Table of Contents
1. Dark Background With Maroon Accents
2. Audiobookshelf Cover Fetch & Caching
3. Centralized Log Rotation
4. Sharable Search/History URLs
5. Grouped “Showcase” Search Mode
6. Code Cleanup & Progressive Rendering
7. Metadata & Testing Prep
8. ABS Import Verification
MAM Audiobook Finder - Refined Todo List

---

## ✔ 1. Dark Background With Maroon Accents — *Completed*
- [x] Define new palette tokens  
- [x] Update `body`/`.app-shell` styles  
- [x] Restyle panels/cards  
- [x] Adjust typography  
- [x] Refresh button styles  
- [x] Update templates  
- [ ] Capture before/after screenshots

---

## ✔ 2. Audiobookshelf Cover Fetch & Caching — *Completed*
- [x] Add env vars + validation  
- [x] Implement `fetch_abs_cover`  
- [x] Extend DB schema  
- [x] Surface metadata in search rows  
- [x] Cache lookups  
- [x] Update `/api/covers/fetch` + service  
- [x] Add refresh endpoint  
- [x] Auto-heal missing-file cache cases  

---

## ✔ 3. Centralized Log Rotation (Default 5 Files) — *Completed*
- [x] Log destination setup  
- [x] Replace prints with logger  
- [x] Add log rotation env vars  
- [x] Ensure console logging works  
- [x] Document rotation behavior  

---

## ✔ 4. Sharable Search/History URLs — *Completed*
- [x] Define URL schema  
- [x] Push state on searches  
- [x] Parse URL on load  
- [x] Handle `popstate`  
- [x] Reflect filters in URL  

---

## 5. Display Covers With Grouped Searches (“Showcase” Mode) — *Completed*
- [x] Create a new helper function for showcase_mode
- [x] Create new page link from toolbar that shows showcase mode
- [x] use existing .sql databases or expand if necessary
- [x] Add a search window from 'search bar' (default 100 results)
- [x] Group searches by normalized title in audible style grid instead of a list table
- [x] Render shared cover
- [x] When a cover is clicked open the list of audiobooks in a list view below on title's own page  
- [x] Responsive layout  
- [x] Lazy-load covers  

---

## ✔ 6. Code Cleanup & Progressive Search Rendering — *Completed*
- [x] Split `main.py` into modules  
- [x] Move migrations out of runtime  
- [x] Standardize logging  
- [x] Implement `CoverService`  
- [x] Progressive image rendering  


---

## ✔ 7. Top-Level Task Bar — *Completed*
- [x] Add persistent task bar
- [x] Extract to helper
- [x] Design logs view
- [x] Evaluate additional destinations  

---

## 8. — Flatten UI With Tree View

All backend, frontend, Python syntax validation, and documentation tasks are complete.

Remaining:  
- [x] Manual testing (run-time verification)

---
# MAM Audiobook Finder - Refined Todo List

## Phase 1. ABS Import Verification System
*Verify that imports successfully appear in Audiobookshelf after completion*

### Database Schema Updates
- [x] **Create migration 006_add_abs_verification.sql** in `app/db/migrations/`
  - Add `abs_verify_status` column (TEXT) to history table - stores 'verified', 'mismatch', 'pending', or 'unreachable'
  - Add `abs_verify_note` column (TEXT) to history table - stores diagnostic messages like "Title mismatch: expected 'X' found 'Y'" or "Not found in library"
  - Migration should target history.db and use ALTER TABLE statements with proper NULL defaults

### ABS Verification Client Implementation
- [x] **Extend AudiobookshelfClient class** in `app/abs_client.py` with verification methods:
  - Add `verify_import(title: str, author: str, library_path: str) -> dict` method
  - Review `abs-api-agents.md` line references for `/api/items` endpoint (source/includes/_items.md:3) to understand query parameters and response schema
  - Method should search ABS library using title/author, checking if item exists at expected path
  - Return structured result: `{"status": "verified|mismatch|not_found", "note": "details", "abs_item_id": "id if found"}`
  - Handle connection failures gracefully, returning status='unreachable' without breaking import flow

### Import Route Integration
- [x] **Update import endpoint** in `app/routes/import_route.py`:
  - After successful file copy/link operations, instantiate AudiobookshelfClient
  - Call `verify_import()` with sanitized title, author, and destination path
  - Store verification results in database using UPDATE query on history table
  - Log verification outcomes at INFO level for debugging
  - Ensure verification failures don't rollback successful imports (wrap in try/except)

### Frontend Verification Display
- [x] **Enhance history view** in `app/static/js/views/historyView.js`:
  - Update history API response in `routes/history.py` to include `abs_verify_status` and `abs_verify_note` fields
  - Add visual indicators to history table based on verification status:
    - Green checkmark badge (✓) for 'verified' status
    - Yellow warning icon (⚠) for 'mismatch' with hover tooltip showing note
    - Gray question mark (?) for 'pending' or 'unreachable'
  - Position badges consistently with existing status indicators

### Resilience & Testing
- [x] **Add verification resilience**:
  - Implement retry logic with exponential backoff (max 3 attempts) in verification client
  - Add `ABS_VERIFY_TIMEOUT` env variable (default 10 seconds) to config.py
  - Mock ABS responses in development when `ABS_URL` is not configured
  - Log all verification attempts and outcomes to app.log for troubleshooting

## Phase 2. ABS Library Visibility Feature
*Show which search results already exist in your Audiobookshelf library*

### Search Enhancement Backend
- [ ] **Extend search endpoint** in `app/routes/search.py`:
  - After MAM search results return, create list of title/author pairs
  - Batch query Audiobookshelf `/api/libraries/{id}/items` endpoint (see _libraries.md:3) with filter parameters
  - Match results based on fuzzy title/author comparison (use existing fuzzy matching logic from torrent_helpers.py)
  - Add `in_abs_library` boolean field to each search result
  - Cache library check results in memory for 5 minutes to reduce ABS API calls

### Frontend Library Indicators
- [ ] **Update search view** in `app/static/js/views/searchView.js`:
  - Create a helper which implements the following items modularly:
  - Modify search result rendering to check for `in_abs_library` flag
  - Add green checkmark overlay to cover images for items in library
  - Position checkmark in bottom-right corner with semi-transparent background
  - Use CSS class `.in-library` with ::after pseudo-element for checkmark (✓)
  - Add hover tooltip "Already in your library"

### Update Showcase View     
  - [ ] **Update showcase view** repurpose library_indicator helper to show if any title matches in a group for showcase. 

### Configuration
- [ ] **Add library visibility settings** to `app/config.py`:
  - Add `ABS_CHECK_LIBRARY` boolean env variable (default False) to enable/disable feature
  - Add `ABS_LIBRARY_CACHE_TTL` integer (default 300 seconds) for cache duration
  - Update env.example with new variables and descriptions

## Phase 3. ABS Description Fetching
*Pull book descriptions from Audiobookshelf to enhance UI*

### Database Schema for Descriptions
- [ ] **Create migration 007_add_abs_description.sql**:
  - Add `abs_description` column (TEXT) to history table - stores book synopsis
  - Add `abs_description_source` column (TEXT) - tracks where description came from ('abs', 'mam', 'manual')
  - Consider adding description to covers table for showcase view enhancement
  - Do NOT add to search to prevent crowding

### Description Fetching Implementation
- [ ] **Extend AudiobookshelfClient** in `app/abs_client.py`:
  - Add `fetch_item_details(item_id: str) -> dict` method
  - Use `/api/items/{id}` endpoint (see _items.md schema) to get full item metadata
  - Extract description/synopsis field from response
  - Handle missing descriptions gracefully (return None)
  - Add caching layer to avoid repeated fetches for same item

### API Response Enhancement
- [ ] **Update data responses** to include descriptions:
  - Modify `/api/history` endpoint to include `abs_description` and `abs_description_source`
  - Update `/search` endpoint to attempt description fetch when cover is fetched
  - Add description to showcase view data (`/api/showcase` if implemented)

### Frontend Description Display
- [ ] **Add description rendering**:
  - Update history and showcase views to display descriptions when available
  - Create expandable description sections with "Show more/less" for long text
  - Style descriptions with proper typography and spacing
  - Add source indicator (small "via Audiobookshelf" text)

## Phase 4. Testing Infrastructure
*Establish testing framework for critical functionality*

### Test Framework Setup
- [ ] **Create tests/ package structure**:
  ```
  tests/
  ├── __init__.py
  ├── conftest.py          # pytest configuration and fixtures
  ├── test_search.py       # MAM search payload construction tests
  ├── test_covers.py       # Cover caching and cleanup tests
  ├── test_verification.py # ABS verification logic tests
  └── test_helpers.py      # Utility function tests
  ```

### Core Test Coverage
- [ ] **Implement search tests** in `test_search.py`:
  - Test search payload construction with various parameter combinations
  - Verify proper MAM cookie handling
  - Test response parsing and flattening logic
  - Mock httpx calls to avoid actual MAM API requests

- [ ] **Implement cover tests** in `test_covers.py`:
  - Test cache hit/miss scenarios
  - Verify automatic cleanup when exceeding MAX_COVERS_SIZE_MB
  - Test concurrent cover fetches with connection pooling
  - Mock ABS API responses for predictable testing

- [ ] **Implement verification tests** in `test_verification.py`:
  - Test successful verification scenarios
  - Test mismatch detection logic
  - Test resilience when ABS is unreachable
  - Verify database updates occur correctly

### Test Execution
- [ ] **Add test commands to documentation**:
  - Document pytest installation in requirements-dev.txt
  - Add test execution instructions to CLAUDE.md
  - Create GitHub Actions workflow for automated testing (optional)

## Phase 5. Documentation Updates
*Keep documentation aligned with new features*

### README.md Updates
- [ ] **Document verification feature**:
  - Add "Import Verification" section explaining automatic ABS checks
  - Document verification status indicators in UI
  - Explain when verification runs and how to interpret results
  - Add troubleshooting for common verification issues

- [ ] **Document library visibility feature**:
  - Explain green checkmark indicators on search results
  - Document ABS_CHECK_LIBRARY configuration
  - Note performance implications of library checking

- [ ] **Document progressive cover workflow**:
  - Explain cover fetching from MAM → ABS → local cache
  - Document cache management and cleanup
  - Describe lazy loading behavior in UI

### CLAUDE.md Updates
- [ ] **Add new module documentation**:
  - Document verification helper functions
  - Update abs_client.py section with new methods
  - Add test package structure and patterns
  - Update database schema section with new columns

- [ ] **Update Architecture & Data Flow**:
  - Add verification workflow diagram
  - Update cover caching workflow with library check
  - Document description fetching flow

### Configuration Documentation
- [ ] **Update env.example** with new variables:
  - ABS_VERIFY_TIMEOUT (optional, default 10)
  - ABS_CHECK_LIBRARY (optional, default false)
  - ABS_LIBRARY_CACHE_TTL (optional, default 300)
  - Remove deprecated ABS_LIBRARY_ID references
  
# TO-DO IN FUTURE
## Stretch Goal: Book Descriptions & Enhanced Search
- [ ] Add Hardcover API Endpoint  
- [ ] Optional Audible fallback  
- [ ] Create a series tab to display series and order
- [ ] Import entire series and then add items to series on abs
